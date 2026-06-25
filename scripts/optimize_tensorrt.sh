#!/usr/bin/env bash
# =============================================================================
# RACK FP Plugin — TensorRT Optimization for Jetson Nano / PACSTAR Edge
# =============================================================================
#
# Converts ONNX models to TensorRT engines optimized for edge deployment.
# Supports FP16 and INT8 precision for latency-constrained inference.
#
# Prerequisites:
#   - NVIDIA TensorRT SDK installed (via JetPack on Jetson, or apt on server)
#   - trtexec binary in PATH
#   - ONNX model exported from pipeline/export_to_edge.py
#
# Usage:
#   bash scripts/optimize_tensorrt.sh                              # defaults
#   bash scripts/optimize_tensorrt.sh models/threat_classifier.onnx  # custom path
#   bash scripts/optimize_tensorrt.sh --int8                       # INT8 quantization
#
# Target platforms:
#   - Jetson Nano (Maxwell 128-core, 4GB shared RAM/VRAM)
#   - Jetson Orin NX (Ampere, 8-16GB)
#   - PACSTAR embedded compute modules
#   - Lab server NVIDIA L40S (for benchmarking)
#
# Kill chain timing budget:
#   DETECT (0-5s) -> IDENTIFY (5-15s) -> DECIDE (10-30s) -> ENGAGE (0-10s)
#   Inference must complete within the IDENTIFY phase: <500ms on Jetson Nano
# =============================================================================

set -euo pipefail

# Defaults
ONNX_MODEL="${1:-models/threat_classifier.onnx}"
OUTPUT_DIR="models/tensorrt"
PRECISION="fp16"  # fp16 or int8
BATCH_SIZE=1
WORKSPACE_MB=2048  # 2GB workspace (fits Jetson Nano 4GB)
VERBOSE=false

# Parse additional flags
shift 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --int8)     PRECISION="int8"; shift ;;
        --fp32)     PRECISION="fp32"; shift ;;
        --fp16)     PRECISION="fp16"; shift ;;
        --batch)    BATCH_SIZE="$2"; shift 2 ;;
        --verbose)  VERBOSE=true; shift ;;
        *)          echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Validate input
if [[ ! -f "$ONNX_MODEL" ]]; then
    echo "ERROR: ONNX model not found: $ONNX_MODEL"
    echo "Run first: python pipeline/export_to_edge.py"
    exit 1
fi

# Check for trtexec
if ! command -v trtexec &> /dev/null; then
    echo "=========================================="
    echo "TensorRT (trtexec) not found in PATH"
    echo "=========================================="
    echo ""
    echo "This script requires NVIDIA TensorRT SDK."
    echo ""
    echo "Installation options:"
    echo ""
    echo "  Jetson (JetPack):"
    echo "    sudo apt-get install nvidia-tensorrt"
    echo "    # trtexec is at /usr/src/tensorrt/bin/trtexec"
    echo "    export PATH=\$PATH:/usr/src/tensorrt/bin"
    echo ""
    echo "  x86 Server (L40S):"
    echo "    pip install nvidia-tensorrt"
    echo "    # Or download from https://developer.nvidia.com/tensorrt"
    echo ""
    echo "  Docker (recommended for reproducibility):"
    echo "    docker run --gpus all -v \$(pwd):/workspace nvcr.io/nvidia/tensorrt:24.05-py3 \\"
    echo "      trtexec --onnx=/workspace/$ONNX_MODEL --saveEngine=/workspace/$OUTPUT_DIR/engine.trt"
    echo ""
    echo "Generating command reference for manual execution..."
    echo ""

    # Still output the commands for documentation
    mkdir -p "$OUTPUT_DIR"
fi

mkdir -p "$OUTPUT_DIR"

MODEL_NAME=$(basename "$ONNX_MODEL" .onnx)
ENGINE_FILE="$OUTPUT_DIR/${MODEL_NAME}_${PRECISION}_b${BATCH_SIZE}.trt"

echo "=========================================="
echo "RACK FP TensorRT Optimization"
echo "=========================================="
echo "  ONNX model:    $ONNX_MODEL"
echo "  Output engine:  $ENGINE_FILE"
echo "  Precision:      $PRECISION"
echo "  Batch size:     $BATCH_SIZE"
echo "  Workspace:      ${WORKSPACE_MB}MB"
echo ""

