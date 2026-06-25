"""Pytest configuration for RACK FP Plugin tests."""
import sys
from pathlib import Path

# Add project root to path so pipeline imports work
sys.path.insert(0, str(Path(__file__).parent.parent))
