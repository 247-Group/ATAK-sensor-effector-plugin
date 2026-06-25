"""
Tests for the schema validation module.

Validates:
  - ThreatEvent schema validation (valid + invalid events)
  - CapabilityManifest schema validation
  - Batch validation
  - Physics bounds validation
"""

import uuid
from datetime import datetime, timezone

import pytest

from pipeline.schema_validator import (
    validate_capability_manifest,
    validate_events_batch,
    validate_physics_bounds,
    validate_threat_event,
)


def _make_valid_event(**overrides):
    """Create a minimal valid ThreatEvent."""
    event = {
        "event_id": str(uuid.uuid4()),
        "sensor_id": "ECHODYNE-01",
        "sensor_type": "echodyne_echoguard",
        "track_id": "TRK-12345",
        "bearing_deg": 180.0,
        "range_m": 1500.0,
        "altitude_m_agl": 120.0,
        "velocity_mps": 15.0,
        "heading_deg": 90.0,
        "radar_cross_section_m2": 0.015,
        "track_age_s": 30.0,
        "track_confidence_0_1": 0.85,
        "timestamp_utc": "2026-06-15T14:30:00.000Z",
        "raw_payload": {"generator": "test"},
    }
    event.update(overrides)
    return event


class TestThreatEventValidation:
    def test_valid_event_passes(self):
        event = _make_valid_event()
        errors = validate_threat_event(event)
        assert not errors, f"Valid event failed: {errors}"

    def test_missing_required_field(self):
        event = _make_valid_event()
        del event["sensor_id"]
        errors = validate_threat_event(event)
        assert any("sensor_id" in e for e in errors)

    def test_invalid_sensor_type(self):
        event = _make_valid_event(sensor_type="invalid_sensor")
        errors = validate_threat_event(event)
        assert errors

    def test_bearing_out_of_range(self):
        event = _make_valid_event(bearing_deg=400)
        errors = validate_threat_event(event)
        assert errors

    def test_negative_range(self):
        event = _make_valid_event(range_m=-100)
        errors = validate_threat_event(event)
        assert errors

    def test_confidence_above_one(self):
        event = _make_valid_event(track_confidence_0_1=1.5)
        errors = validate_threat_event(event)
        assert errors

    def test_valid_threat_class(self):
        event = _make_valid_event(threat_class="air_uas_small")
        errors = validate_threat_event(event)
        assert not errors

    def test_invalid_threat_class(self):
        event = _make_valid_event(threat_class="spaceship")
        errors = validate_threat_event(event)
        assert errors

    def test_additional_properties_rejected(self):
        event = _make_valid_event(made_up_field="bad")
        errors = validate_threat_event(event)
        assert errors


class TestCapabilityManifestValidation:
    def test_valid_manifest(self):
        manifest = {
            "plugin_id": "com.aicowboys.rack.fp",
            "display_name": "RACK Force Protection AI",
            "available_actions": [
                {
                    "action_id": "issue_fp_alert",
                    "action_label": "Issue FP Alert",
                    "applicable_threat_classes": ["*"],
                }
            ],
            "current_status": "online",
        }
        errors = validate_capability_manifest(manifest)
        assert not errors, f"Valid manifest failed: {errors}"

    def test_missing_plugin_id(self):
        manifest = {
            "display_name": "Test",
            "available_actions": [],
            "current_status": "online",
        }
        errors = validate_capability_manifest(manifest)
        assert any("plugin_id" in e for e in errors)

    def test_invalid_status(self):
        manifest = {
            "plugin_id": "com.test",
            "display_name": "Test",
            "available_actions": [],
            "current_status": "broken",
        }
        errors = validate_capability_manifest(manifest)
        assert errors

    def test_action_with_human_gate(self):
        manifest = {
            "plugin_id": "com.aicowboys.rack.fp",
            "display_name": "RACK FP",
            "available_actions": [
                {
                    "action_id": "escalate_fpcon",
                    "action_label": "Escalate FPCON",
                    "applicable_threat_classes": ["*"],
                    "requires_human_gate": True,
                    "max_response_time_s": 30,
                }
            ],
            "current_status": "online",
        }
        errors = validate_capability_manifest(manifest)
        assert not errors


class TestBatchValidation:
    def test_all_valid(self):
        events = [_make_valid_event() for _ in range(10)]
        result = validate_events_batch(events)
        assert result["valid"] == 10
        assert result["invalid"] == 0

    def test_mixed_valid_invalid(self):
        events = [
            _make_valid_event(),
            _make_valid_event(bearing_deg=999),  # invalid
            _make_valid_event(),
        ]
        result = validate_events_batch(events)
        assert result["valid"] == 2
        assert result["invalid"] == 1
        assert result["errors"][0]["index"] == 1


class TestPhysicsBounds:
    def test_valid_uas(self):
        event = _make_valid_event(
            threat_class="air_uas_small",
            velocity_mps=15,
            altitude_m_agl=100,
        )
        issues = validate_physics_bounds(event)
        assert not issues

    def test_supersonic_uas_fails(self):
        event = _make_valid_event(
            threat_class="air_uas_small",
            velocity_mps=400,
        )
        issues = validate_physics_bounds(event)
        assert any("speed of sound" in i for i in issues)

    def test_wildlife_hypersonic_fails(self):
        event = _make_valid_event(
            threat_class="benign_wildlife",
            velocity_mps=100,
        )
        issues = validate_physics_bounds(event)
        assert any("biological maximum" in i for i in issues)

    def test_ground_vehicle_airborne_fails(self):
        event = _make_valid_event(
            threat_class="ground_vehicle",
            altitude_m_agl=200,
        )
        issues = validate_physics_bounds(event)
        assert any("ground entity" in i for i in issues)

    def test_subsurface_fails(self):
        event = _make_valid_event(altitude_m_agl=-200)
        issues = validate_physics_bounds(event)
        assert any("terrain boundary" in i for i in issues)

    def test_benign_aircraft_valid(self):
        event = _make_valid_event(
            threat_class="benign_aircraft",
            velocity_mps=250,
            altitude_m_agl=5000,
        )
        issues = validate_physics_bounds(event)
        assert not issues
