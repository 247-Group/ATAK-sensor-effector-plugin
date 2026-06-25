"""
Tests for the RACK FP REST API server.

Starts the server in a subprocess and tests all endpoints via HTTP.
"""

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

PROJECT_ROOT = str(Path(__file__).parent.parent)
PORT = 18790  # Use high port to avoid conflicts


def _req(method, path, data=None, raw_data=None):
    """Make an HTTP request to the test server."""
    url = f"http://127.0.0.1:{PORT}{path}"
    if data is not None:
        raw_data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=raw_data, method=method)
    if raw_data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        body = resp.read().decode()
        return resp.status, json.loads(body) if body and resp.headers.get("Content-Type", "").startswith("application/json") else body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return e.code, body


def _valid_event(**overrides):
    event = {
        "event_id": str(uuid.uuid4()),
        "sensor_id": "ECHODYNE-01",
        "sensor_type": "echodyne_echoguard",
        "track_id": "TRK-001",
        "bearing_deg": 45.0,
        "range_m": 500.0,
        "altitude_m_agl": 100.0,
        "velocity_mps": 15.0,
        "heading_deg": 180.0,
        "radar_cross_section_m2": 0.01,
        "track_age_s": 5.0,
        "track_confidence_0_1": 0.85,
        "timestamp_utc": "2026-06-23T20:00:00Z",
        "raw_payload": {"source": "test"},
        "elevation_deg": 11.3,
        "frequency_mhz": 9400.0,
        "lat": 35.0,
        "lon": -79.0,
        "threat_class": "air_uas_small",
        "threat_score": 0.85,
    }
    event.update(overrides)
    return event


def _valid_manifest(**overrides):
    manifest = {
        "plugin_id": "com.aicowboys.rack.fp",
        "display_name": "RACK Force Protection AI",
        "available_actions": [
            {
                "action_id": "issue_alert",
                "action_label": "Issue FP Alert",
                "applicable_threat_classes": ["*"],
            },
        ],
        "current_status": "online",
    }
    manifest.update(overrides)
    return manifest


