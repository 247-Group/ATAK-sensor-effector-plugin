"""
RACK FP Plugin — REST API Server
==================================

Provides HTTP endpoints for:
  - ThreatEvent ingestion and validation
  - CapabilityManifest registration
  - Dataset statistics and health monitoring
  - Threat classification inference (when model loaded)
  - WebSocket streaming for real-time event feeds

Endpoints:
  GET  /api/health               — Server health check
  GET  /api/stats                — Dataset statistics
  GET  /api/schemas/threat-event — ThreatEvent JSON schema
  GET  /api/schemas/capability   — CapabilityManifest JSON schema
  POST /api/events               — Ingest a ThreatEvent (validates + stores)
  POST /api/events/batch         — Ingest batch of ThreatEvents
  POST /api/events/validate      — Validate without storing
  POST /api/manifests            — Register a CapabilityManifest
  GET  /api/manifests            — List registered manifests
  GET  /api/events/stream        — SSE stream of real-time events
  POST /api/classify             — Classify a ThreatEvent (inference)
  GET  /api/export/parquet       — Download dataset as Parquet
  GET  /api/export/jsonl         — Download dataset as JSONL

Usage:
    python -m server.api                          # default port 8790
    python -m server.api --port 8790 --host 0.0.0.0
    RACK_DATA_DIR=./data python -m server.api
"""

import argparse
import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any

logger = logging.getLogger("rack-fp-api")

# Lazy imports — server should start even if some deps missing
try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.schema_validator import (
    get_capability_manifest_schema,
    get_threat_event_schema,
    validate_capability_manifest,
    validate_events_batch,
    validate_physics_bounds,
    validate_threat_event,
)

# ---------------------------------------------------------------------------
# In-memory stores (production would use a database)
# ---------------------------------------------------------------------------
_events: list[dict] = []
_manifests: dict[str, dict] = {}
_ws_clients: list[web.WebSocketResponse] = []
_start_time: float = time.time()
_event_count: int = 0
_MAX_EVENTS_BUFFER: int = 10_000

