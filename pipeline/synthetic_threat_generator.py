"""
RACK FP Synthetic Threat Event Generator
=========================================

Generates physics-based labeled ThreatEvent data for AI model training.
Produces 5,000+ events per threat class with Gaussian noise (sigma 5-10%).

Threat classes:
  - air_uas_small:     Small UAS / commercial drones (Group 1)
  - air_fixed_wing:    Fixed-wing aircraft (manned or large UAS)
  - ground_vehicle:    Ground vehicles (wheeled/tracked)
  - ground_personnel:  Dismounted personnel / foot patrols
  - benign_wildlife:   Birds, deer, coyotes (false-positive rejection)
  - benign_aircraft:   Commercial/friendly aircraft (false-positive rejection)

Physics-based parameter ranges derived from:
  - EchoGuard ESA radar specifications (120 deg azimuth, 80 deg elevation, 3km sUAS / 9km vehicle)
  - ATP 3-37 / ATP 3-01.81 force protection doctrine
  - RACK System Architecture v3.0 sensor specifications
  - Kill chain timing constraints (detect 0-5s, identify 5-15s, decide 10-30s)

Usage:
    python pipeline/synthetic_threat_generator.py --output data/synthetic/threat_events.parquet --per-class 5000
    python pipeline/synthetic_threat_generator.py --output data/synthetic/threat_events.parquet --per-class 10000 --seed 42
"""

import argparse
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ============================================================================
# Physics-based parameter profiles per threat class
# ============================================================================

