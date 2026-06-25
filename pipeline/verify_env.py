"""
GPU Environment Verification Script
====================================

Validates that the ML development environment is correctly configured.
Run this after initial setup and before any training jobs.

Usage:
    python pipeline/verify_env.py
"""

import sys


def check_python():
    v = sys.version_info
    print(f"Python:        {v.major}.{v.minor}.{v.micro}")
    if not (v.major == 3 and v.minor >= 10):
        print("ERROR: Python 3.10+ required")
        return False
    return True


def check_pytorch():
    try:
        import torch
        print(f"PyTorch:       {torch.__version__}")
        print(f"CUDA avail:    {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA version:  {torch.version.cuda}")
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"  GPU {i}:       {props.name} ({props.total_mem / 1e9:.1f} GB)")
            # Quick matmul test
            x = torch.randn(256, 256, device="cuda")
            y = x @ x.T
            assert y.shape == (256, 256)
            print(f"  GPU matmul:  PASSED")
        return True
    except ImportError:
        print("PyTorch:       NOT INSTALLED")
        return False


def check_xgboost():
    try:
        import xgboost as xgb
        print(f"XGBoost:       {xgb.__version__}")
        # Quick training test
        import numpy as np
        X = np.random.randn(100, 10).astype(np.float32)
        y = np.random.randint(0, 6, 100)
        dtrain = xgb.DMatrix(X, label=y)
        params = {"max_depth": 3, "num_class": 6, "objective": "multi:softprob", "verbosity": 0}
        model = xgb.train(params, dtrain, num_boost_round=10)
        preds = model.predict(dtrain)
        assert preds.shape == (100, 6)
        print(f"  XGB train:   PASSED (6-class, 100 samples)")
        # Check GPU support
        try:
            params_gpu = {**params, "device": "cuda"}
            model_gpu = xgb.train(params_gpu, dtrain, num_boost_round=5)
            print(f"  XGB GPU:     AVAILABLE")
        except Exception:
            print(f"  XGB GPU:     CPU only (fine for Sprint 1)")
        return True
    except ImportError:
        print("XGBoost:       NOT INSTALLED")
        return False


def check_onnx():
    try:
        import onnx
        import onnxruntime as ort
        print(f"ONNX:          {onnx.__version__}")
        print(f"ORT:           {ort.__version__}")
        providers = ort.get_available_providers()
        print(f"  Providers:   {', '.join(providers)}")
        has_cuda = "CUDAExecutionProvider" in providers
        print(f"  CUDA ORT:    {'AVAILABLE' if has_cuda else 'CPU only'}")
        return True
    except ImportError:
        print("ONNX Runtime:  NOT INSTALLED")
        return False


def check_sklearn():
    try:
        import sklearn
        print(f"scikit-learn:  {sklearn.__version__}")
        return True
    except ImportError:
        print("scikit-learn:  NOT INSTALLED")
        return False


def check_data_stack():
    try:
        import pandas as pd
        import pyarrow
        import numpy as np
        print(f"pandas:        {pd.__version__}")
        print(f"pyarrow:       {pyarrow.__version__}")
        print(f"numpy:         {np.__version__}")
        # Test Parquet round-trip
        import tempfile
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=True) as tmp:
            df.to_parquet(tmp.name, engine="pyarrow")
            df2 = pd.read_parquet(tmp.name)
        assert df.equals(df2)
        print(f"  Parquet:     PASSED")
        return True
    except ImportError as e:
        print(f"Data stack:    MISSING ({e})")
        return False


def check_jsonschema():
    try:
        import jsonschema
        print(f"jsonschema:    {jsonschema.__version__}")
        return True
    except ImportError:
        print("jsonschema:    NOT INSTALLED")
        return False


def main():
    print("=" * 60)
    print("RACK FP Plugin — Environment Verification")
    print("=" * 60)
    print()

    results = {
        "Python": check_python(),
        "PyTorch": check_pytorch(),
        "XGBoost": check_xgboost(),
        "ONNX": check_onnx(),
        "scikit-learn": check_sklearn(),
        "Data stack": check_data_stack(),
        "jsonschema": check_jsonschema(),
    }

    print()
    print("=" * 60)
    passed = sum(results.values())
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")

    if all(results.values()):
        print("STATUS: ENVIRONMENT READY")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"STATUS: MISSING COMPONENTS: {', '.join(failed)}")
        print("\nInstall missing packages:")
        print("  pip install torch torchvision xgboost scikit-learn onnx onnxruntime pandas pyarrow jsonschema")

    print("=" * 60)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
