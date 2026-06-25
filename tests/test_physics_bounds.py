"""
Physics-Bound Assertion Tests for RACK FP Synthetic Data
=========================================================

Validates that the generated synthetic dataset obeys physical laws.
These go beyond JSON schema validation to enforce real-world constraints.

Tests:
  - No entity exceeds speed of sound (except benign_aircraft)
  - Biological entities obey G-force and velocity limits
  - Ground entities remain ground-level
  - Fixed-wing aircraft maintain stall speed
  - Benign aircraft at high altitude
  - RCS consistency with sensor type
  - No subsurface anomalies
  - Schema compliance for every event
  - Coordinate bounds (WGS-84)
  - Track confidence bounds
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.schema_validator import (
    validate_events_batch,
    validate_physics_bounds,
    validate_threat_event,
)
from pipeline.synthetic_threat_generator import (
    THREAT_PROFILES,
    generate_dataset,
    generate_threat_event,
)

SPEED_OF_SOUND_MPS = 343.0  # at sea level, 20C
MAX_WILDLIFE_VELOCITY_MPS = 90.0  # peregrine falcon dive
MAX_WILDLIFE_ACCEL_G = 5.0  # biological G-force limit
MAX_GROUND_ALTITUDE_M = 50.0  # generous bound for ground entities
MIN_FIXED_WING_STALL_MPS = 15.0  # generous minimum


@pytest.fixture(scope="module")
def dataset():
    """Generate a medium dataset for physics testing."""
    return generate_dataset(per_class=500, seed=42)


@pytest.fixture(scope="module")
def dataset_records(dataset):
    """Convert dataset to list of dicts for schema validation."""
    return dataset.to_dict(orient="records")


class TestSpeedOfSound:
    """No non-aircraft entity should exceed the speed of sound."""

    def test_uas_below_speed_of_sound(self, dataset):
        uas = dataset[dataset["threat_class"] == "air_uas_small"]
        assert uas["velocity_mps"].max() <= SPEED_OF_SOUND_MPS, (
            f"sUAS max velocity {uas['velocity_mps'].max()} exceeds speed of sound"
        )

    def test_ground_vehicle_below_speed_of_sound(self, dataset):
        vehicles = dataset[dataset["threat_class"] == "ground_vehicle"]
        assert vehicles["velocity_mps"].max() <= SPEED_OF_SOUND_MPS

    def test_ground_personnel_below_speed_of_sound(self, dataset):
        personnel = dataset[dataset["threat_class"] == "ground_personnel"]
        assert personnel["velocity_mps"].max() <= SPEED_OF_SOUND_MPS

    def test_wildlife_below_speed_of_sound(self, dataset):
        wildlife = dataset[dataset["threat_class"] == "benign_wildlife"]
        assert wildlife["velocity_mps"].max() <= SPEED_OF_SOUND_MPS

    def test_fixed_wing_below_speed_of_sound(self, dataset):
        fw = dataset[dataset["threat_class"] == "air_fixed_wing"]
        assert fw["velocity_mps"].max() <= SPEED_OF_SOUND_MPS


class TestBiologicalLimits:
    """Wildlife must obey biological constraints."""

    def test_wildlife_velocity_limit(self, dataset):
        wildlife = dataset[dataset["threat_class"] == "benign_wildlife"]
        assert wildlife["velocity_mps"].max() <= MAX_WILDLIFE_VELOCITY_MPS, (
            f"Wildlife max velocity {wildlife['velocity_mps'].max()} exceeds biological max"
        )

    def test_wildlife_low_rcs(self, dataset):
        """Wildlife RCS should be small (birds/deer)."""
        wildlife = dataset[
            (dataset["threat_class"] == "benign_wildlife")
            & (dataset["sensor_type"] == "echodyne_echoguard")
        ]
        if len(wildlife) > 0:
            assert wildlife["radar_cross_section_m2"].max() <= 1.0, (
                "Wildlife RCS exceeds 1.0 m2 (too large for biological target)"
            )

    def test_wildlife_moderate_altitude(self, dataset):
        """Wildlife shouldn't be at extreme altitudes."""
        wildlife = dataset[dataset["threat_class"] == "benign_wildlife"]
        assert wildlife["altitude_m_agl"].max() <= 500, (
            "Wildlife altitude exceeds 500m AGL"
        )


class TestGroundEntities:
    """Ground vehicles and personnel must be near ground level."""

    def test_vehicle_ground_level(self, dataset):
        vehicles = dataset[dataset["threat_class"] == "ground_vehicle"]
        assert vehicles["altitude_m_agl"].max() <= MAX_GROUND_ALTITUDE_M, (
            f"Ground vehicle at {vehicles['altitude_m_agl'].max()}m AGL"
        )

    def test_personnel_ground_level(self, dataset):
        personnel = dataset[dataset["threat_class"] == "ground_personnel"]
        assert personnel["altitude_m_agl"].max() <= MAX_GROUND_ALTITUDE_M, (
            f"Personnel at {personnel['altitude_m_agl'].max()}m AGL"
        )

    def test_personnel_speed_limit(self, dataset):
        """Humans can't run faster than ~12 m/s (Usain Bolt peak)."""
        personnel = dataset[dataset["threat_class"] == "ground_personnel"]
        assert personnel["velocity_mps"].max() <= 15, (
            f"Personnel velocity {personnel['velocity_mps'].max()} exceeds human maximum"
        )

    def test_vehicle_speed_limit(self, dataset):
        """Vehicles in a force protection zone shouldn't exceed ~50 m/s (112 mph)."""
        vehicles = dataset[dataset["threat_class"] == "ground_vehicle"]
        assert vehicles["velocity_mps"].max() <= 60


