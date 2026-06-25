# RACK FP — Sensor & Effector Plugin for ATAK

**Real-time AI-powered threat classification for Android Tactical Awareness Kit (ATAK)**

RACK FP (Force Protection) is a dual-stack system combining an Android ATAK plugin with a Python ML pipeline and REST API server. It ingests sensor data from radar, EO/IR, acoustic, RF, seismic, lidar, magnetic, and cyber sources, classifies threats using ensemble ML models (MLP + XGBoost), and injects Cursor-on-Target (CoT) markers directly into the ATAK common operating picture.

Built for Andersen AFB (PACAF) force protection operations under the 247 Group RPDT program.

---

## Architecture

```
┌─────────────────────┐         ┌─────────────────────────────────┐
│   ATAK Plugin       │  HTTP   │     RACK FP Server (Python)     │
│   (Android/Java)    │◄───────►│     aiohttp + WebSocket         │
│                     │   WS    │                                 │
│  ThreatEvent model  │         │  /api/v1/ingest    POST         │
│  CoT XML injection  │         │  /api/v1/classify  POST         │
│  RackApiClient      │         │  /api/v1/events    GET/SSE/WS   │
│  Connection Service │         │  /api/v1/health    GET          │
│  Capability Manifest│         │  /api/v1/manifest  POST         │
└─────────────────────┘         │  /api/v1/stats     GET          │
                                │  /api/v1/export/*  GET          │
                                │  /dashboard        GET          │
                                └────────┬────────────────────────┘
                                         │
                                ┌────────▼────────────────────────┐
                                │     ML Pipeline                 │
                                │  Synthetic data generation      │
                                │  Schema validation (JSON+physics)│
                                │  ONNX edge export (Jetson/PACSTAR)│
                                │  XGBoost + MLP ensemble         │
                                └─────────────────────────────────┘
```

## Features

- **7 threat classes**: `perimeter_breach`, `uas_incursion`, `vehicle_approach`, `indirect_fire`, `cyber_intrusion`, `insider_threat`, `environmental`
- **9 sensor types**: `radar`, `eo_ir`, `acoustic`, `rf_spectrum`, `seismic`, `lidar`, `magnetic`, `cyber`, `fusion`
- **24-field ThreatEvent schema** with JSON Schema Draft 2020-12 validation and physics bounds checking
- **Real-time streaming** via WebSocket and Server-Sent Events (SSE)
- **CoT XML injection** into ATAK map with threat-specific markers (hostile/suspect/friend/unknown)
- **Capability manifest** registration with human-gated escalation actions
- **ONNX edge export** for Jetson Nano and PACSTAR deployments with INT8 quantization
- **Physics-based synthetic data** generation across Andersen AFB AOI
- **Built-in dashboard** at `/dashboard` with live event monitoring
- **Automatic reconnection** with event buffering during disconnection

## Quick Start

### Prerequisites

- Python 3.10+ with pip
- Android Studio (for plugin development)
- JDK 17 (for Gradle builds)

### Server

```bash
# Install dependencies
pip install -r requirements.txt

# Generate synthetic training data
python pipeline/synthetic_threat_generator.py \
  --output data/synthetic/threat_events.parquet \
  --per-class 5000 --seed 42 --json-export

# Start the RACK server
python rack_cli.py server --host 0.0.0.0 --port 8790

# Or use the CLI
python rack_cli.py server          # Start server (default: 0.0.0.0:8790)
python rack_cli.py generate        # Generate synthetic data
python rack_cli.py validate        # Validate dataset against schema
python rack_cli.py export-onnx     # Export models to ONNX
python rack_cli.py verify-env      # Check GPU/ML environment
python rack_cli.py test            # Run test suite
python rack_cli.py stats           # Dataset statistics
```

### Android Plugin

```bash
# Build debug APK
./gradlew assembleDebug

# Run unit tests
./gradlew test

# Build signed release (requires keystore secrets)
KEYSTORE_FILE=/path/to/keystore.jks \
KEYSTORE_PASSWORD=... \
KEY_ALIAS=... \
KEY_PASSWORD=... \
./gradlew assembleRelease
```

The plugin connects to the RACK server at `10.247.4.44:8790` by default. Override via SharedPreferences at runtime.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Server health check |
| `POST` | `/api/v1/ingest` | Ingest single ThreatEvent |
| `POST` | `/api/v1/ingest/batch` | Ingest batch of events |
| `POST` | `/api/v1/classify` | Classify a ThreatEvent |
| `GET` | `/api/v1/events` | List recent events |
| `GET` | `/api/v1/events/stream` | SSE event stream |
| `WS` | `/api/v1/events/ws` | WebSocket event stream |
| `POST` | `/api/v1/manifest` | Register capability manifest |
| `GET` | `/api/v1/stats` | Dataset and server statistics |
| `GET` | `/api/v1/export/onnx` | Download ONNX model |
| `GET` | `/api/v1/export/schema` | Download ThreatEvent schema |
| `GET` | `/api/v1/config` | Server configuration |
| `POST` | `/api/v1/config` | Update server configuration |
| `GET` | `/dashboard` | Web dashboard |

