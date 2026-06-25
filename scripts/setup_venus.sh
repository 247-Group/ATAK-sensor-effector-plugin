#!/usr/bin/env bash
# =============================================================================
# RACK FP Plugin — Venus Server Setup (venus.247grp.net)
# =============================================================================
#
# Protocol 1-2 from the SolarStorm deployment manifest.
# Configures the venus hypervisor for ML workloads.
#
# Prerequisites:
#   - SSH access to venus.247grp.net as root or sudo-capable user
#   - ZFS datasets already provisioned by host admin
#
# Usage:
#   # Run discovery (safe, read-only)
#   bash scripts/setup_venus.sh discover
#
#   # Full setup (requires root)
#   sudo bash scripts/setup_venus.sh setup
#
#   # Verify environment
#   bash scripts/setup_venus.sh verify
# =============================================================================

set -euo pipefail

VENV_PATH="/opt/venv/ml-rack"
OLLAMA_PORT=11434
ALLOWED_SUBNET="10.247.4.0/24"
ALLOWED_HOST="10.247.4.44"

# ============================================================================
# Protocol 1: Hardware, ZFS, and Network Discovery
# ============================================================================

discover() {
    echo "=========================================="
    echo "Protocol 1: Hardware Discovery"
    echo "=========================================="
    echo ""

    echo "--- System Architecture ---"
    uname -a
    echo ""

    echo "--- CPU ---"
    lscpu | grep -E "(Model name|CPU\(s\)|Thread|Socket|Architecture)"
    echo ""

    echo "--- Memory ---"
    free -h
    echo ""

    echo "--- Block Devices ---"
    lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE
    echo ""

    echo "--- NVMe Devices ---"
    if command -v nvme &>/dev/null; then
        nvme list 2>/dev/null || echo "  nvme-cli not installed or no NVMe devices"
    else
        ls -la /dev/nvme* 2>/dev/null || echo "  No NVMe devices found"
    fi
    echo ""

    echo "--- Swap Status ---"
    swapon --show 2>/dev/null || echo "  No swap active"
    echo ""

    echo "--- ZFS Pools ---"
    if command -v zpool &>/dev/null; then
        zpool status 2>/dev/null || echo "  No ZFS pools"
        echo ""
        echo "--- ZFS Datasets ---"
        zfs list 2>/dev/null || echo "  No ZFS datasets"
    else
        echo "  ZFS not installed"
    fi
    echo ""

    echo "--- 9p Mounts ---"
    mount | grep 9p || echo "  No 9p mounts found"
    echo ""
    echo "--- /etc/fstab 9p entries ---"
    grep -i 9p /etc/fstab 2>/dev/null || echo "  No 9p entries in fstab"
    echo ""

    echo "--- NVIDIA GPU ---"
    if command -v nvidia-smi &>/dev/null; then
        nvidia-smi
    else
        echo "  nvidia-smi not found (NVIDIA driver not installed or not in PATH)"
    fi
    echo ""

    echo "--- CUDA Version ---"
    if [[ -f /usr/local/cuda/version.txt ]]; then
        cat /usr/local/cuda/version.txt
    elif command -v nvcc &>/dev/null; then
        nvcc --version | grep release
    else
        echo "  CUDA toolkit not found"
    fi
    echo ""

    echo "--- Network Interfaces ---"
    ip addr show 2>/dev/null | grep -E "(inet |^[0-9])" || ifconfig 2>/dev/null | grep -E "(inet |^[a-z])"
    echo ""

    echo "--- Firewall Status ---"
    if command -v ufw &>/dev/null; then
        ufw status verbose 2>/dev/null || echo "  ufw not active"
    fi
    if command -v iptables &>/dev/null; then
        echo "--- iptables rules (filter) ---"
        iptables -L -n --line-numbers 2>/dev/null | head -30 || echo "  Requires root"
    fi
    echo ""

    echo "--- Ollama Service ---"
    if command -v ollama &>/dev/null; then
        ollama --version 2>/dev/null || echo "  ollama binary found but version check failed"
    fi
    ss -tlnp 2>/dev/null | grep $OLLAMA_PORT || echo "  Ollama not listening on port $OLLAMA_PORT"
    echo ""

    echo "--- Python ---"
    python3 --version 2>/dev/null || echo "  Python3 not found"
    if [[ -f "$VENV_PATH/bin/python" ]]; then
        echo "  ml-rack venv exists: $VENV_PATH"
        "$VENV_PATH/bin/python" --version
    else
        echo "  ml-rack venv NOT found at $VENV_PATH"
    fi
    echo ""

    echo "Discovery complete."
}

# ============================================================================
# Protocol 2: Environment Setup
# ============================================================================