THREAT_PROFILES = {
    "air_uas_small": {
        "description": "Group 1 sUAS / commercial drones (DJI Mavic, Autel, FPV)",
        "sensor_types": ["echodyne_echoguard", "bulzi_zscout", "jcew_drak", "bosch_ptz"],
        "sensor_modalities": ["radar", "rf_passive", "visual"],
        # EchoGuard detection range for 0.01m2 RCS: up to 3km
        "range_m": {"min": 50, "max": 3000, "mean": 800, "std": 500},
        "altitude_m_agl": {"min": 5, "max": 400, "mean": 80, "std": 60},
        # sUAS typical speeds: 0-30 m/s (0-67 mph)
        "velocity_mps": {"min": 0, "max": 30, "mean": 12, "std": 6},
        # RCS for small drones: 0.001 - 0.05 m2
        "rcs_m2": {"min": 0.001, "max": 0.05, "mean": 0.015, "std": 0.01},
        "track_confidence": {"min": 0.55, "max": 0.98, "mean": 0.78, "std": 0.10},
        "track_age_s": {"min": 1, "max": 600, "mean": 45, "std": 80},
        "elevation_deg": {"min": 1, "max": 45, "mean": 8, "std": 6},
        "cot_types": ["a-h-A-M-F-Q", "a-u-A-M-F-Q"],
        # RF emissions from drone control link
        "frequency_mhz": {"min": 900, "max": 5800, "mean": 2437, "std": 800},
        "signal_strength_dbm": {"min": -90, "max": -30, "mean": -62, "std": 12},
    },
    "air_fixed_wing": {
        "description": "Manned fixed-wing aircraft or large Group 3+ UAS",
        "sensor_types": ["echodyne_echoguard", "jcew_drak", "bosch_ptz"],
        "sensor_modalities": ["radar", "visual"],
        # EchoGuard detection range for larger RCS: up to 9km
        "range_m": {"min": 500, "max": 9000, "mean": 4000, "std": 2000},
        "altitude_m_agl": {"min": 100, "max": 5000, "mean": 1500, "std": 1000},
        # Fixed-wing speeds: 30-150 m/s (67-335 mph)
        "velocity_mps": {"min": 30, "max": 150, "mean": 70, "std": 25},
        # RCS for fixed-wing: 1-100 m2
        "rcs_m2": {"min": 1.0, "max": 100.0, "mean": 10.0, "std": 15.0},
        "track_confidence": {"min": 0.70, "max": 0.99, "mean": 0.88, "std": 0.06},
        "track_age_s": {"min": 2, "max": 300, "mean": 60, "std": 50},
        "elevation_deg": {"min": 5, "max": 60, "mean": 20, "std": 12},
        "cot_types": ["a-h-A", "a-u-A"],
        "frequency_mhz": {"min": 0, "max": 0, "mean": 0, "std": 0},
        "signal_strength_dbm": {"min": 0, "max": 0, "mean": 0, "std": 0},
    },
    "ground_vehicle": {
        "description": "Wheeled or tracked ground vehicles",
        "sensor_types": ["echodyne_echoguard", "mcq_ranger", "bosch_ptz", "dft_fiber"],
        "sensor_modalities": ["radar", "seismic", "visual", "acoustic"],
        # EchoGuard detection range for vehicles: up to 9km
        "range_m": {"min": 50, "max": 9000, "mean": 2000, "std": 1500},
        "altitude_m_agl": {"min": 0, "max": 3, "mean": 1.5, "std": 0.5},
        # Vehicle speeds: 0-40 m/s (0-90 mph)
        "velocity_mps": {"min": 0, "max": 40, "mean": 12, "std": 8},
        # RCS for vehicles: 5-100 m2
        "rcs_m2": {"min": 5.0, "max": 100.0, "mean": 20.0, "std": 15.0},
        "track_confidence": {"min": 0.65, "max": 0.99, "mean": 0.82, "std": 0.08},
        "track_age_s": {"min": 2, "max": 1200, "mean": 120, "std": 200},
        "elevation_deg": {"min": -2, "max": 5, "mean": 0.5, "std": 1.0},
        "cot_types": ["a-h-G-E-V", "a-u-G-E-V"],
        "frequency_mhz": {"min": 0, "max": 0, "mean": 0, "std": 0},
        "signal_strength_dbm": {"min": 0, "max": 0, "mean": 0, "std": 0},
    },
    "ground_personnel": {
        "description": "Dismounted personnel / foot patrols",
        "sensor_types": ["echodyne_echoguard", "mcq_ranger", "bosch_ptz", "dft_fiber", "bulzi_zscout"],
        "sensor_modalities": ["radar", "seismic", "visual", "rf_passive", "fiber_optic"],
        # Personnel detection range: EchoGuard up to ~2km for 0.5m2 RCS
        "range_m": {"min": 10, "max": 2000, "mean": 400, "std": 350},
        "altitude_m_agl": {"min": 0, "max": 2, "mean": 1.0, "std": 0.3},
        # Walking/running: 0-8 m/s (0-18 mph)
        "velocity_mps": {"min": 0, "max": 8, "mean": 1.5, "std": 1.2},
        # Personnel RCS: 0.5-1.5 m2
        "rcs_m2": {"min": 0.3, "max": 2.0, "mean": 0.8, "std": 0.3},
        "track_confidence": {"min": 0.40, "max": 0.95, "mean": 0.65, "std": 0.12},
        "track_age_s": {"min": 1, "max": 900, "mean": 60, "std": 120},
        "elevation_deg": {"min": -2, "max": 3, "mean": 0.2, "std": 0.5},
        "cot_types": ["a-h-G", "a-u-G"],
        # Cell phone emissions if carrying
        "frequency_mhz": {"min": 700, "max": 2600, "mean": 1800, "std": 400},
        "signal_strength_dbm": {"min": -100, "max": -50, "mean": -75, "std": 10},
    },
    "benign_wildlife": {
        "description": "Birds (large raptors, geese), deer, coyotes — false positive rejection class",
        "sensor_types": ["echodyne_echoguard", "mcq_ranger", "bosch_ptz"],
        "sensor_modalities": ["radar", "seismic", "visual"],
        "range_m": {"min": 20, "max": 2000, "mean": 300, "std": 300},
        # Birds fly, ground animals are ground-level
        "altitude_m_agl": {"min": 0, "max": 200, "mean": 30, "std": 50},
        # Animals: 0-25 m/s (birds can be fast)
        "velocity_mps": {"min": 0, "max": 25, "mean": 5, "std": 5},
        # Small RCS: birds 0.001-0.01, deer/coyote 0.1-0.5
        "rcs_m2": {"min": 0.001, "max": 0.5, "mean": 0.05, "std": 0.08},
        "track_confidence": {"min": 0.20, "max": 0.75, "mean": 0.45, "std": 0.12},
        "track_age_s": {"min": 1, "max": 120, "mean": 15, "std": 20},
        "elevation_deg": {"min": -2, "max": 30, "mean": 5, "std": 8},
        "cot_types": ["a-u-G", "a-u-A"],
        "frequency_mhz": {"min": 0, "max": 0, "mean": 0, "std": 0},
        "signal_strength_dbm": {"min": 0, "max": 0, "mean": 0, "std": 0},
    },
    "benign_aircraft": {
        "description": "Commercial / authorized military aircraft — false positive rejection class",
        "sensor_types": ["echodyne_echoguard", "bosch_ptz"],
        "sensor_modalities": ["radar", "visual"],
        # Typically higher altitude, longer range
        "range_m": {"min": 2000, "max": 9000, "mean": 6000, "std": 1500},
        "altitude_m_agl": {"min": 1000, "max": 12000, "mean": 5000, "std": 2500},
        # Airliners / transport: 80-260 m/s
        "velocity_mps": {"min": 80, "max": 260, "mean": 150, "std": 40},
        # Large RCS
        "rcs_m2": {"min": 10, "max": 500, "mean": 50, "std": 80},
        "track_confidence": {"min": 0.80, "max": 0.99, "mean": 0.92, "std": 0.04},
        "track_age_s": {"min": 5, "max": 600, "mean": 120, "std": 100},
        "elevation_deg": {"min": 10, "max": 80, "mean": 35, "std": 15},
        "cot_types": ["a-f-A", "a-n-A"],
        "frequency_mhz": {"min": 0, "max": 0, "mean": 0, "std": 0},
        "signal_strength_dbm": {"min": 0, "max": 0, "mean": 0, "std": 0},
    },
}

