#!/usr/bin/env python3
"""
RACK FP — Command-Line Interface
==================================

Unified CLI for the RACK Force Protection AI/ML Engine.

Usage:
    python rack_cli.py server               # Start API server
    python rack_cli.py generate             # Generate synthetic data
    python rack_cli.py validate             # Validate existing dataset
    python rack_cli.py export-onnx          # Export MLP to ONNX
    python rack_cli.py verify-env           # Check GPU/ML environment
    python rack_cli.py test                 # Run full test suite
    python rack_cli.py stats               # Print dataset statistics
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def cmd_server(args):
    """Start the RACK FP API server."""
    cmd = [sys.executable, "-m", "server.api", "--host", args.host, "--port", str(args.port)]
    subprocess.run(cmd, cwd=ROOT)


def cmd_generate(args):
    """Generate synthetic threat data."""
    cmd = [
        sys.executable, "pipeline/synthetic_threat_generator.py",
        "--output", args.output,
        "--per-class", str(args.per_class),
        "--seed", str(args.seed),
    ]
    if args.json_export:
        cmd.append("--json-export")
    subprocess.run(cmd, cwd=ROOT)


def cmd_validate(args):
    """Validate existing dataset."""
    cmd = [
        sys.executable, "pipeline/synthetic_threat_generator.py",
        "--output", args.dataset,
        "--validate-only",
    ]
    subprocess.run(cmd, cwd=ROOT)


def cmd_export_onnx(args):
    """Export threat classifier to ONNX."""
    cmd = [
        sys.executable, "pipeline/export_to_edge.py",
        "--model-type", args.model_type,
        "--output", args.output,
    ]
    subprocess.run(cmd, cwd=ROOT)


def cmd_verify_env(args):
    """Verify GPU/ML environment."""
    subprocess.run([sys.executable, "pipeline/verify_env.py"], cwd=ROOT)


def cmd_test(args):
    """Run the test suite."""
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v"]
    if args.coverage:
        cmd.extend(["--cov=pipeline", "--cov=server", "--cov-report=term-missing"])
    subprocess.run(cmd, cwd=ROOT)


def cmd_stats(args):
    """Print dataset statistics."""
    try:
        import pandas as pd
        parquet = ROOT / "data" / "synthetic" / "threat_events.parquet"
        if not parquet.exists():
            print(f"Dataset not found at {parquet}")
            print("Run: python rack_cli.py generate")
            sys.exit(1)

        df = pd.read_parquet(parquet)
        print(f"Dataset: {parquet}")
        print(f"Total events: {len(df):,}")
        print(f"File size: {parquet.stat().st_size / (1024*1024):.2f} MB")
        print(f"\nThreat class distribution:")
        for cls, count in df["threat_class"].value_counts().items():
            print(f"  {cls:25s} {count:6,} ({count/len(df)*100:.1f}%)")
        print(f"\nSensor type distribution:")
        for sensor, count in df["sensor_type"].value_counts().items():
            print(f"  {sensor:25s} {count:6,} ({count/len(df)*100:.1f}%)")
        print(f"\nColumns ({len(df.columns)}):")
        for col in sorted(df.columns):
            nulls = df[col].isna().sum()
            null_str = f" ({nulls:,} null)" if nulls > 0 else ""
            print(f"  {col}{null_str}")
    except ImportError:
        print("pandas not installed. Run: pip install pandas pyarrow")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="RACK FP — AI/ML Engine for Force Protection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s server                     Start API server on :8790
  %(prog)s server --port 9000         Start on custom port
  %(prog)s generate                   Generate 30K synthetic events
  %(prog)s generate --per-class 10000 Generate 60K events
  %(prog)s validate                   Validate existing dataset
  %(prog)s export-onnx                Export MLP to ONNX
  %(prog)s verify-env                 Check GPU/ML dependencies
  %(prog)s test                       Run all tests
  %(prog)s test --coverage            Run tests with coverage
  %(prog)s stats                      Print dataset statistics
""",
    )
    subs = parser.add_subparsers(dest="command", help="Command to run")

    # server
    p = subs.add_parser("server", help="Start the API server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8790)

    # generate
    p = subs.add_parser("generate", help="Generate synthetic threat data")
    p.add_argument("--output", default="data/synthetic/threat_events.parquet")
    p.add_argument("--per-class", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--json-export", action="store_true", default=False, help="Also export as JSONL")

    # validate
    p = subs.add_parser("validate", help="Validate existing dataset")
    p.add_argument("--dataset", default="data/synthetic/threat_events.parquet")

    # export-onnx
    p = subs.add_parser("export-onnx", help="Export model to ONNX")
    p.add_argument("--model-type", default="mlp", choices=["mlp", "xgboost"])
    p.add_argument("--output", default="models/threat_classifier.onnx")

    # verify-env
    subs.add_parser("verify-env", help="Verify GPU/ML environment")

    # test
    p = subs.add_parser("test", help="Run test suite")
    p.add_argument("--coverage", action="store_true", help="Include coverage report")

    # stats
    subs.add_parser("stats", help="Print dataset statistics")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "server": cmd_server,
        "generate": cmd_generate,
        "validate": cmd_validate,
        "export-onnx": cmd_export_onnx,
        "verify-env": cmd_verify_env,
        "test": cmd_test,
        "stats": cmd_stats,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
