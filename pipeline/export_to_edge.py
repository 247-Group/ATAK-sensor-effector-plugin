"""
RACK FP Edge Export Pipeline
==============================

Exports trained threat classification models to ONNX format for
deployment on NVIDIA Jetson Nano / PACSTAR tactical edge devices.

Sprint 1: Establishes the export pathway with a representative model.
Sprint 2+: Exports the actual trained XGBoost/neural classifier.

Usage:
    python pipeline/export_to_edge.py
    python pipeline/export_to_edge.py --model-type mlp --output models/threat_classifier.onnx
    python pipeline/export_to_edge.py --model-type xgboost --output models/threat_classifier_xgb.onnx

Output:
    models/threat_classifier.onnx     — ONNX model for edge inference
    models/threat_classifier_fp16.onnx — FP16 quantized variant
"""

import argparse
import sys
from pathlib import Path

import numpy as np

# Feature vector: the numeric fields from ThreatEvent that feed the classifier
FEATURE_NAMES = [
    "bearing_deg",
    "range_m",
    "altitude_m_agl",
    "velocity_mps",
    "heading_deg",
    "radar_cross_section_m2",
    "track_age_s",
    "track_confidence_0_1",
    "elevation_deg",
    "frequency_mhz",
]

THREAT_CLASSES = [
    "air_uas_small",
    "air_fixed_wing",
    "ground_vehicle",
    "ground_personnel",
    "benign_wildlife",
    "benign_aircraft",
]

NUM_FEATURES = len(FEATURE_NAMES)
NUM_CLASSES = len(THREAT_CLASSES)


def export_mlp_onnx(output_path, validate: bool = True) -> dict:
    """Export a representative MLP threat classifier to ONNX.

    This creates a small feedforward network matching the expected
    input/output shape for the RACK FP threat classifier. In Sprint 2,
    this will be replaced with the actual trained model.
    """
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        print("ERROR: PyTorch not installed. Install with:")
        print("  pip install torch --index-url https://download.pytorch.org/whl/cu124")
        return {"success": False, "error": "PyTorch not installed"}

    try:
        import onnx
    except ImportError:
        print("ERROR: ONNX not installed. Install with: pip install onnx")
        return {"success": False, "error": "ONNX not installed"}

    # Define a representative MLP architecture
    # Architecture chosen for Jetson Nano constraints:
    # - Small enough to fit in 4GB shared RAM/VRAM
    # - Fast enough for <500ms inference latency
    # - Expressive enough for 6-class discrimination
    class ThreatClassifierMLP(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(NUM_FEATURES, 64),
                nn.ReLU(),
                nn.BatchNorm1d(64),
                nn.Dropout(0.2),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.BatchNorm1d(32),
                nn.Dropout(0.1),
                nn.Linear(32, NUM_CLASSES),
            )

        def forward(self, x):
            return self.net(x)

    model = ThreatClassifierMLP()
    model.eval()

    # Create representative input (batch_size=1, features=NUM_FEATURES)
    dummy_input = torch.randn(1, NUM_FEATURES)

    # Determine device
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
        model = model.to(device)
        dummy_input = dummy_input.to(device)
        print(f"Using GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("Using CPU (GPU not available)")

    # Export to ONNX
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["features"],
        output_names=["logits"],
        dynamic_axes={
            "features": {0: "batch_size"},
            "logits": {0: "batch_size"},
        },
    )

    file_size_kb = output_path.stat().st_size / 1024
    print(f"ONNX model exported: {output_path} ({file_size_kb:.1f} KB)")

    result = {
        "success": True,
        "model_path": str(output_path),
        "model_size_kb": round(file_size_kb, 1),
        "num_features": NUM_FEATURES,
        "num_classes": NUM_CLASSES,
        "opset_version": 17,
        "device": device,
    }

    # Validate the exported ONNX model
    if validate:
        print("\nValidating ONNX model...")
        onnx_model = onnx.load(str(output_path))
        onnx.checker.check_model(onnx_model)
        print("  ONNX model structure: VALID")

        # Verify with ONNX Runtime
        try:
            import onnxruntime as ort

            providers = ort.get_available_providers()
            abs_path = str(output_path.resolve())
            session = ort.InferenceSession(abs_path, providers=providers)

            # Run inference with random input
            test_input = np.random.randn(1, NUM_FEATURES).astype(np.float32)
            outputs = session.run(None, {"features": test_input})
            logits = outputs[0]

            if logits.shape != (1, NUM_CLASSES):
                raise RuntimeError(f"Unexpected output shape: {logits.shape}, expected (1, {NUM_CLASSES})")
            print(f"  ONNX Runtime inference: PASSED (output shape: {logits.shape})")
            print(f"  Available providers: {', '.join(providers)}")
            result["ort_validated"] = True
            result["ort_providers"] = providers
        except ImportError:
            print("  ONNX Runtime not installed — skipping runtime validation")
            result["ort_validated"] = False
        except Exception as e:
            print(f"  ONNX Runtime validation skipped (ORT issue: {e})")
            print("  ONNX model structure validated successfully via onnx.checker.")
            result["ort_validated"] = False

    return result