# Sensor ID pools per sensor type
SENSOR_IDS = {
    "echodyne_echoguard": ["ECHODYNE-01", "ECHODYNE-02"],
    "mcq_ranger": ["MCQ-RANGER-NORTH", "MCQ-RANGER-SOUTH", "MCQ-RANGER-EAST", "MCQ-RANGER-WEST"],
    "bosch_ptz": ["BOSCH-PTZ-01", "BOSCH-PTZ-02", "BOSCH-PTZ-03"],
    "bulzi_zscout": ["BULZI-ZSCOUT-01"],
    "dft_fiber": ["DFT-PERIMETER-NORTH", "DFT-PERIMETER-SOUTH", "DFT-PERIMETER-EAST", "DFT-PERIMETER-WEST"],
    "jcew_drak": ["JCEW-DRAK-01"],
    "weartak": ["WEARTAK-ALPHA-1", "WEARTAK-BRAVO-1"],
    "spotd": ["SPOTD-TEAL-01"],
    "synthetic": ["SYNTH-GEN-01"],
}

DETECTION_ZONES = [
    "NORTH-PERIMETER", "SOUTH-PERIMETER", "EAST-PERIMETER", "WEST-PERIMETER",
    "GATE-1", "GATE-2", "AIRFIELD-APPROACH", "ASP-SECTOR",
    "TOWER-OVERWATCH", "HQ-COMPOUND", "MOTOR-POOL", "COMMS-FACILITY",
]

# AOI center: Andersen AFB, Guam (from RACK config)
AOI_CENTER_LAT = 13.5839
AOI_CENTER_LON = 144.9247
AOI_RADIUS_KM = 5.5


def _gaussian_clamp(rng: np.random.Generator, profile: dict, noise_sigma_pct: float = 0.075) -> float:
    """Sample from a Gaussian distribution, clamp to [min, max], and add noise."""
    value = rng.normal(profile["mean"], profile["std"])
    value = np.clip(value, profile["min"], profile["max"])
    # Add Gaussian noise (5-10% sigma)
    noise = rng.normal(0, abs(value) * noise_sigma_pct) if value != 0 else 0
    value += noise
    return float(np.clip(value, profile["min"], profile["max"]))


def _random_lat_lon(rng: np.random.Generator, range_m: float) -> tuple[float, float]:
    """Generate a random lat/lon within range_m of the AOI center."""
    # Random bearing and distance
    bearing = rng.uniform(0, 360)
    distance_km = min(range_m / 1000.0, AOI_RADIUS_KM) * rng.uniform(0.1, 1.0)

    bearing_rad = math.radians(bearing)
    lat = AOI_CENTER_LAT + (distance_km * math.cos(bearing_rad)) / 111.32
    lon = AOI_CENTER_LON + (distance_km * math.sin(bearing_rad)) / (
        111.32 * math.cos(math.radians(AOI_CENTER_LAT))
    )
    return round(lat, 6), round(lon, 6)