DATA_DIR = Path(os.environ.get("RACK_DATA_DIR", Path(__file__).parent.parent / "data"))


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def health(request: "web.Request") -> "web.Response":
    """GET /api/health — Server health check."""
    return web.json_response({
        "status": "ok",
        "uptime_s": round(time.time() - _start_time, 1),
        "events_ingested": _event_count,
        "manifests_registered": len(_manifests),
        "ws_clients": len(_ws_clients),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def stats(request: "web.Request") -> "web.Response":
    """GET /api/stats — Dataset statistics."""
    try:
        import pandas as pd
        parquet_path = DATA_DIR / "synthetic" / "threat_events.parquet"
        if parquet_path.exists():
            df = pd.read_parquet(parquet_path)
            class_counts = df["threat_class"].value_counts().to_dict()
            sensor_counts = df["sensor_type"].value_counts().to_dict()
            return web.json_response({
                "dataset": {
                    "total_events": len(df),
                    "classes": class_counts,
                    "sensors": sensor_counts,
                    "columns": list(df.columns),
                    "file_size_mb": round(parquet_path.stat().st_size / (1024 * 1024), 2),
                },
                "live": {
                    "events_ingested": _event_count,
                    "buffer_size": len(_events),
                },
            })
        else:
            return web.json_response({"error": "No dataset found", "path": str(parquet_path)}, status=404)
    except ImportError:
        return web.json_response({"error": "pandas not installed"}, status=500)


async def get_threat_event_schema_handler(request: "web.Request") -> "web.Response":
    """GET /api/schemas/threat-event — Return ThreatEvent JSON schema."""
    return web.json_response(get_threat_event_schema())


async def get_capability_schema_handler(request: "web.Request") -> "web.Response":
    """GET /api/schemas/capability — Return CapabilityManifest JSON schema."""
    return web.json_response(get_capability_manifest_schema())


async def ingest_event(request: "web.Request") -> "web.Response":
    """POST /api/events — Ingest and validate a single ThreatEvent."""
    global _event_count
    try:
        event = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    # Auto-generate event_id if missing
    if "event_id" not in event:
        event["event_id"] = str(uuid.uuid4())

    # Auto-generate timestamp if missing
    if "timestamp_utc" not in event:
        event["timestamp_utc"] = datetime.now(timezone.utc).isoformat()

    # Validate against schema
    schema_errors = validate_threat_event(event)
    if schema_errors:
        return web.json_response({"error": "Schema validation failed", "details": schema_errors}, status=422)

    # Validate physics bounds
    physics_issues = validate_physics_bounds(event)

    # Store (cap in-memory buffer to prevent unbounded growth)
    _events.append(event)
    _event_count += 1
    if len(_events) > _MAX_EVENTS_BUFFER:
        _events[:] = _events[-_MAX_EVENTS_BUFFER:]

    # Broadcast to WebSocket clients
    await _broadcast_event(event)

    return web.json_response({
        "status": "accepted",
        "event_id": event["event_id"],
        "physics_warnings": physics_issues if physics_issues else None,
    }, status=201)


async def ingest_batch(request: "web.Request") -> "web.Response":
    """POST /api/events/batch — Ingest batch of ThreatEvents."""
    global _event_count
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    events = body if isinstance(body, list) else body.get("events", [])
    if not events:
        return web.json_response({"error": "No events provided"}, status=400)

    # Auto-fill missing fields
    for event in events:
        if "event_id" not in event:
            event["event_id"] = str(uuid.uuid4())
        if "timestamp_utc" not in event:
            event["timestamp_utc"] = datetime.now(timezone.utc).isoformat()

    # Batch validate
    results = validate_events_batch(events)

    # Store valid events
    accepted = 0
    for i, event in enumerate(events):
        is_invalid = any(e["index"] == i for e in results["errors"])
        if not is_invalid:
            _events.append(event)
            _event_count += 1
            accepted += 1
            await _broadcast_event(event)

    if len(_events) > _MAX_EVENTS_BUFFER:
        _events[:] = _events[-_MAX_EVENTS_BUFFER:]

    return web.json_response({
        "total": results["total"],
        "accepted": accepted,
        "rejected": results["invalid"],
        "errors": results["errors"][:20],  # Cap error detail at 20
    }, status=201 if accepted > 0 else 422)


async def validate_event(request: "web.Request") -> "web.Response":
    """POST /api/events/validate — Validate without storing."""
    try:
        event = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    schema_errors = validate_threat_event(event)
    physics_issues = validate_physics_bounds(event)

    valid = not schema_errors and not physics_issues
    return web.json_response({
        "valid": valid,
        "schema_errors": schema_errors if schema_errors else None,
        "physics_warnings": physics_issues if physics_issues else None,
    })


async def register_manifest(request: "web.Request") -> "web.Response":
    """POST /api/manifests — Register a CapabilityManifest."""
    try:
        manifest = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    errors = validate_capability_manifest(manifest)
    if errors:
        return web.json_response({"error": "Schema validation failed", "details": errors}, status=422)

    plugin_id = manifest["plugin_id"]
    manifest["_registered_utc"] = datetime.now(timezone.utc).isoformat()
    _manifests[plugin_id] = manifest

    return web.json_response({
        "status": "registered",
        "plugin_id": plugin_id,
        "actions": len(manifest.get("available_actions", [])),
    }, status=201)


async def list_manifests(request: "web.Request") -> "web.Response":
    """GET /api/manifests — List registered manifests."""
    return web.json_response({
        "count": len(_manifests),
        "manifests": list(_manifests.values()),
    })


async def classify_event(request: "web.Request") -> "web.Response":
    """POST /api/classify — Classify a ThreatEvent (placeholder for model inference)."""
    try:
        event = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    # Placeholder: rule-based classification until Sprint 2 model is trained
    alt = event.get("altitude_m_agl", 0)
    vel = event.get("velocity_mps", 0)
    rcs = event.get("radar_cross_section_m2", 0)

    if rcs < 0.1 and alt > 5 and vel < 35:
        pred_class = "air_uas_small"
        confidence = 0.72
    elif vel > 80 and alt > 1000:
        pred_class = "benign_aircraft"
        confidence = 0.88
    elif rcs > 5 and alt < 5:
        pred_class = "ground_vehicle"
        confidence = 0.80
    elif vel < 10 and alt < 3:
        pred_class = "ground_personnel"
        confidence = 0.65
    elif rcs < 0.5 and vel < 25:
        pred_class = "benign_wildlife"
        confidence = 0.55
    else:
        pred_class = "unknown"
        confidence = 0.30

    return web.json_response({
        "threat_class": pred_class,
        "threat_score": round(confidence, 3),
        "model": "rule_based_v0",
        "latency_ms": 1,
        "note": "Rule-based placeholder. Sprint 2 will use trained XGBoost/MLP model.",
    })


async def export_parquet(request: "web.Request") -> "web.Response":
    """GET /api/export/parquet — Download dataset as Parquet."""
    path = DATA_DIR / "synthetic" / "threat_events.parquet"
    if not path.exists():
        return web.json_response({"error": "No dataset found"}, status=404)
    return web.FileResponse(path, headers={
        "Content-Disposition": "attachment; filename=threat_events.parquet",
    })


async def export_jsonl(request: "web.Request") -> "web.Response":
    """GET /api/export/jsonl — Download dataset as JSONL."""
    path = DATA_DIR / "synthetic" / "threat_events.jsonl"
    if not path.exists():
        return web.json_response({"error": "No dataset found"}, status=404)
    return web.FileResponse(path, headers={
        "Content-Disposition": "attachment; filename=threat_events.jsonl",
    })


# ---------------------------------------------------------------------------
# WebSocket for real-time event streaming
# ---------------------------------------------------------------------------

async def event_stream_ws(request: "web.Request") -> "web.WebSocketResponse":
    """WebSocket /api/ws/events — Real-time event stream."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    _ws_clients.append(ws)
    logger.info(f"WebSocket client connected ({len(_ws_clients)} total)")

    try:
        # Send initial status
        await ws.send_json({
            "type": "connected",
            "events_ingested": _event_count,
            "manifests": len(_manifests),
        })

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                # Client can send commands like {"type": "ping"}
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "Invalid JSON"})
                    continue
                if data.get("type") == "ping":
                    await ws.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
            elif msg.type in (web.WSMsgType.ERROR, web.WSMsgType.CLOSE):
                break
    finally:
        if ws in _ws_clients:
            _ws_clients.remove(ws)
        logger.info(f"WebSocket client disconnected ({len(_ws_clients)} remaining)")

    return ws


async def event_stream_sse(request: "web.Request") -> "web.StreamResponse":
    """GET /api/events/stream — Server-Sent Events stream."""
    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await response.prepare(request)

    # Send initial event
    data = json.dumps({"type": "connected", "events_ingested": _event_count})
    await response.write(f"data: {data}\n\n".encode())

    # Stream events as they arrive (poll-based for simplicity)
    last_idx = len(_events)
    try:
        while True:
            await asyncio.sleep(0.5)
            current_len = len(_events)
            if current_len > last_idx:
                for event in _events[last_idx:current_len]:
                    data = json.dumps(event, default=str)
                    await response.write(f"data: {data}\n\n".encode())
                last_idx = current_len
    except (ConnectionResetError, asyncio.CancelledError):
        pass

    return response


async def _broadcast_event(event: dict) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    if not _ws_clients:
        return
    msg = json.dumps({"type": "event", "data": event}, default=str)
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_str(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RACK FP — Threat Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #0a0e17; color: #e0e6ed; }
        .header { background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%); padding: 16px 24px; border-bottom: 1px solid #21262d; display: flex; align-items: center; justify-content: space-between; }
        .header h1 { font-size: 18px; font-weight: 600; color: #58a6ff; }
        .header .status { display: flex; align-items: center; gap: 8px; font-size: 13px; }
        .header .dot { width: 8px; height: 8px; border-radius: 50%; background: #3fb950; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; padding: 16px 24px; }
        .card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; }
        .card .label { font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 1px; margin-bottom: 4px; }
        .card .value { font-size: 28px; font-weight: 700; color: #58a6ff; }
        .card .sub { font-size: 12px; color: #8b949e; margin-top: 4px; }
        .main { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 0 24px 24px; }
        .panel { background: #161b22; border: 1px solid #21262d; border-radius: 8px; overflow: hidden; }
        .panel .title { padding: 12px 16px; font-size: 13px; font-weight: 600; border-bottom: 1px solid #21262d; color: #c9d1d9; }
        .event-feed { max-height: 400px; overflow-y: auto; padding: 8px; }
        .event-row { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11px; padding: 6px 8px; border-bottom: 1px solid #0d1117; display: grid; grid-template-columns: 140px 120px 80px 60px 1fr; gap: 8px; }
        .event-row:hover { background: #1c2128; }
        .class-badge { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: 600; }
        .class-air_uas_small { background: #da3633; color: #fff; }
        .class-air_fixed_wing { background: #f0883e; color: #fff; }
        .class-ground_vehicle { background: #d29922; color: #000; }
        .class-ground_personnel { background: #8957e5; color: #fff; }
        .class-benign_wildlife { background: #3fb950; color: #000; }
        .class-benign_aircraft { background: #58a6ff; color: #000; }
        .class-unknown { background: #484f58; color: #fff; }
        .bar-chart { padding: 16px; }
        .bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
        .bar-label { width: 140px; font-size: 11px; text-align: right; }
        .bar-fill { height: 20px; border-radius: 3px; transition: width 0.5s ease; }
        .bar-count { font-size: 11px; color: #8b949e; min-width: 50px; }
        .actions-list { padding: 16px; }
        .action-row { display: flex; align-items: center; gap: 12px; padding: 8px; border-bottom: 1px solid #0d1117; }
        .action-btn { padding: 4px 12px; border-radius: 4px; border: 1px solid #30363d; background: #21262d; color: #c9d1d9; font-size: 11px; cursor: pointer; }
        .action-btn:hover { background: #30363d; }
        .action-btn.danger { border-color: #da3633; color: #f85149; }
        .action-btn.danger:hover { background: #da3633; color: #fff; }
        @media (max-width: 768px) { .main { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>RACK FP — Threat Classification Monitor</h1>
        <div class="status">
            <div class="dot" id="ws-dot"></div>
            <span id="ws-status">Connecting...</span>
        </div>
    </div>

    <div class="grid">
        <div class="card"><div class="label">Events Ingested</div><div class="value" id="stat-events">-</div><div class="sub">Total processed</div></div>
        <div class="card"><div class="label">Active Manifests</div><div class="value" id="stat-manifests">-</div><div class="sub">Plugin instances</div></div>
        <div class="card"><div class="label">WS Clients</div><div class="value" id="stat-ws">-</div><div class="sub">Real-time listeners</div></div>
        <div class="card"><div class="label">Uptime</div><div class="value" id="stat-uptime">-</div><div class="sub">Server runtime</div></div>
    </div>

    <div class="main">
        <div class="panel">
            <div class="title">Live Event Feed</div>
            <div class="event-feed" id="event-feed">
                <div style="padding: 16px; color: #8b949e; text-align: center;">Waiting for events...</div>
            </div>
        </div>
        <div class="panel">
            <div class="title">Threat Class Distribution</div>
            <div class="bar-chart" id="class-chart"></div>
            <div class="title" style="margin-top: 8px;">Effector Actions</div>
            <div class="actions-list" id="actions-list">
                <div class="action-row"><span style="font-size:12px">issue_fp_alert</span><div class="action-btn">Issue Alert</div></div>
                <div class="action-row"><span style="font-size:12px">slew_camera</span><div class="action-btn">Slew PTZ</div></div>
                <div class="action-row"><span style="font-size:12px">redirect_uas</span><div class="action-btn">Redirect UAS</div></div>
                <div class="action-row"><span style="font-size:12px">escalate_fpcon</span><div class="action-btn danger">Escalate FPCON</div></div>
                <div class="action-row"><span style="font-size:12px">generate_coa</span><div class="action-btn">Generate COA</div></div>
            </div>
        </div>
    </div>

    <script>
        const classCounts = {};
        const classColors = {
            air_uas_small: '#da3633', air_fixed_wing: '#f0883e', ground_vehicle: '#d29922',
            ground_personnel: '#8957e5', benign_wildlife: '#3fb950', benign_aircraft: '#58a6ff', unknown: '#484f58'
        };
        let eventCount = 0;
        let ws = null;

        function connectWS() {
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${proto}//${location.host}/api/ws/events`);
            ws.onopen = () => {
                document.getElementById('ws-dot').style.background = '#3fb950';
                document.getElementById('ws-status').textContent = 'Connected';
            };
            ws.onclose = () => {
                document.getElementById('ws-dot').style.background = '#da3633';
                document.getElementById('ws-status').textContent = 'Disconnected';
                setTimeout(connectWS, 3000);
            };
            ws.onmessage = (e) => {
                const msg = JSON.parse(e.data);
                if (msg.type === 'event') addEvent(msg.data);
                if (msg.type === 'connected') {
                    eventCount = msg.events_ingested;
                    document.getElementById('stat-events').textContent = eventCount.toLocaleString();
                }
            };
        }

        function addEvent(event) {
            eventCount++;
            const feed = document.getElementById('event-feed');
            if (feed.querySelector('div[style]')) feed.innerHTML = '';
            const cls = event.threat_class || 'unknown';
            classCounts[cls] = (classCounts[cls] || 0) + 1;
            const row = document.createElement('div');
            row.className = 'event-row';
            row.innerHTML = `
                <span>${event.timestamp_utc?.substring(11, 23) || '-'}</span>
                <span class="class-badge class-${cls}">${cls}</span>
                <span>${event.velocity_mps?.toFixed(1) || '-'} m/s</span>
                <span>${event.altitude_m_agl?.toFixed(0) || '-'}m</span>
                <span>${event.sensor_id || '-'}</span>
            `;
            feed.insertBefore(row, feed.firstChild);
            if (feed.children.length > 100) feed.removeChild(feed.lastChild);
            document.getElementById('stat-events').textContent = eventCount.toLocaleString();
            updateChart();
        }

        function updateChart() {
            const chart = document.getElementById('class-chart');
            const max = Math.max(...Object.values(classCounts), 1);
            chart.innerHTML = Object.entries(classCounts)
                .sort((a, b) => b[1] - a[1])
                .map(([cls, count]) => `
                    <div class="bar-row">
                        <div class="bar-label">${cls}</div>
                        <div class="bar-fill" style="width:${(count/max)*100}%;background:${classColors[cls]||'#484f58'}"></div>
                        <div class="bar-count">${count.toLocaleString()}</div>
                    </div>
                `).join('');
        }

        async function refreshStats() {
            try {
                const res = await fetch('/api/health');
                const data = await res.json();
                document.getElementById('stat-events').textContent = data.events_ingested.toLocaleString();
                document.getElementById('stat-manifests').textContent = data.manifests_registered;
                document.getElementById('stat-ws').textContent = data.ws_clients;
                const mins = Math.floor(data.uptime_s / 60);
                const hrs = Math.floor(mins / 60);
                document.getElementById('stat-uptime').textContent = hrs > 0 ? `${hrs}h ${mins%60}m` : `${mins}m`;
            } catch(e) {}
        }

        connectWS();
        refreshStats();
        setInterval(refreshStats, 5000);
    </script>
</body>
</html>"""


async def dashboard(request: "web.Request") -> "web.Response":
    """GET / — Serve the monitoring dashboard."""
    return web.Response(text=DASHBOARD_HTML, content_type="text/html")


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

@web.middleware
async def cors_middleware(request: "web.Request", handler):
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> "web.Application":
    """Create the aiohttp application with all routes."""
    if not HAS_AIOHTTP:
        raise ImportError("aiohttp is required. Install with: pip install aiohttp")

    app = web.Application(middlewares=[cors_middleware])

    # Dashboard
    app.router.add_get("/", dashboard)

    # API routes
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/stats", stats)
    app.router.add_get("/api/schemas/threat-event", get_threat_event_schema_handler)
    app.router.add_get("/api/schemas/capability", get_capability_schema_handler)
    app.router.add_post("/api/events", ingest_event)
    app.router.add_post("/api/events/batch", ingest_batch)
    app.router.add_post("/api/events/validate", validate_event)
    app.router.add_post("/api/manifests", register_manifest)
    app.router.add_get("/api/manifests", list_manifests)
    app.router.add_post("/api/classify", classify_event)
    app.router.add_get("/api/events/stream", event_stream_sse)
    app.router.add_get("/api/ws/events", event_stream_ws)
    app.router.add_get("/api/export/parquet", export_parquet)
    app.router.add_get("/api/export/jsonl", export_jsonl)

    return app


def main():
    parser = argparse.ArgumentParser(description="RACK FP Plugin API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8790, help="Port (default: 8790)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    if not HAS_AIOHTTP:
        print("ERROR: aiohttp is required for the API server.")
        print("Install with: pip install aiohttp")
        sys.exit(1)

    app = create_app()
    logger.info(f"Starting RACK FP API Server on {args.host}:{args.port}")
    logger.info(f"Dashboard: http://localhost:{args.port}/")
    logger.info(f"Health:    http://localhost:{args.port}/api/health")
    logger.info(f"WebSocket: ws://localhost:{args.port}/api/ws/events")
    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
