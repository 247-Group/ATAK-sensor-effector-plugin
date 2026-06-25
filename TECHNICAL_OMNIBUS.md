# RACK FP — Technical Omnibus

> Comprehensive technical reference for the RACK Force Protection Sensor & Effector system.
> Version 1.0.0 | 247 Group RPDT Program | Andersen AFB (PACAF)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [ThreatEvent Data Model](#2-threatevent-data-model)
3. [Capability Manifest](#3-capability-manifest)
4. [REST API Server](#4-rest-api-server)
5. [Android ATAK Plugin](#5-android-atak-plugin)
6. [ML Pipeline](#6-ml-pipeline)
7. [Schema Validation](#7-schema-validation)
8. [ONNX Edge Export](#8-onnx-edge-export)
9. [Synthetic Data Generation](#9-synthetic-data-generation)
10. [Deployment Infrastructure](#10-deployment-infrastructure)
11. [CI/CD Pipeline](#11-cicd-pipeline)
12. [Security Model](#12-security-model)
13. [Network Architecture](#13-network-architecture)
14. [CLI Reference](#14-cli-reference)

---

## 1. System Overview

RACK FP is a dual-stack AI/ML threat classification system designed for real-time force protection at Andersen AFB. It consists of three integrated subsystems:

**Android ATAK Plugin** (Java/Kotlin, Android SDK 34)
- Connects to ATAK via BroadcastReceiver lifecycle
- Maintains persistent WebSocket connection to RACK server
- Translates ThreatEvents into CoT XML for map injection
- Buffers events during disconnection with automatic flush on reconnect
- Registers capability manifest defining available sensor/effector actions

**Python REST API Server** (aiohttp, async)
- 14 REST endpoints for event ingestion, classification, streaming, and management
- WebSocket and SSE real-time event distribution
- In-memory event store with configurable buffer cap (10,000 max)
- Embedded web dashboard for operational monitoring
- Parquet-backed dataset management for training data

**ML Pipeline** (NumPy, pandas, PyArrow, scikit-learn, XGBoost, ONNX)
- Physics-based synthetic data generation with configurable AOI
- JSON Schema Draft 2020-12 validation with physics bounds enforcement
- Dual-model ensemble: MLP (PyTorch) + XGBoost
- ONNX export with INT8 quantization for edge deployment
- Targets: NVIDIA Jetson Nano (TensorRT) and PACSTAR (ONNX Runtime)

---

## 2. ThreatEvent Data Model

### Schema Reference

The ThreatEvent is the core data object, defined in `schemas/threat_event.schema.json` (JSON Schema Draft 2020-12).

**24 total properties | 14 required | 10 optional**

#### Required Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `event_id` | string (uuid) | UUID v4 format | Unique event identifier |
| `timestamp` | string (date-time) | ISO 8601 | Event occurrence time |
| `sensor_type` | string (enum) | 9 values | Originating sensor class |
| `threat_class` | string (enum) | 7 values | Classified threat category |
| `confidence` | number | [0.0, 1.0] | Classification confidence score |
| `latitude` | number | [-90.0, 90.0] | WGS84 latitude |
| `longitude` | number | [-180.0, 180.0] | WGS84 longitude |
| `altitude_m` | number | [0.0, 100000.0] | Altitude in meters (MSL) |
| `velocity_mps` | number | [0.0, 300000000.0] | Speed in meters/second |
| `heading_deg` | number | [0.0, 360.0] | Bearing in degrees (true north) |
| `signal_strength_dbm` | number | [-200.0, 50.0] | Signal strength in dBm |
| `sensor_id` | string | 1-128 chars | Originating sensor identifier |
| `aoi_id` | string | 1-64 chars | Area of Interest identifier |
| `raw_payload` | object | — | Sensor-specific raw data |

#### Optional Extended Fields

| Field | Type | Description |
|-------|------|-------------|
| `bearing_deg` | number [0, 360] | Relative bearing to target |
| `range_m` | number [0, 1e6] | Range to target in meters |
| `rcs_dbsm` | number [-60, 80] | Radar cross section (dBsm) |
| `doppler_shift_hz` | number [-1e6, 1e6] | Doppler frequency shift |
| `frequency_mhz` | number [0.001, 300000] | Operating frequency |
| `modulation_type` | string | RF modulation scheme |
| `acoustic_signature_db` | number [0, 200] | Sound pressure level |
| `classification_hierarchy` | array of strings | Hierarchical classification path |
| `track_id` | string | Persistent track correlator |
| `engagement_status` | string (enum) | `tracking`, `engaging`, `resolved`, `escalated` |

#### Sensor Types (9)

`radar`, `eo_ir`, `acoustic`, `rf_spectrum`, `seismic`, `lidar`, `magnetic`, `cyber`, `fusion`

#### Threat Classes (7)

| Class | Description | Typical Sensors |
|-------|-------------|-----------------|
| `perimeter_breach` | Unauthorized entry to secured area | seismic, magnetic, eo_ir |
| `uas_incursion` | Unmanned aerial system penetration | radar, rf_spectrum, acoustic |
| `vehicle_approach` | Unauthorized vehicle in restricted zone | radar, seismic, eo_ir |
| `indirect_fire` | Incoming projectile/mortar/rocket | radar, acoustic, seismic |
| `cyber_intrusion` | Network/infrastructure compromise | cyber |
| `insider_threat` | Insider anomalous behavior | fusion, cyber, eo_ir |
| `environmental` | Weather, wildlife, natural event | acoustic, seismic, eo_ir |

### CoT XML Mapping

ThreatEvents are converted to Cursor-on-Target XML for ATAK injection via `ThreatEvent.toCotXml()`:

```xml
<event version="2.0" uid="{event_id}" type="{cot_type}" time="{timestamp}"
       start="{timestamp}" stale="{timestamp+5min}" how="m-g">
  <point lat="{latitude}" lon="{longitude}" hae="{altitude_m}" ce="10" le="10"/>
  <detail>
    <contact callsign="RACK-{threat_class}"/>
    <remarks>Threat: {threat_class} | Confidence: {confidence}
      Sensor: {sensor_type} | Signal: {signal_strength_dbm} dBm</remarks>
  </detail>
</event>
```

CoT type mapping by threat class:
- `uas_incursion` → `a-h-A` (hostile air)
- `vehicle_approach` → `a-h-G` (hostile ground)
- `perimeter_breach`, `insider_threat` → `a-s-G` (suspect ground)
- `indirect_fire` → `a-h-G` (hostile ground)
- `cyber_intrusion` → `a-u-G` (unknown ground)
- `environmental` → `a-f-G` (friendly ground)

All string fields are XML-escaped via `escapeXml()` to prevent injection attacks.

---

## 3. Capability Manifest

Defined in `schemas/capability_manifest.schema.json`, the manifest registers plugin capabilities with the RACK server on connection.

### Default Manifest

```json
{
  "plugin_id": "atak-sensor-effector-v1",
  "plugin_version": "1.0.0",
  "capabilities": ["sensor_ingest", "threat_display", "cot_injection",
                    "effector_control", "alert_routing"],
  "actions": [
    {"name": "display_threat", "human_gate": false},
    {"name": "inject_cot_marker", "human_gate": false},
    {"name": "escalate_fpcon", "human_gate": true},
    {"name": "acknowledge_alert", "human_gate": false},
    {"name": "redirect_uas", "human_gate": true},
    {"name": "log_event", "human_gate": false},
    {"name": "request_classification", "human_gate": false}
  ],
  "compute_profile": {
    "edge_capable": true,
    "gpu_available": false,
    "max_batch_size": 100,
    "preferred_model_format": "onnx"
  }
}
```

Human-gated actions (`escalate_fpcon`, `redirect_uas`) require explicit operator confirmation before execution.

---

## 4. REST API Server

**File**: `server/api.py` (659 lines)
**Framework**: aiohttp (async Python)
**Default bind**: `0.0.0.0:8790`

### Endpoint Reference

#### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Returns `{"status": "healthy", "version": "1.0.0", "uptime": ...}` |
| `/api/v1/stats` | GET | Dataset statistics, event counts, model info |
| `/api/v1/config` | GET | Current server configuration |
| `/api/v1/config` | POST | Update runtime configuration |

#### Event Ingestion

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/api/v1/ingest` | POST | ThreatEvent JSON | Ingest single event, validates against schema |
| `/api/v1/ingest/batch` | POST | `{"events": [...]}` | Batch ingest (array of ThreatEvents) |

Both endpoints enforce JSON Schema validation and return `400` on invalid payloads. The in-memory buffer is capped at 10,000 events (FIFO eviction).

#### Classification

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/api/v1/classify` | POST | ThreatEvent JSON | `{"event_id", "predicted_class", "confidence", "all_scores": {...}}` |

Returns top prediction with confidence and scores across all 7 threat classes.

#### Event Retrieval & Streaming

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/events` | GET | Returns recent events (query: `?limit=N`) |
| `/api/v1/events/stream` | GET | Server-Sent Events stream (`text/event-stream`) |
| `/api/v1/events/ws` | WebSocket | Bidirectional event stream (JSON frames) |

#### Model & Schema Export

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/export/onnx` | GET | Download trained ONNX model file |
| `/api/v1/export/schema` | GET | Download ThreatEvent JSON Schema |

#### Plugin Registration

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/api/v1/manifest` | POST | CapabilityManifest JSON | Register plugin capabilities |

#### Dashboard

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | HTML dashboard with live event table, stats, WebSocket auto-refresh |

### WebSocket Protocol

The WebSocket endpoint (`/api/v1/events/ws`) accepts and sends JSON frames:

**Server → Client**: ThreatEvent JSON objects as they are ingested
**Client → Server**: ThreatEvent JSON for ingestion (alternative to REST POST)

Connection lifecycle:
1. Client connects to `ws://{host}:{port}/api/v1/events/ws`
2. Server adds client to broadcast list
3. On each ingested event, server broadcasts to all connected clients
4. Client can send events via the same WebSocket
5. On disconnect, server removes client from broadcast list

---

## 5. Android ATAK Plugin

### Build Configuration

| Property | Value |
|----------|-------|
| `compileSdk` | 34 |
| `minSdk` | 26 |
| `targetSdk` | 34 |
| `Java` | 11 |
| `applicationId` | `com.group247.ataksensoreffector` |

### Dependencies

- **ATAK SDK**: `main.jar` in `app/libs/` (compileOnly)
- **OkHttp 4.12.0**: HTTP/WebSocket client
- **Gson 2.10.1**: JSON serialization
- **AndroidX AppCompat 1.6.1**: UI compatibility
- **Material 1.11.0**: Material Design components

### Component Architecture

#### SensorEffectorLifecycle (`plugin/`)
- `BroadcastReceiver` registered in AndroidManifest
- Handles ATAK plugin load/unload lifecycle via `PLUGIN_LOAD_COMPLETE` action
- Entry point for plugin initialization

#### RackApiClient (`network/`)
- OkHttp-based HTTP and WebSocket client
- Endpoint methods: `checkHealth()`, `ingestEvent()`, `ingestBatch()`, `classify()`, `registerManifest()`, `getEvents()`, `getStats()`
- WebSocket: `connectWebSocket(EventListener)` with automatic JSON parsing
- 30-second connect/read/write timeouts
- `EventListener` interface: `onThreatEvent()`, `onConnectionStateChanged()`, `onError()`

#### RackConnectionService (`network/`)
- Android `Service` with `START_STICKY` restart policy
- Maintains persistent connection with automatic reconnection (5-second delay)
- Thread-safe event buffering (max 1,000 events) during disconnection
- `CopyOnWriteArrayList` for callback management
- Registers capability manifest on connection
- `volatile` connection state with `destroyed` flag to prevent post-destroy reconnection
- `ThreatEventCallback` interface for UI updates on main thread

#### ThreatEvent (`model/`)
- Java POJO with Gson `@SerializedName` annotations
- `toCotXml()` generates Cursor-on-Target XML with affiliation mapping
- `escapeXml()` sanitizes all user-controlled strings (prevents XML injection)
- Builder-style setters returning `this` for method chaining

#### CapabilityManifest (`model/`)
- Static `createDefault()` factory for standard manifest
- 5 capabilities, 7 actions (2 human-gated), compute profile

#### ClassifyResponse (`model/`)
- Wraps classification result: `event_id`, `predicted_class`, `confidence`, `all_scores`

### Network Security

`network_security_config.xml` allows cleartext HTTP to:
- `10.247.4.44` (venus RACK server)
- `localhost` / `127.0.0.1`

All other destinations require HTTPS.

---

## 6. ML Pipeline

### Model Architecture

**Ensemble**: MLP (primary) + XGBoost (secondary)

#### MLP (Multi-Layer Perceptron)
- Input: 11 numeric features (normalized)
- Architecture: configurable hidden layers (default: [128, 64, 32])
- Activation: ReLU
- Output: 7-class softmax
- Training: Adam optimizer, CrossEntropyLoss
- Export: PyTorch → ONNX with dynamic batch axis

#### XGBoost
- Gradient boosted trees classifier
- Features: same 11 numeric inputs
- Output: 7-class probability distribution
- Export: custom ONNX conversion via `onnxmltools`

### Feature Vector (11 dimensions)

| Index | Feature | Normalization |
|-------|---------|---------------|
| 0 | sensor_type | One-hot encoded (ordinal) |
| 1 | confidence | Raw [0, 1] |
| 2 | latitude | Standardized |
| 3 | longitude | Standardized |
| 4 | altitude_m | Log-scaled |
| 5 | velocity_mps | Log-scaled |
| 6 | heading_deg | Circular (sin/cos) |
| 7 | signal_strength_dbm | Standardized |
| 8 | bearing_deg | Circular (sin/cos) |
| 9 | range_m | Log-scaled |
| 10 | rcs_dbsm | Standardized |

---

## 7. Schema Validation

**File**: `pipeline/schema_validator.py` (180 lines)

Two-stage validation pipeline:

### Stage 1: JSON Schema Validation
- JSON Schema Draft 2020-12 (`jsonschema` library)
- Validates all 24 fields against type constraints, enums, ranges
- Returns structured error list with JSON path locations

### Stage 2: Physics Bounds Checking
- Validates physical plausibility beyond schema ranges:
  - Latitude/longitude within AOI bounding box (configurable)
  - Velocity below speed of light
  - Altitude non-negative
  - Signal strength within receiver sensitivity range
  - Confidence normalized [0, 1]
- Configurable strictness levels: `strict`, `warn`, `permissive`

### Usage

```python
from pipeline.schema_validator import SchemaValidator

validator = SchemaValidator()

# Validate single event
errors = validator.validate(event_dict)

# Validate DataFrame
report = validator.validate_dataframe(df)
# Returns: {valid: int, invalid: int, errors: [...]}
```

---

## 8. ONNX Edge Export

**File**: `pipeline/export_to_edge.py` (315 lines)

### Export Pipeline

```
Trained Model (PyTorch/XGBoost)
    ↓
ONNX Export (opset 17)
    ↓
ONNX Optimization (graph passes)
    ↓
INT8 Quantization (optional)
    ↓
Target Validation
    ↓
Artifact Bundle (.onnx + metadata.json)
```

### Target Platforms

| Platform | Runtime | Quantization | Batch Size |
|----------|---------|-------------|------------|
| Jetson Nano | TensorRT (via ONNX) | INT8 | 1-64 |
| PACSTAR | ONNX Runtime | FP32 / INT8 | 1-128 |
| Server (Venus) | ONNX Runtime GPU | FP32 | 1-1024 |

### INT8 Quantization

- Post-training quantization via ONNX Runtime quantization tools
- Calibration dataset: 1,000 samples from synthetic generator
- Accuracy validation: <1% degradation threshold
- Size reduction: typically 4x compared to FP32

### Metadata Bundle

Each export produces `metadata.json`:

```json
{
  "model_name": "rack_fp_mlp",
  "version": "1.0.0",
  "opset": 17,
  "input_shape": [null, 11],
  "output_shape": [null, 7],
  "classes": ["perimeter_breach", "uas_incursion", ...],
  "quantization": "int8",
  "target_platform": "jetson_nano",
  "export_timestamp": "2026-06-25T12:00:00Z",
  "accuracy_fp32": 0.94,
  "accuracy_int8": 0.93
}
```

---

## 9. Synthetic Data Generation

**File**: `pipeline/synthetic_threat_generator.py` (472 lines)

### Physics-Based Generation

Each threat class has physically realistic noise models:

| Class | Position Noise (m) | Velocity Range (m/s) | Altitude Range (m) | Signal (dBm) |
|-------|--------------------|-----------------------|---------------------|---------------|
| `perimeter_breach` | Gaussian σ=50 | 0.5–5.0 | 0–10 | -90 to -50 |
| `uas_incursion` | Gaussian σ=100 | 5–30 | 10–500 | -80 to -40 |
| `vehicle_approach` | Gaussian σ=200 | 5–40 | 0–5 | -70 to -30 |
| `indirect_fire` | Gaussian σ=500 | 100–900 | 50–5000 | -60 to -20 |
| `cyber_intrusion` | Fixed (facility coords) | 0 | 0 | -100 to -60 |
| `insider_threat` | Gaussian σ=30 | 0.5–3.0 | 0–5 | -85 to -55 |

### AOI: Andersen AFB

- Center: 13.583° N, 144.924° E
- Bounding box: ±0.05° lat/lon (~5.5 km)
- Altitude: 0–500 m (terrain-adjusted)

### Output Formats

- **Parquet** (primary): columnar, compressed, schema-preserving
- **JSON** (optional `--json-export`): one event per line, schema-validated
- **CSV** (optional): flat table for quick inspection

### CLI

```bash
python pipeline/synthetic_threat_generator.py \
  --output data/synthetic/threat_events.parquet \
  --per-class 5000 \
  --seed 42 \
  --json-export \
  --aoi-center 13.583 144.924 \
  --aoi-radius 0.05
```

---

## 10. Deployment Infrastructure

### Server Topology

```
Internet ──► Phobos (38.97.126.85:179)
                │ SSH Gateway
                │ LAN: 10.247.4.4
                │
           ─────┼───── 10.247.4.0/24 Lab Network ─────
                │
                ├── Venus (10.247.4.44)
                │   RACK Server (:8790)
                │   ML Workloads
                │   GPU: NVIDIA (TBD)
                │   1TB RAM, ZFS storage
                │   Ubuntu 24.04 (QEMU/KVM VM)
                │
                └── Other VMs (10.247.4.1, 10.247.4.3)
```

### Venus Server Setup

`scripts/setup_venus.sh` provides three protocols:

1. **Protocol 1: Discovery** (`discover`)
   - CPU, memory, GPU, ZFS, network, firewall, Ollama, Python inventory
   - Safe, read-only operation

2. **Protocol 2: Setup** (`setup`, requires root)
   - Disables NVMe swap (anti-pattern with 1TB RAM)
   - Configures UFW firewall (Ollama locked to lab network)
   - Optimizes 9p mounts with `cache=mmap`
   - Creates Python venv at `/opt/venv/ml-rack`
   - Installs PyTorch (CUDA 12.4), XGBoost, scikit-learn, ONNX Runtime GPU, MLflow

3. **Protocol 3: Verify** (`verify`)
   - Validates PyTorch + CUDA, data stack, ONNX Runtime, XGBoost
   - GPU matmul smoke test
   - Reports READY/INCOMPLETE status

### 9p Shared Filesystem

Venus VMs share filesystems via 9p virtio mounts:
- Recommended: `cache=mmap`, `msize=262144`
- Used for model artifacts and dataset sharing between VMs

---

## 11. CI/CD Pipeline

**File**: `.github/workflows/ci.yml`

### Jobs

#### 1. `android-build` (Android Build & Tests)
- **Runner**: `ubuntu-latest`
- **JDK**: Temurin 17
- **Steps**: Checkout → JDK setup → Gradle cache → `test` → `lint` → `assembleDebug` → `assembleRelease` (if keystore secrets present) → Upload APKs

#### 2. `python-tests` (Python Pipeline Tests)
- **Runner**: `ubuntu-latest`
- **Python**: 3.12
- **Steps**: Checkout → Python setup → `pip install -r requirements.txt` → Generate synthetic dataset → `pytest tests/ -v --tb=short -x`

#### 3. `build` (Rollup)
- **Depends on**: `android-build`, `python-tests`
- **Purpose**: Required status check for branch protection
- **Steps**: Echo "All checks passed"

### Artifacts

| Name | Path | Condition |
|------|------|-----------|
| `debug-apk` | `app/build/outputs/apk/debug/*.apk` | Always |
| `release-apk` | `app/build/outputs/apk/release/*.apk` | Keystore secrets present |

### Branch Protection

- Required status check: `build`
- Required approving reviews: 1 (from collaborator with write access)
- Target branch: `main`

---

## 12. Security Model

### Network Security

| Control | Implementation |
|---------|---------------|
| Cleartext HTTP | Only to `10.247.4.44`, `localhost`, `127.0.0.1` |
| Ollama access | UFW/iptables: port 11434 restricted to `10.247.4.44` + localhost |
| SSH | Key-based auth only (ed25519) |
| Lab network | `10.247.4.0/24` isolated subnet |

### Application Security

| Control | Implementation |
|---------|---------------|
| XML injection | `escapeXml()` on all CoT XML string fields |
| Memory cap | In-memory event buffer limited to 10,000 (server) and 1,000 (Android) |
| Input validation | JSON Schema Draft 2020-12 + physics bounds |
| Human gates | `escalate_fpcon` and `redirect_uas` require operator confirmation |
| Thread safety | `volatile` flags, `CopyOnWriteArrayList`, `synchronized` blocks |
| Reconnection | `destroyed` flag prevents post-destroy reconnect loops |

### Data Classification

- ThreatEvents contain geolocation and sensor data — handle as CUI minimum
- Raw sensor payloads may contain classified data — `raw_payload` field is opaque
- Parquet datasets are unencrypted — encrypt at rest on Venus ZFS

---

## 13. Network Architecture

### Protocol Stack

```
┌──────────────────────────────────────┐
│            Application               │
│  ThreatEvent JSON / CoT XML         │
├──────────────────────────────────────┤
│            Transport                 │
│  HTTP/1.1 (REST) / WebSocket / SSE  │
├──────────────────────────────────────┤
│            Network                   │
│  IPv4 (10.247.4.0/24)              │
├──────────────────────────────────────┤
│            Link                      │
│  virtio-net (QEMU/KVM VMs)         │
└──────────────────────────────────────┘
```

### Port Assignments

| Port | Service | Host |
|------|---------|------|
| 8790 | RACK FP API | Venus (10.247.4.44) |
| 11434 | Ollama | Venus (10.247.4.44) |
| 179 | SSH (non-standard) | Phobos (38.97.126.85) |
| 22 | SSH | Venus (internal, restricted) |

### Connection Lifecycle

```
Plugin Boot
    │
    ├── onCreate(): Initialize RackApiClient with host:port
    │
    ├── onStartCommand(): Begin connection
    │   │
    │   ├── checkHealth() → HTTP GET /api/v1/health
    │   │   ├── Success → registerManifest() + connectWebSocket()
    │   │   └── Failure → scheduleReconnect(5000ms)
    │   │
    │   └── WebSocket Connected
    │       ├── onConnectionStateChanged(true)
    │       ├── flushBuffer() → POST /api/v1/ingest/batch
    │       └── Begin receiving ThreatEvents
    │
    ├── Runtime: submitEvent(event)
    │   ├── Connected → POST /api/v1/ingest
    │   └── Disconnected → bufferEvent() (max 1000, FIFO)
    │
    └── onDestroy(): destroyed=true, disconnect, shutdown executor
```

---

## 14. CLI Reference

**File**: `rack_cli.py` (178 lines)

```
rack_cli.py <command> [options]

Commands:
  server          Start the RACK FP API server
                  --host HOST     Bind address (default: 0.0.0.0)
                  --port PORT     Bind port (default: 8790)

  generate        Generate synthetic threat data
                  --output PATH   Output parquet file
                  --per-class N   Events per threat class (default: 5000)
                  --seed N        Random seed
                  --json-export   Also export JSON

  validate        Validate dataset against ThreatEvent schema
                  --input PATH    Parquet file to validate
                  --strict        Fail on physics warnings

  export-onnx     Export trained models to ONNX format
                  --model PATH    Model checkpoint
                  --output PATH   ONNX output path
                  --quantize      Apply INT8 quantization
                  --target        Target platform (jetson|pacstar|server)

  verify-env      Verify ML environment (GPU, CUDA, libraries)

  test            Run the full test suite (pytest)

  stats           Display dataset statistics
                  --input PATH    Parquet file
```

---

*Document generated for 247 Group RPDT Program. For questions, contact the RACK FP development team.*