def generate_threat_event(
    rng: np.random.Generator,
    threat_class: str,
    base_time: datetime,
    noise_sigma_pct: float = 0.075,
) -> dict:
    """Generate a single physics-based ThreatEvent."""
    profile = THREAT_PROFILES[threat_class]

    # Sample sensor type
    sensor_type = rng.choice(profile["sensor_types"])
    sensor_id = rng.choice(SENSOR_IDS.get(sensor_type, ["UNKNOWN-01"]))
    sensor_modality = rng.choice(profile["sensor_modalities"])

    # Sample physics parameters with noise
    range_m = _gaussian_clamp(rng, profile["range_m"], noise_sigma_pct)
    altitude = _gaussian_clamp(rng, profile["altitude_m_agl"], noise_sigma_pct)
    velocity = _gaussian_clamp(rng, profile["velocity_mps"], noise_sigma_pct)
    rcs = _gaussian_clamp(rng, profile["rcs_m2"], noise_sigma_pct)
    confidence = _gaussian_clamp(rng, profile["track_confidence"], noise_sigma_pct)
    track_age = max(0, _gaussian_clamp(rng, profile["track_age_s"], noise_sigma_pct))
    elevation = _gaussian_clamp(rng, profile["elevation_deg"], noise_sigma_pct)

    bearing = float(rng.uniform(0, 360))
    heading = float(rng.uniform(0, 360))

    lat, lon = _random_lat_lon(rng, range_m)

    # Timestamp: random offset from base_time (within 24-hour window)
    offset_s = rng.uniform(0, 86400)
    timestamp = base_time + timedelta(seconds=offset_s)

    # RF params (only for RF-capable sensors and threat classes)
    freq_mhz = 0.0
    signal_dbm = None
    if profile["frequency_mhz"]["mean"] > 0 and sensor_type in ("bulzi_zscout", "jcew_drak"):
        freq_mhz = _gaussian_clamp(rng, profile["frequency_mhz"], noise_sigma_pct)
        signal_dbm = _gaussian_clamp(rng, profile["signal_strength_dbm"], noise_sigma_pct)

    # Non-radar sensors report RCS as 0
    if sensor_type not in ("echodyne_echoguard",):
        rcs = 0.0

    cot_type = rng.choice(profile["cot_types"])
    zone = rng.choice(DETECTION_ZONES)

    event = {
        "event_id": str(uuid.uuid4()),
        "sensor_id": sensor_id,
        "sensor_type": sensor_type,
        "track_id": f"TRK-{rng.integers(10000, 99999)}",
        "bearing_deg": round(bearing, 2),
        "range_m": round(range_m, 1),
        "altitude_m_agl": round(altitude, 1),
        "velocity_mps": round(velocity, 2),
        "heading_deg": round(heading, 2),
        "radar_cross_section_m2": round(rcs, 4),
        "track_age_s": round(track_age, 1),
        "track_confidence_0_1": round(np.clip(confidence, 0, 1), 3),
        "timestamp_utc": timestamp.isoformat(),
        "raw_payload": {
            "generator": "synthetic_threat_generator_v1",
            "profile": threat_class,
            "noise_sigma_pct": noise_sigma_pct,
        },
        "threat_class": threat_class,
        "threat_score": round(
            float(np.clip(confidence * (0.9 if "benign" not in threat_class else 0.15), 0, 1)),
            3,
        ),
        "lat": lat,
        "lon": lon,
        "elevation_deg": round(elevation, 2),
        "cot_type": cot_type,
        "sensor_modality": sensor_modality,
        "detection_zone": zone,
        "frequency_mhz": round(freq_mhz, 2) if freq_mhz > 0 else 0.0,
        "signal_strength_dbm": round(signal_dbm, 1) if signal_dbm is not None else None,
    }

    return event


def generate_dataset(
    per_class: int = 5000,
    seed: int = 42,
    noise_sigma_pct: float = 0.075,
    base_time: datetime | None = None,
) -> pd.DataFrame:
    """Generate a full labeled dataset across all threat classes.

    Args:
        per_class: Number of events per threat class (minimum 5000 per spec).
        seed: Random seed for reproducibility.
        noise_sigma_pct: Gaussian noise sigma as fraction (0.05 = 5%, 0.10 = 10%).
        base_time: Base timestamp for event generation. Defaults to now.

    Returns:
        DataFrame with all generated events.
    """
    rng = np.random.default_rng(seed)
    if base_time is None:
        base_time = datetime.now(timezone.utc)

    all_events = []
    for threat_class in THREAT_PROFILES:
        print(f"  Generating {per_class:,} events for {threat_class}...")
        for _ in range(per_class):
            event = generate_threat_event(rng, threat_class, base_time, noise_sigma_pct)
            all_events.append(event)

    df = pd.DataFrame(all_events)

    # Shuffle to prevent ordering bias during training
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    return df