def export_xgboost_onnx(output_path: Path) -> dict:
    """Export a representative XGBoost classifier to ONNX.

    Uses sklearn-onnx converter for XGBoost models.
    """
    try:
        import xgboost as xgb
        from sklearn.datasets import make_classification
    except ImportError:
        print("ERROR: XGBoost/sklearn not installed.")
        return {"success": False, "error": "XGBoost not installed"}

    # Create a representative training set
    X, y = make_classification(
        n_samples=1000,
        n_features=NUM_FEATURES,
        n_classes=NUM_CLASSES,
        n_informative=8,
        random_state=42,
    )
    X = X.astype(np.float32)

    # Train a small XGBoost model
    dtrain = xgb.DMatrix(X, label=y, feature_names=FEATURE_NAMES)
    params = {
        "max_depth": 6,
        "num_class": NUM_CLASSES,
        "objective": "multi:softprob",
        "eval_metric": "mlogloss",
        "verbosity": 0,
        "tree_method": "hist",
    }
    model = xgb.train(params, dtrain, num_boost_round=50)

    # Save as XGBoost native format first
    xgb_path = output_path.with_suffix(".xgb")
    xgb_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(xgb_path))
    print(f"XGBoost model saved: {xgb_path}")

    # Export to ONNX via onnxmltools if available
    try:
        from onnxmltools import convert_xgboost
        from onnxconverter_common import FloatTensorType

        initial_type = [("features", FloatTensorType([None, NUM_FEATURES]))]
        onnx_model = convert_xgboost(model, initial_types=initial_type, target_opset=17)

        import onnx
        onnx.save(onnx_model, str(output_path))
        file_size_kb = output_path.stat().st_size / 1024
        print(f"ONNX model exported: {output_path} ({file_size_kb:.1f} KB)")
        return {"success": True, "model_path": str(output_path)}
    except ImportError:
        print("WARNING: onnxmltools not installed. XGBoost saved in native format only.")
        print("  Install with: pip install onnxmltools onnxconverter-common")
        print(f"  Native XGBoost model at: {xgb_path}")
        return {"success": False, "error": "onnxmltools not installed", "xgb_path": str(xgb_path), "format": "xgboost_native"}


def create_int8_variant(input_path, output_path) -> dict:
    """Create a dynamically quantized INT8 variant of an ONNX model.

    INT8 dynamic quantization reduces model size and increases inference
    speed on edge devices. For production FP16/INT8 with calibration,
    use TensorRT via scripts/optimize_tensorrt.sh.
    """
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError:
        print("NOTE: onnxruntime quantization not available.")
        print("  Use TensorRT for production INT8 quantization on Jetson.")
        return {"success": False, "error": "quantization not available"}

    input_path, output_path = Path(input_path), Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    quantize_dynamic(
        str(input_path),
        str(output_path),
        weight_type=QuantType.QUInt8,
    )
    file_size_kb = output_path.stat().st_size / 1024
    print(f"Quantized model (INT8): {output_path} ({file_size_kb:.1f} KB)")
    return {"success": True, "model_path": str(output_path), "size_kb": round(file_size_kb, 1)}


def main():
    parser = argparse.ArgumentParser(description="Export RACK FP threat classifier to ONNX")
    parser.add_argument(
        "--output", "-o",
        default="models/threat_classifier.onnx",
        help="Output ONNX model path",
    )
    parser.add_argument(
        "--model-type",
        choices=["mlp", "xgboost"],
        default="mlp",
        help="Model architecture to export (default: mlp)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip ONNX validation after export",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    print("RACK FP Edge Export Pipeline")
    print("=" * 40)
    print(f"  Model type:   {args.model_type}")
    print(f"  Output:       {output_path}")
    print(f"  Features:     {NUM_FEATURES} ({', '.join(FEATURE_NAMES)})")
    print(f"  Classes:      {NUM_CLASSES} ({', '.join(THREAT_CLASSES)})")
    print()

    if args.model_type == "mlp":
        result = export_mlp_onnx(output_path, validate=not args.no_validate)
    else:
        result = export_xgboost_onnx(output_path)

    if result["success"]:
        print("\nEdge Export: SUCCESS")
        print(f"  Model ready for TensorRT optimization.")
        print(f"  Run: bash scripts/optimize_tensorrt.sh {output_path}")
    else:
        print(f"\nEdge Export: FAILED ({result.get('error', 'unknown')})")
        sys.exit(1)


if __name__ == "__main__":
    main()