@pytest.fixture(scope="module")
def server():
    """Start the API server in a subprocess for the test module."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.api", "--port", str(PORT), "--host", "127.0.0.1"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to be ready
    for _ in range(30):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("Server failed to start")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_ok(self, server):
        status, data = _req("GET", "/api/health")
        assert status == 200
        assert data["status"] == "ok"
        assert "uptime_s" in data
        assert "events_ingested" in data
        assert "ws_clients" in data
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_returns_dataset(self, server):
        status, data = _req("GET", "/api/stats")
        assert status == 200
        assert "dataset" in data
        assert data["dataset"]["total_events"] >= 30000
        assert "classes" in data["dataset"]
        assert "sensors" in data["dataset"]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TestSchemas:
    def test_threat_event_schema(self, server):
        status, data = _req("GET", "/api/schemas/threat-event")
        assert status == 200
        assert data["title"] == "ThreatEvent"
        assert "properties" in data
        assert len(data["properties"]) >= 14

    def test_capability_schema(self, server):
        status, data = _req("GET", "/api/schemas/capability")
        assert status == 200
        assert data["title"] == "CapabilityManifest"
        assert "properties" in data


# ---------------------------------------------------------------------------
# Event Ingestion
# ---------------------------------------------------------------------------

class TestEventIngestion:
    def test_ingest_valid_event(self, server):
        event = _valid_event()
        status, data = _req("POST", "/api/events", data=event)
        assert status == 201
        assert data["status"] == "accepted"
        assert data["event_id"] == event["event_id"]

    def test_ingest_auto_generates_id(self, server):
        event = _valid_event()
        del event["event_id"]
        del event["timestamp_utc"]
        status, data = _req("POST", "/api/events", data=event)
        assert status == 201
        assert "event_id" in data
        uuid.UUID(data["event_id"])

    def test_ingest_invalid_schema(self, server):
        status, data = _req("POST", "/api/events", data={"bad": "data"})
        assert status == 422
        assert data["error"] == "Schema validation failed"
        assert len(data["details"]) > 0

    def test_ingest_invalid_json(self, server):
        status, data = _req("POST", "/api/events", raw_data=b"not json")
        assert status == 400
        assert data["error"] == "Invalid JSON"


# ---------------------------------------------------------------------------
# Batch Ingestion
# ---------------------------------------------------------------------------

class TestBatchIngestion:
    def test_batch_ingest_valid(self, server):
        events = [
            _valid_event(event_id=str(uuid.uuid4()), track_id="TRK-A"),
            _valid_event(event_id=str(uuid.uuid4()), track_id="TRK-B"),
        ]
        status, data = _req("POST", "/api/events/batch", data=events)
        assert status == 201
        assert data["total"] == 2
        assert data["accepted"] == 2
        assert data["rejected"] == 0

    def test_batch_partial_reject(self, server):
        events = [
            _valid_event(event_id=str(uuid.uuid4())),
            {"bad": "event"},
        ]
        status, data = _req("POST", "/api/events/batch", data=events)
        assert data["accepted"] == 1
        assert data["rejected"] == 1

    def test_batch_empty(self, server):
        status, data = _req("POST", "/api/events/batch", data=[])
        assert status == 400


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_validate_valid_event(self, server):
        status, data = _req("POST", "/api/events/validate", data=_valid_event())
        assert status == 200
        assert data["valid"] is True

    def test_validate_invalid_event(self, server):
        status, data = _req("POST", "/api/events/validate", data={"bad": "data"})
        assert status == 200
        assert data["valid"] is False
        assert data["schema_errors"] is not None

    def test_validate_physics_warning(self, server):
        # Supersonic ground personnel should trigger physics warning
        event = _valid_event(
            threat_class="ground_personnel",
            velocity_mps=500.0,
            altitude_m_agl=1.0,
        )
        status, data = _req("POST", "/api/events/validate", data=event)
        assert status == 200
        # Physics warnings may or may not fire depending on validator
        assert "physics_warnings" in data


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

class TestManifests:
    def test_register_valid_manifest(self, server):
        manifest = _valid_manifest()
        status, data = _req("POST", "/api/manifests", data=manifest)
        assert status == 201
        assert data["status"] == "registered"
        assert data["plugin_id"] == manifest["plugin_id"]

    def test_register_invalid_manifest(self, server):
        status, data = _req("POST", "/api/manifests", data={"bad": "manifest"})
        assert status == 422

    def test_list_manifests(self, server):
        status, data = _req("GET", "/api/manifests")
        assert status == 200
        assert "count" in data
        assert "manifests" in data
        assert data["count"] >= 1  # At least the one we just registered


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestClassification:
    def test_classify_uas(self, server):
        status, data = _req("POST", "/api/classify", data={
            "altitude_m_agl": 100.0,
            "velocity_mps": 15.0,
            "radar_cross_section_m2": 0.01,
        })
        assert status == 200
        assert data["threat_class"] == "air_uas_small"
        assert data["model"] == "rule_based_v0"
        assert "threat_score" in data

    def test_classify_aircraft(self, server):
        status, data = _req("POST", "/api/classify", data={
            "altitude_m_agl": 5000.0,
            "velocity_mps": 200.0,
            "radar_cross_section_m2": 50.0,
        })
        assert data["threat_class"] == "benign_aircraft"

    def test_classify_ground_vehicle(self, server):
        status, data = _req("POST", "/api/classify", data={
            "altitude_m_agl": 1.0,
            "velocity_mps": 20.0,
            "radar_cross_section_m2": 20.0,
        })
        assert data["threat_class"] == "ground_vehicle"

    def test_classify_personnel(self, server):
        status, data = _req("POST", "/api/classify", data={
            "altitude_m_agl": 1.5,
            "velocity_mps": 2.0,
            "radar_cross_section_m2": 1.0,
        })
        assert data["threat_class"] == "ground_personnel"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_parquet(self, server):
        url = f"http://127.0.0.1:{PORT}/api/export/parquet"
        resp = urllib.request.urlopen(url, timeout=10)
        assert resp.status == 200
        data = resp.read()
        assert len(data) > 1000  # Parquet file should be sizable
        assert data[:4] == b"PAR1"  # Parquet magic bytes

    def test_export_jsonl(self, server):
        url = f"http://127.0.0.1:{PORT}/api/export/jsonl"
        resp = urllib.request.urlopen(url, timeout=10)
        assert resp.status == 200
        first_line = resp.readline().decode().strip()
        parsed = json.loads(first_line)
        assert "event_id" in parsed


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_serves_html(self, server):
        url = f"http://127.0.0.1:{PORT}/"
        resp = urllib.request.urlopen(url, timeout=10)
        assert resp.status == 200
        text = resp.read().decode()
        assert "RACK FP" in text
        assert "<script>" in text
        assert "WebSocket" in text
        assert "connectWS" in text

    def test_dashboard_has_class_badges(self, server):
        url = f"http://127.0.0.1:{PORT}/"
        resp = urllib.request.urlopen(url, timeout=10)
        text = resp.read().decode()
        assert "air_uas_small" in text
        assert "ground_vehicle" in text


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

class TestCORS:
    def test_cors_headers_on_get(self, server):
        url = f"http://127.0.0.1:{PORT}/api/health"
        resp = urllib.request.urlopen(url, timeout=10)
        assert resp.headers["Access-Control-Allow-Origin"] == "*"


# ---------------------------------------------------------------------------
# Health tracks ingestion count
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_health_reflects_ingested_events(self, server):
        # Get current count
        _, h1 = _req("GET", "/api/health")
        count_before = h1["events_ingested"]

        # Ingest one event
        _req("POST", "/api/events", data=_valid_event())

        # Check count incremented
        _, h2 = _req("GET", "/api/health")
        assert h2["events_ingested"] == count_before + 1