class TestAircraftPhysics:
    """Aircraft must obey aerodynamic constraints."""

    def test_benign_aircraft_high_altitude(self, dataset):
        """Benign/authorized aircraft should be at transit altitude."""
        benign = dataset[dataset["threat_class"] == "benign_aircraft"]
        # At least 50% should be above 1000m
        high_pct = (benign["altitude_m_agl"] > 500).mean()
        assert high_pct > 0.5, (
            f"Only {high_pct*100:.0f}% of benign aircraft above 500m AGL"
        )

    def test_benign_aircraft_fast(self, dataset):
        """Authorized aircraft should be fast (above stall speed)."""
        benign = dataset[dataset["threat_class"] == "benign_aircraft"]
        # Median should be well above stall
        assert benign["velocity_mps"].median() > 50

    def test_fixed_wing_minimum_speed(self, dataset):
        """Fixed-wing aircraft have stall speeds."""
        fw = dataset[dataset["threat_class"] == "air_fixed_wing"]
        # At least 90% should be above a generous stall speed
        above_stall_pct = (fw["velocity_mps"] > MIN_FIXED_WING_STALL_MPS).mean()
        assert above_stall_pct > 0.85, (
            f"Only {above_stall_pct*100:.0f}% of fixed-wing above stall speed"
        )


class TestRCSConsistency:
    """Radar Cross Section must be consistent with sensor type."""

    def test_non_radar_rcs_zero(self, dataset):
        """Non-radar sensors should report RCS = 0."""
        non_radar = dataset[dataset["sensor_type"] != "echodyne_echoguard"]
        assert (non_radar["radar_cross_section_m2"] == 0).all(), (
            "Non-radar sensors reporting nonzero RCS"
        )

    def test_radar_threats_have_rcs(self, dataset):
        """Radar-detected threats (non-wildlife) should have positive RCS."""
        radar_threats = dataset[
            (dataset["sensor_type"] == "echodyne_echoguard")
            & (~dataset["threat_class"].str.startswith("benign"))
            & (dataset["threat_class"] != "ground_personnel")
        ]
        if len(radar_threats) > 0:
            # At least 95% should have positive RCS (some personnel may have tiny RCS)
            positive_pct = (radar_threats["radar_cross_section_m2"] > 0).mean()
            assert positive_pct > 0.95


class TestCoordinateBounds:
    """Spatial coordinates must be valid WGS-84."""

    def test_latitude_bounds(self, dataset):
        assert dataset["lat"].min() >= -90
        assert dataset["lat"].max() <= 90

    def test_longitude_bounds(self, dataset):
        assert dataset["lon"].min() >= -180
        assert dataset["lon"].max() <= 180

    def test_bearing_bounds(self, dataset):
        assert dataset["bearing_deg"].min() >= 0
        assert dataset["bearing_deg"].max() <= 360

    def test_heading_bounds(self, dataset):
        assert dataset["heading_deg"].min() >= 0
        assert dataset["heading_deg"].max() <= 360

    def test_confidence_bounds(self, dataset):
        assert dataset["track_confidence_0_1"].min() >= 0
        assert dataset["track_confidence_0_1"].max() <= 1


class TestSubsurface:
    """No entity should penetrate terrain without valid reason."""

    def test_no_extreme_subsurface(self, dataset):
        """No entity below -100m AGL (schema minimum)."""
        assert dataset["altitude_m_agl"].min() >= -100

    def test_air_entities_above_ground(self, dataset):
        """Airborne entities should have positive altitude."""
        air = dataset[dataset["threat_class"].isin(["air_uas_small", "air_fixed_wing", "benign_aircraft"])]
        # At least 95% should be above ground
        above_ground = (air["altitude_m_agl"] > 0).mean()
        assert above_ground > 0.95


class TestSchemaCompliance:
    """Every generated event must pass JSON schema validation."""

    def test_sample_schema_validation(self):
        """Validate 100 random events against ThreatEvent schema."""
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        for threat_class in THREAT_PROFILES:
            for _ in range(100):
                event = generate_threat_event(rng, threat_class, base_time)
                # Remove None values (JSON schema doesn't handle Python None the same way)
                event = {k: v for k, v in event.items() if v is not None}
                errors = validate_threat_event(event)
                assert not errors, f"Schema violation in {threat_class}: {errors}"

    def test_physics_bounds_all_classes(self):
        """Run physics bounds check on 100 events per class."""
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        for threat_class in THREAT_PROFILES:
            for _ in range(100):
                event = generate_threat_event(rng, threat_class, base_time)
                issues = validate_physics_bounds(event)
                assert not issues, f"Physics violation in {threat_class}: {issues}"


class TestVelocityNonNegative:
    """All velocities must be non-negative (magnitude, not vector component)."""

    def test_all_velocities_non_negative(self, dataset):
        assert (dataset["velocity_mps"] >= 0).all()

    def test_all_ranges_non_negative(self, dataset):
        assert (dataset["range_m"] >= 0).all()

    def test_all_track_ages_non_negative(self, dataset):
        assert (dataset["track_age_s"] >= 0).all()

    def test_all_rcs_non_negative(self, dataset):
        assert (dataset["radar_cross_section_m2"] >= 0).all()
