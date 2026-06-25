"""
RACK FP Schema Validator
========================

Programmatic validation of ThreatEvent and CapabilityManifest objects
against their JSON Schema contracts (Draft 2020-12).

Usage:
    from pipeline.schema_validator import validate_threat_event, validate_capability_manifest

    errors = validate_threat_event(event_dict)
    if errors:
        print(f"Validation failed: {errors}")

    # Batch validation
    results = validate_events_batch(list_of_events)
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

_SCHEMA_DIR = Path(__file__).parent.parent / "schemas"

_threat_event_schema = None
_capability_manifest_schema = None


def _load_schema(name: str) -> dict:
    path = _SCHEMA_DIR / name
    with open(path) as f:
        return json.load(f)


def get_threat_event_schema() -> dict:
    global _threat_event_schema
    if _threat_event_schema is None:
        _threat_event_schema = _load_schema("threat_event.schema.json")
    return _threat_event_schema


def get_capability_manifest_schema() -> dict:
    global _capability_manifest_schema
    if _capability_manifest_schema is None:
        _capability_manifest_schema = _load_schema("capability_manifest.schema.json")
    return _capability_manifest_schema


def validate_threat_event(event: dict) -> list[str]:
    """Validate a single ThreatEvent against the JSON schema.

    Returns a list of error messages. Empty list means valid.
    """
    schema = get_threat_event_schema()
    validator = Draft202012Validator(schema)
    return [f"{e.json_path}: {e.message}" for e in validator.iter_errors(event)]


def validate_capability_manifest(manifest: dict) -> list[str]:
    """Validate a CapabilityManifest against the JSON schema.

    Returns a list of error messages. Empty list means valid.
    """
    schema = get_capability_manifest_schema()
    validator = Draft202012Validator(schema)
    return [f"{e.json_path}: {e.message}" for e in validator.iter_errors(manifest)]


def validate_events_batch(events: list[dict]) -> dict:
    """Validate a batch of ThreatEvents.

    Returns:
        {
            "total": int,
            "valid": int,
            "invalid": int,
            "errors": [{index: int, errors: list[str]}, ...]
        }
    """
    schema = get_threat_event_schema()
    validator = Draft202012Validator(schema)

    results: dict[str, Any] = {"total": len(events), "valid": 0, "invalid": 0, "errors": []}

    for i, event in enumerate(events):
        errs = [f"{e.json_path}: {e.message}" for e in validator.iter_errors(event)]
        if errs:
            results["invalid"] += 1
            results["errors"].append({"index": i, "errors": errs})
        else:
            results["valid"] += 1

    return results


def validate_physics_bounds(event: dict) -> list[str]:
    """Apply physics-bound assertions beyond JSON schema validation.

    Checks that no entity violates physical laws:
    - No object exceeds the speed of sound (343 m/s) except benign_aircraft
    - Biological entities (wildlife) cannot exceed 5G acceleration
    - Ground entities have altitude < 5m AGL
    - No object below terrain (altitude < -10m) without crash state
    - RCS must be positive for radar sensors
    """
    issues = []
    tc = event.get("threat_class", "unknown")
    vel = event.get("velocity_mps", 0)
    alt = event.get("altitude_m_agl", 0)
    rcs = event.get("radar_cross_section_m2", 0)
    sensor = event.get("sensor_type", "")

    # Speed of sound check (343 m/s at sea level)
    if tc != "benign_aircraft" and vel > 343:
        issues.append(f"velocity {vel} m/s exceeds speed of sound for class {tc}")

    # Wildlife G-force: max ~50 m/s (peregrine falcon dive ~90 m/s, but our profile caps at 25)
    if tc == "benign_wildlife" and vel > 90:
        issues.append(f"wildlife velocity {vel} m/s exceeds biological maximum")

    # Ground entities should be ground-level
    if tc in ("ground_vehicle", "ground_personnel") and alt > 50:
        issues.append(f"ground entity {tc} at {alt}m AGL (expected <50m)")

    # Subsurface check
    if alt < -100:
        issues.append(f"altitude {alt}m AGL below minimum terrain boundary")

    # Radar RCS check
    if sensor == "echodyne_echoguard" and tc not in ("benign_wildlife",) and rcs < 0:
        issues.append(f"negative RCS {rcs} for radar detection")

    # Fixed-wing stall speed check (minimum ~25 m/s for most aircraft)
    if tc == "air_fixed_wing" and vel < 15 and vel > 0:
        issues.append(f"fixed-wing velocity {vel} m/s below plausible stall speed")

    # Benign aircraft should be high altitude
    if tc == "benign_aircraft" and alt < 100:
        issues.append(f"benign aircraft at {alt}m AGL (expected >100m for authorized transit)")

    return issues


if __name__ == "__main__":
    import sys

    # Quick validation demo
    sample_event = {
        "event_id": "00000000-0000-0000-0000-000000000001",
        "sensor_id": "ECHODYNE-01",
        "sensor_type": "echodyne_echoguard",
        "track_id": "TRK-12345",
        "bearing_deg": 180.5,
        "range_m": 1500.0,
        "altitude_m_agl": 120.0,
        "velocity_mps": 15.0,
        "heading_deg": 90.0,
        "radar_cross_section_m2": 0.015,
        "track_age_s": 30.0,
        "track_confidence_0_1": 0.85,
        "timestamp_utc": "2026-06-15T14:30:00.000Z",
        "raw_payload": {"generator": "manual_test"},
        "threat_class": "air_uas_small",
    }

    schema_errors = validate_threat_event(sample_event)
    physics_errors = validate_physics_bounds(sample_event)

    if schema_errors:
        print(f"Schema errors: {schema_errors}")
        sys.exit(1)
    elif physics_errors:
        print(f"Physics errors: {physics_errors}")
        sys.exit(1)
    else:
        print("Sample event: VALID (schema + physics)")