# Build the trtexec command as an array (safe against shell injection)
TRTEXEC_ARGS=(
    --onnx="$ONNX_MODEL"
    --saveEngine="$ENGINE_FILE"
    --workspace="$WORKSPACE_MB"
)

# Precision flags
case $PRECISION in
    fp16)
        TRTEXEC_ARGS+=(--fp16)
        ;;
    int8)
        TRTEXEC_ARGS+=(--int8)
        # INT8 requires calibration data — use representative synthetic events
        TRTEXEC_ARGS+=(--calib="$OUTPUT_DIR/calibration_cache.bin")
        echo "NOTE: INT8 quantization requires calibration data."
        echo "  Generate calibration cache with: python pipeline/generate_calibration.py"
        ;;
    fp32)
        # No extra flags needed for FP32
        ;;
esac

# Dynamic batch support
TRTEXEC_ARGS+=(
    --minShapes=features:1x10
    --optShapes=features:"${BATCH_SIZE}x10"
    --maxShapes=features:32x10
)

if $VERBOSE; then
    TRTEXEC_ARGS+=(--verbose)
fi

echo "Command:"
echo "  trtexec ${TRTEXEC_ARGS[*]}"
echo ""

# Execute if trtexec is available
if command -v trtexec &> /dev/null; then
    echo "Optimizing..."
    trtexec "${TRTEXEC_ARGS[@]}"

    ENGINE_SIZE_KB=$(($(stat -c%s "$ENGINE_FILE" 2>/dev/null || stat -f%z "$ENGINE_FILE") / 1024))
    echo ""
    echo "=========================================="
    echo "Optimization Complete"
    echo "=========================================="
    echo "  Engine:       $ENGINE_FILE"
    echo "  Size:         ${ENGINE_SIZE_KB} KB"
    echo "  Precision:    $PRECISION"
    echo ""

    # Run benchmark
    echo "Running inference benchmark..."
    trtexec --loadEngine="$ENGINE_FILE" \
            --shapes=features:1x10 \
            --warmUp=1000 \
            --iterations=1000 \
            --avgRuns=100 2>&1 | grep -E "(mean|median|percentile|Throughput)"

    echo ""
    echo "Deploy to Jetson:"
    echo "  scp $ENGINE_FILE jetson:/opt/rack-fp/models/"
    echo "  # Note: TRT engines are GPU-architecture specific."
    echo "  # Rebuild on target device if arch differs (Maxwell vs Ada)."
else
    echo "=========================================="
    echo "Command Reference (run on target device)"
    echo "=========================================="
    echo ""
    echo "# FP16 (recommended for Jetson Nano — best latency/accuracy tradeoff)"
    echo "trtexec \\"
    echo "  --onnx=$ONNX_MODEL \\"
    echo "  --saveEngine=${OUTPUT_DIR}/${MODEL_NAME}_fp16.trt \\"
    echo "  --fp16 \\"
    echo "  --workspace=2048 \\"
    echo "  --minShapes=features:1x10 \\"
    echo "  --optShapes=features:1x10 \\"
    echo "  --maxShapes=features:32x10"
    echo ""
    echo "# INT8 (maximum speed, requires calibration)"
    echo "trtexec \\"
    echo "  --onnx=$ONNX_MODEL \\"
    echo "  --saveEngine=${OUTPUT_DIR}/${MODEL_NAME}_int8.trt \\"
    echo "  --int8 \\"
    echo "  --workspace=2048 \\"
    echo "  --minShapes=features:1x10 \\"
    echo "  --optShapes=features:1x10 \\"
    echo "  --maxShapes=features:32x10"
    echo ""
    echo "# Benchmark after build"
    echo "trtexec --loadEngine=${OUTPUT_DIR}/${MODEL_NAME}_fp16.trt --shapes=features:1x10 --iterations=1000"
    echo ""
    echo "# Expected performance targets:"
    echo "#   L40S (lab):        <1ms  per inference (FP16)"
    echo "#   Jetson Orin NX:    <10ms per inference (FP16)"
    echo "#   Jetson Nano:       <50ms per inference (FP16), <500ms required by kill chain"
fi