## ThreatEvent Schema

Each event contains 14 required fields and 10 optional extended fields:

```json
{
  "event_id": "uuid",
  "timestamp": "2026-06-25T12:00:00Z",
  "sensor_type": "radar",
  "threat_class": "uas_incursion",
  "confidence": 0.95,
  "latitude": 13.583,
  "longitude": 144.924,
  "altitude_m": 150.0,
  "velocity_mps": 12.5,
  "heading_deg": 270.0,
  "signal_strength_dbm": -45.0,
  "sensor_id": "RADAR-01",
  "aoi_id": "andersen_north",
  "raw_payload": {}
}
```

Physics bounds are enforced: latitude [-90, 90], longitude [-180, 180], altitude [0, 100000], velocity [0, 3e8], heading [0, 360], confidence [0, 1].

## Project Structure

```
├── .github/workflows/ci.yml           # CI: Android + Python + rollup
├── app/                                # Android ATAK plugin
│   ├── build.gradle                    # Android build config (SDK 34, Java 11)
│   ├── libs/                           # ATAK SDK (main.jar)
│   └── src/
│       ├── main/java/.../
│       │   ├── model/                  # ThreatEvent, CapabilityManifest, ClassifyResponse
│       │   ├── network/                # RackApiClient (OkHttp), RackConnectionService
│       │   └── plugin/                 # SensorEffectorLifecycle (BroadcastReceiver)
│       ├── main/res/xml/               # network_security_config.xml
│       └── test/java/                  # PluginTest, RackApiClientTest
├── server/
│   └── api.py                          # aiohttp REST API (14 endpoints, WS, SSE, dashboard)
├── pipeline/
│   ├── synthetic_threat_generator.py   # Physics-based data generation (6 classes)
│   ├── schema_validator.py             # JSON Schema + physics bounds validation
│   ├── export_to_edge.py               # ONNX export (MLP + XGBoost, INT8 quant)
│   └── verify_env.py                   # GPU/ML environment checker
├── schemas/
│   ├── threat_event.schema.json        # ThreatEvent JSON Schema (Draft 2020-12)
│   └── capability_manifest.schema.json # Plugin capability registration
├── scripts/
│   ├── setup_venus.sh                  # Venus server provisioning (discovery/setup/verify)
│   └── optimize_tensorrt.sh            # TensorRT optimization script
├── tests/                              # Python test suite (27 API + 82 pipeline tests)
├── rack_cli.py                         # Unified CLI (7 subcommands)
├── requirements.txt                    # Python dependencies
└── DEPLOYMENT_MANIFEST.md              # Deployment documentation
```

## Deployment

The system runs on the 247 Group lab network (`10.247.4.0/24`):

| Host | Role | Address |
|------|------|---------|
| Venus | ML workloads, RACK server | `10.247.4.44:8790` |
| Phobos | Build server, SSH gateway | `38.97.126.85:179` (LAN: `10.247.4.4`) |

See `scripts/setup_venus.sh` for server provisioning and `DEPLOYMENT_MANIFEST.md` for full deployment procedures.

### Edge Targets

| Platform | Format | Quantization |
|----------|--------|-------------|
| Jetson Nano | ONNX → TensorRT | INT8 |
| PACSTAR | ONNX Runtime | FP32/INT8 |

## CI/CD

GitHub Actions runs on every push/PR to `main`:

1. **Android Build & Tests** — JDK 17, Gradle build, lint, debug + signed release APK
2. **Python Pipeline Tests** — Python 3.12, synthetic data generation, pytest suite
3. **Build** — Rollup status check (required for merge)

Artifacts: `debug-apk` and `release-apk` uploaded on successful builds.

## Testing

```bash
# Python tests (109 tests)
python -m pytest tests/ -v --tb=short -x

# Android unit tests
./gradlew test

# Full CI locally
python rack_cli.py test
```

## Security

- Cleartext HTTP allowed only to `10.247.4.44`, `localhost`, and `127.0.0.1` (configured in `network_security_config.xml`)
- Ollama port (11434) firewalled to lab network only
- Human-gated actions: `escalate_fpcon`, `redirect_uas`
- XML injection protection on all CoT output fields
- In-memory event buffer capped at 10,000 entries

## License

Proprietary — 247 Group, Inc. All rights reserved.
