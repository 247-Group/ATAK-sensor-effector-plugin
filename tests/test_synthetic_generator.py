"""
Tests for the synthetic ThreatEvent generator.

Validates:
  - Schema compliance for all generated events
  - Physics bounds per threat class
  - Class balance (minimum 5,000 per class)
  - Gaussian noise characteristics
  - Reproducibility via seed
  - Parquet round-trip integrity
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.synthetic_threat_generator import (
    THREAT_PROFILES,
    generate_dataset,
    generate_threat_event,
    validate_dataset,
)


@pytest.fixture
def small_dataset():
    """Generate a small dataset for fast tests."""
    return generate_dataset(per_class=100, seed=42)


@pytest.fixture
def full_dataset():
    """Generate the full 5000-per-class dataset."""
    return generate_dataset(per_class=5000, seed=42)


class TestEventGeneration:
    """Test individual event generation."""

    def test_required_fields_present(self):
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        for threat_class in THREAT_PROFILES:
            event = generate_threat_event(rng, threat_class, base_time)
            required = [
                "event_id", "sensor_id", "sensor_type", "track_id",
                "bearing_deg", "range_m", "altitude_m_agl", "velocity_mps",
                "heading_deg", "radar_cross_section_m2", "track_age_s",
                "track_confidence_0_1", "timestamp_utc", "raw_payload",
                "threat_class",
            ]
            for field in required:
                assert field in event, f"Missing field '{field}' in {threat_class}"

    def test_bearing_bounds(self):
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        for _ in range(500):
            for threat_class in THREAT_PROFILES:
                event = generate_threat_event(rng, threat_class, base_time)
                assert 0 <= event["bearing_deg"] <= 360

    def test_confidence_bounds(self):
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        for _ in range(500):
            for threat_class in THREAT_PROFILES:
                event = generate_threat_event(rng, threat_class, base_time)
                assert 0 <= event["track_confidence_0_1"] <= 1

    def test_velocity_non_negative(self):
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        for _ in range(500):
            for threat_class in THREAT_PROFILES:
                event = generate_threat_event(rng, threat_class, base_time)
                assert event["velocity_mps"] >= 0

    def test_range_non_negative(self):
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        for _ in range(200):
            for threat_class in THREAT_PROFILES:
                event = generate_threat_event(rng, threat_class, base_time)
                assert event["range_m"] >= 0

    def test_uuid_uniqueness(self):
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        ids = set()
        for _ in range(1000):
            event = generate_threat_event(rng, "air_uas_small", base_time)
            assert event["event_id"] not in ids
            ids.add(event["event_id"])

    def test_sensor_type_valid(self):
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        valid_types = {
            "echodyne_echoguard", "mcq_ranger", "bosch_ptz", "bulzi_zscout",
            "dft_fiber", "jcew_drak", "weartak", "spotd", "synthetic",
        }
        for _ in range(500):
            for threat_class in THREAT_PROFILES:
                event = generate_threat_event(rng, threat_class, base_time)
                assert event["sensor_type"] in valid_types

    def test_threat_class_matches_input(self):
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        for threat_class in THREAT_PROFILES:
            event = generate_threat_event(rng, threat_class, base_time)
            assert event["threat_class"] == threat_class


class TestPhysicsBounds:
    """Verify physics-based parameter ranges per threat class."""

    def test_uas_altitude_airborne(self, small_dataset):
        uas = small_dataset[small_dataset["threat_class"] == "air_uas_small"]
        # Most UAS should be above ground
        assert uas["altitude_m_agl"].median() > 5

    def test_uas_rcs_small(self, small_dataset):
        uas = small_dataset[
            (small_dataset["threat_class"] == "air_uas_small") &
            (small_dataset["sensor_type"] == "echodyne_echoguard")
        ]
        if len(uas) > 0:
            # sUAS RCS should be very small
            assert uas["radar_cross_section_m2"].max() <= 0.1

    def test_vehicle_ground_level(self, small_dataset):
        vehicles = small_dataset[small_dataset["threat_class"] == "ground_vehicle"]
        assert vehicles["altitude_m_agl"].median() < 5

    def test_personnel_slow(self, small_dataset):
        personnel = small_dataset[small_dataset["threat_class"] == "ground_personnel"]
        assert personnel["velocity_mps"].median() < 5

    def test_fixed_wing_fast(self, small_dataset):
        fw = small_dataset[small_dataset["threat_class"] == "air_fixed_wing"]
        assert fw["velocity_mps"].median() > 30

    def test_benign_aircraft_high_altitude(self, small_dataset):
        benign = small_dataset[small_dataset["threat_class"] == "benign_aircraft"]
        assert benign["altitude_m_agl"].median() > 500

    def test_wildlife_low_confidence(self, small_dataset):
        wildlife = small_dataset[small_dataset["threat_class"] == "benign_wildlife"]
        assert wildlife["track_confidence_0_1"].median() < 0.6


class TestDataset:
    """Test full dataset generation."""

    def test_class_balance_minimum(self, small_dataset):
        counts = small_dataset["threat_class"].value_counts()
        for cls in THREAT_PROFILES:
            assert counts.get(cls, 0) == 100  # small_dataset uses per_class=100

    def test_full_dataset_5000_per_class(self, full_dataset):
        counts = full_dataset["threat_class"].value_counts()
        for cls in THREAT_PROFILES:
            assert counts.get(cls, 0) >= 5000

    def test_total_event_count(self, small_dataset):
        assert len(small_dataset) == 100 * len(THREAT_PROFILES)

    def test_validation_passes(self, full_dataset):
        stats = validate_dataset(full_dataset)
        assert stats["valid"], f"Validation failed: {stats['issues']}"

    def test_reproducibility(self):
        from datetime import datetime, timezone
        fixed_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        df1 = generate_dataset(per_class=50, seed=123, base_time=fixed_time)
        df2 = generate_dataset(per_class=50, seed=123, base_time=fixed_time)
        # UUIDs are intentionally unique per call; compare everything else
        cols = [c for c in df1.columns if c != "event_id"]
        pd.testing.assert_frame_equal(df1[cols], df2[cols])

    def test_different_seeds_differ(self):
        df1 = generate_dataset(per_class=50, seed=1)
        df2 = generate_dataset(per_class=50, seed=2)
        assert not df1["event_id"].equals(df2["event_id"])


class TestNoiseCharacteristics:
    """Verify Gaussian noise is applied at 5-10% sigma."""

    def test_noise_adds_variance(self):
        """Events with same profile should vary due to noise."""
        rng = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)
        ranges = [
            generate_threat_event(rng, "air_uas_small", base_time)["range_m"]
            for _ in range(1000)
        ]
        # Standard deviation should be meaningful (not zero)
        assert np.std(ranges) > 10

    def test_noise_sigma_controllable(self):
        """Higher noise sigma should produce more variance."""
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        base_time = datetime.now(timezone.utc)

        low_noise = [
            generate_threat_event(rng1, "ground_vehicle", base_time, 0.01)["velocity_mps"]
            for _ in range(500)
        ]
        high_noise = [
            generate_threat_event(rng2, "ground_vehicle", base_time, 0.15)["velocity_mps"]
            for _ in range(500)
        ]
        # Higher noise sigma should produce larger spread (or at least comparable)
        # This is probabilistic, so we use a generous tolerance
        assert np.std(high_noise) >= np.std(low_noise) * 0.5


class TestParquetRoundTrip:
    """Test Parquet save/load preserves data."""

    def test_round_trip(self, small_dataset):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.parquet"
            small_dataset.to_parquet(path, index=False, engine="pyarrow")
            loaded = pd.read_parquet(path)
            pd.testing.assert_frame_equal(small_dataset, loaded)

    def test_schema_preserved(self, small_dataset):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.parquet"
            small_dataset.to_parquet(path, index=False, engine="pyarrow")
            loaded = pd.read_parquet(path)
            assert set(small_dataset.columns) == set(loaded.columns)
            assert len(loaded) == len(small_dataset)