def validate_dataset(df: pd.DataFrame, min_per_class: int = 5000) -> dict:
    """Validate generated dataset against schema constraints and physics bounds."""
    issues = []

    # Check class balance
    class_counts = df["threat_class"].value_counts()
    for cls, count in class_counts.items():
        if count < min_per_class:
            issues.append(f"Class {cls} has only {count} events (minimum {min_per_class})")

    # Physics bounds checks
    if (df["bearing_deg"] < 0).any() or (df["bearing_deg"] > 360).any():
        issues.append("bearing_deg out of [0, 360] range")
    if (df["range_m"] < 0).any():
        issues.append("Negative range_m values found")
    if (df["track_confidence_0_1"] < 0).any() or (df["track_confidence_0_1"] > 1).any():
        issues.append("track_confidence_0_1 out of [0, 1] range")
    if (df["velocity_mps"] < 0).any():
        issues.append("Negative velocity_mps values found")

    # Check for null required fields
    required = [
        "event_id", "sensor_id", "sensor_type", "track_id", "bearing_deg",
        "range_m", "altitude_m_agl", "velocity_mps", "heading_deg",
        "radar_cross_section_m2", "track_age_s", "track_confidence_0_1",
        "timestamp_utc", "threat_class",
    ]
    for col in required:
        nulls = df[col].isna().sum()
        if nulls > 0:
            issues.append(f"Required field '{col}' has {nulls} null values")

    # RCS sanity: radar sensors should have nonzero RCS for threat classes
    radar_threats = df[
        (df["sensor_type"] == "echodyne_echoguard") &
        (~df["threat_class"].str.startswith("benign"))
    ]
    zero_rcs = (radar_threats["radar_cross_section_m2"] == 0).sum()
    if zero_rcs > 0:
        issues.append(f"{zero_rcs} radar-detected threats have zero RCS")

    stats = {
        "total_events": len(df),
        "classes": class_counts.to_dict(),
        "sensor_types": df["sensor_type"].value_counts().to_dict(),
        "issues": issues,
        "valid": len(issues) == 0,
    }

    return stats


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic ThreatEvent training data")
    parser.add_argument(
        "--output", "-o",
        default="data/synthetic/threat_events.parquet",
        help="Output file path (Parquet format)",
    )
    parser.add_argument(
        "--per-class", "-n",
        type=int,
        default=5000,
        help="Number of events per threat class (default: 5000)",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--noise",
        type=float,
        default=0.075,
        help="Gaussian noise sigma as fraction (default: 0.075 = 7.5%%)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate an existing dataset (requires --output to point to existing file)",
    )
    parser.add_argument(
        "--json-export",
        action="store_true",
        help="Also export as JSONL alongside Parquet",
    )

    args = parser.parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.validate_only:
        print(f"Validating existing dataset: {output_path}")
        df = pd.read_parquet(output_path)
        stats = validate_dataset(df)
        print(json.dumps(stats, indent=2))
        return

    print(f"RACK FP Synthetic ThreatEvent Generator")
    print(f"========================================")
    print(f"  Events per class: {args.per_class:,}")
    print(f"  Total events:     {args.per_class * len(THREAT_PROFILES):,}")
    print(f"  Threat classes:   {len(THREAT_PROFILES)}")
    print(f"  Noise sigma:      {args.noise * 100:.1f}%")
    print(f"  Seed:             {args.seed}")
    print(f"  Output:           {output_path}")
    print()

    df = generate_dataset(
        per_class=args.per_class,
        seed=args.seed,
        noise_sigma_pct=args.noise,
    )

    # Validate
    print("\nValidating dataset...")
    stats = validate_dataset(df)

    if not stats["valid"]:
        print("VALIDATION ISSUES:")
        for issue in stats["issues"]:
            print(f"  - {issue}")
    else:
        print("  All validations passed.")

    # Save Parquet
    df.to_parquet(output_path, index=False, engine="pyarrow")
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nParquet saved: {output_path} ({file_size_mb:.1f} MB)")

    # Optional JSONL export
    if args.json_export:
        jsonl_path = output_path.with_suffix(".jsonl")
        df.to_json(jsonl_path, orient="records", lines=True)
        jsonl_size_mb = jsonl_path.stat().st_size / (1024 * 1024)
        print(f"JSONL saved:   {jsonl_path} ({jsonl_size_mb:.1f} MB)")

    # Summary
    print(f"\nDataset Summary:")
    print(f"  Total events:    {stats['total_events']:,}")
    print(f"  Class distribution:")
    for cls, count in sorted(stats["classes"].items()):
        print(f"    {cls:25s} {count:>6,}")
    print(f"  Sensor distribution:")
    for sensor, count in sorted(stats["sensor_types"].items()):
        print(f"    {sensor:25s} {count:>6,}")


if __name__ == "__main__":
    main()