setup() {
    echo "=========================================="
    echo "Protocol 2: Environment Setup"
    echo "=========================================="
    echo ""

    # Check root
    if [[ $EUID -ne 0 ]]; then
        echo "ERROR: Setup requires root. Run with sudo."
        exit 1
    fi

    # --- Disable swap if on NVMe (anti-pattern with 1TB RAM) ---
    echo "--- Swap Configuration ---"
    if swapon --show 2>/dev/null | grep -q nvme; then
        echo "WARNING: Swap found on NVMe device. Disabling..."
        swapoff -a
        # Comment out swap entries in fstab
        sed -i.bak '/swap/s/^/#/' /etc/fstab
        echo "  NVMe swap disabled. NVMe reserved for KV cache / L2ARC."
    else
        echo "  No NVMe swap detected (good)."
    fi

    # --- Firewall: Lock down Ollama to allowed subnet ---
    echo ""
    echo "--- Firewall Configuration ---"
    if command -v ufw &>/dev/null; then
        ufw --force enable
        # Allow SSH
        ufw allow ssh
        # Allow Ollama only from allowed subnet
        ufw allow from "$ALLOWED_HOST" to any port $OLLAMA_PORT proto tcp comment "Ollama from lab network"
        ufw allow from 127.0.0.1 to any port $OLLAMA_PORT proto tcp comment "Ollama localhost"
        # Deny all other Ollama access
        ufw deny $OLLAMA_PORT/tcp comment "Block external Ollama access"
        echo "  Ollama port $OLLAMA_PORT restricted to $ALLOWED_HOST + localhost"
        ufw status numbered
    else
        echo "  ufw not available. Applying iptables rules..."
        # Allow Ollama from specific host
        iptables -A INPUT -p tcp --dport $OLLAMA_PORT -s "$ALLOWED_HOST" -j ACCEPT
        iptables -A INPUT -p tcp --dport $OLLAMA_PORT -s 127.0.0.1 -j ACCEPT
        iptables -A INPUT -p tcp --dport $OLLAMA_PORT -j DROP
        echo "  iptables rules applied for port $OLLAMA_PORT"
    fi

    # --- 9p mount optimization ---
    echo ""
    echo "--- 9p Mount Optimization ---"
    if grep -q 9p /etc/fstab 2>/dev/null; then
        # Check if cache=mmap is set
        if ! grep 9p /etc/fstab | grep -q "cache=mmap"; then
            echo "WARNING: 9p mounts missing cache=mmap directive."
            echo "  Current fstab 9p entries:"
            grep 9p /etc/fstab
            echo ""
            echo "  Recommended: Add cache=mmap to mount options for latency mitigation."
            echo "  Example: host_share /home/ollama 9p trans=virtio,cache=mmap,msize=262144 0 0"
        else
            echo "  9p mounts already have cache=mmap (optimal)."
        fi
    else
        echo "  No 9p entries in fstab."
    fi

    # --- Create/configure Python venv ---
    echo ""
    echo "--- Python ML Environment ---"
    if [[ ! -d "$VENV_PATH" ]]; then
        echo "Creating venv at $VENV_PATH..."
        python3 -m venv "$VENV_PATH"
    else
        echo "  Venv exists at $VENV_PATH"
    fi

    # Install Sprint 1 dependencies
    echo "Installing Sprint 1 dependencies..."
    "$VENV_PATH/bin/pip" install --upgrade pip
    "$VENV_PATH/bin/pip" install \
        numpy pandas pyarrow jsonschema \
        pytest pytest-cov aiohttp
    "$VENV_PATH/bin/pip" install \
        torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
    "$VENV_PATH/bin/pip" install \
        xgboost scikit-learn \
        onnx onnxruntime-gpu \
        mlflow

    # Set ownership to mike user
    if id mike &>/dev/null; then
        chown -R mike:mike "$VENV_PATH"
        echo "  Ownership set to mike:mike"
    fi

    echo ""
    echo "Setup complete. Run: bash scripts/setup_venus.sh verify"
}

# ============================================================================
# Verify Environment
# ============================================================================

verify() {
    echo "=========================================="
    echo "Environment Verification"
    echo "=========================================="
    echo ""

    if [[ ! -f "$VENV_PATH/bin/python" ]]; then
        echo "ERROR: venv not found at $VENV_PATH"
        echo "Run: sudo bash scripts/setup_venus.sh setup"
        exit 1
    fi

    "$VENV_PATH/bin/python" - <<'PYEOF'
import sys
print(f"Python: {sys.version}")

checks = {}

# PyTorch + CUDA
try:
    import torch
    checks["PyTorch"] = torch.__version__
    checks["CUDA"] = str(torch.cuda.is_available())
    if torch.cuda.is_available():
        checks["GPU"] = torch.cuda.get_device_name(0)
        checks["VRAM_GB"] = f"{torch.cuda.get_device_properties(0).total_mem / 1e9:.1f}"
        # Quick matmul test
        x = torch.randn(256, 256, device="cuda")
        y = x @ x.T
        checks["GPU_matmul"] = "PASSED"
except ImportError:
    checks["PyTorch"] = "NOT INSTALLED"

# Data stack
try:
    import pandas, pyarrow, numpy
    checks["pandas"] = pandas.__version__
    checks["pyarrow"] = pyarrow.__version__
    checks["numpy"] = numpy.__version__
except ImportError as e:
    checks["data_stack"] = f"MISSING: {e}"

# ONNX
try:
    import onnx, onnxruntime
    checks["ONNX"] = onnx.__version__
    checks["ORT"] = onnxruntime.__version__
    checks["ORT_providers"] = ", ".join(onnxruntime.get_available_providers())
except ImportError:
    checks["ONNX"] = "NOT INSTALLED"

# XGBoost
try:
    import xgboost
    checks["XGBoost"] = xgboost.__version__
except ImportError:
    checks["XGBoost"] = "NOT INSTALLED"

# jsonschema
try:
    import jsonschema
    checks["jsonschema"] = jsonschema.__version__
except ImportError:
    checks["jsonschema"] = "NOT INSTALLED"

for k, v in checks.items():
    print(f"  {k:20s} {v}")

# Overall status
critical = ["PyTorch", "pandas", "numpy", "jsonschema"]
all_ok = all(checks.get(c, "MISSING") not in ("NOT INSTALLED", "MISSING") for c in critical)
print(f"\nSTATUS: {'READY' if all_ok else 'INCOMPLETE'}")
sys.exit(0 if all_ok else 1)
PYEOF
}

# ============================================================================
# Main dispatch
# ============================================================================

case "${1:-discover}" in
    discover) discover ;;
    setup)    setup ;;
    verify)   verify ;;
    *)
        echo "Usage: $0 {discover|setup|verify}"
        exit 1
        ;;
esac
