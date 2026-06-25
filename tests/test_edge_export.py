"""
Tests for the ONNX edge export pipeline.

Validates:
  - Feature/class constants match schema
  - MLP export produces valid ONNX (requires GPU environment)
  - ONNX Runtime inference works
  - Output shape correctness

Note: PyTorch-dependent tests use subprocess isolation to prevent
OMP initialization crashes from killing the test runner on macOS.
These tests run fully on the venus L40S GPU server.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from pipeline.export_to_edge import (
    FEATURE_NAMES,
    NUM_CLASSES,
    NUM_FEATURES,
    THREAT_CLASSES,
)


def _torch_available() -> bool:
    """Check if PyTorch can be imported without crashing the process."""
    import os
    env = {**os.environ, "KMP_DUPLICATE_LIB_OK": "TRUE"}
    result = subprocess.run(
        [sys.executable, "-c", "import torch; print(torch.__version__)"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    return result.returncode == 0


TORCH_OK = _torch_available()


def _ort_available() -> bool:
    """Check if ONNX Runtime can be imported."""
    result = subprocess.run(
        [sys.executable, "-c", "import onnxruntime; print(onnxruntime.__version__)"],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode == 0


ORT_OK = _ort_available()


class TestConstants:
    """Verify export constants match the schema and pipeline."""

    def test_feature_count(self):
        assert NUM_FEATURES == len(FEATURE_NAMES)
        assert NUM_FEATURES == 10

    def test_class_count(self):
        assert NUM_CLASSES == len(THREAT_CLASSES)
        assert NUM_CLASSES == 6

    def test_threat_classes_match_profiles(self):
        from pipeline.synthetic_threat_generator import THREAT_PROFILES
        for cls in THREAT_CLASSES:
            assert cls in THREAT_PROFILES, f"Export class {cls} not in generator profiles"

    def test_features_are_numeric_fields(self):
        """Features should correspond to numeric ThreatEvent fields."""
        expected_numeric = {
            "bearing_deg", "range_m", "altitude_m_agl", "velocity_mps",
            "heading_deg", "radar_cross_section_m2", "track_age_s",
            "track_confidence_0_1", "elevation_deg", "frequency_mhz",
        }
        assert set(FEATURE_NAMES) == expected_numeric


@pytest.mark.skipif(not TORCH_OK, reason="PyTorch not available on this platform")
class TestMLPExport:
    """Test MLP model export to ONNX (subprocess-isolated)."""

    def test_export_and_validate(self):
        """Export MLP to ONNX and validate via subprocess."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.onnx"
            script = f"""
import sys
sys.path.insert(0, '{Path(__file__).parent.parent}')
from pipeline.export_to_edge import export_mlp_onnx
import json
result = export_mlp_onnx('{model_path}', validate=True)
print(json.dumps(result, default=str))
"""
            env = {**__import__("os").environ, "KMP_DUPLICATE_LIB_OK": "TRUE"}
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, timeout=60, env=env,
            )
            assert result.returncode == 0, f"Export failed: {result.stderr}"
            output = json.loads(result.stdout.strip().split("\n")[-1])
            assert output["success"]
            assert output["num_features"] == NUM_FEATURES
            assert output["num_classes"] == NUM_CLASSES
            assert model_path.exists()

    @pytest.mark.skipif(not ORT_OK, reason="ONNX Runtime not available")
    def test_ort_inference_subprocess(self):
        """Export and run ORT inference in subprocess."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.onnx"
            script = f"""
import sys, json, numpy as np
sys.path.insert(0, '{Path(__file__).parent.parent}')
from pipeline.export_to_edge import export_mlp_onnx, NUM_FEATURES, NUM_CLASSES
export_mlp_onnx('{model_path}', validate=False)
import onnxruntime as ort
session = ort.InferenceSession('{model_path}')
test_input = np.random.randn(1, NUM_FEATURES).astype(np.float32)
outputs = session.run(None, {{"features": test_input}})
assert outputs[0].shape == (1, NUM_CLASSES), f"Bad shape: {{outputs[0].shape}}"
# Batch test
batch_input = np.random.randn(32, NUM_FEATURES).astype(np.float32)
batch_out = session.run(None, {{"features": batch_input}})
assert batch_out[0].shape == (32, NUM_CLASSES)
print(json.dumps({{"success": True, "shape_single": list(outputs[0].shape), "shape_batch": list(batch_out[0].shape)}}))
"""
            env = {**__import__("os").environ, "KMP_DUPLICATE_LIB_OK": "TRUE"}
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, timeout=60, env=env,
            )
            assert result.returncode == 0, f"ORT inference failed: {result.stderr}"
            output = json.loads(result.stdout.strip().split("\n")[-1])
            assert output["success"]
            assert output["shape_single"] == [1, NUM_CLASSES]
            assert output["shape_batch"] == [32, NUM_CLASSES]
