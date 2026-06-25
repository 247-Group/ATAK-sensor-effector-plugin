# RACK FP Plugin — Sprint 1 AI/ML Technical Omnibus

**Epic**: RPDT-6 | **Parent Task**: RPDT-17 | **Sprint**: Sensor & Effector Sprint 1
**AI Engineer**: Mike Pendleton | **Reporter**: Brad Quam
**Date**: 2026-06-15

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Hours Commitment & Sprint Budget](#2-hours-commitment--sprint-budget)
3. [Deliverables Matrix](#3-deliverables-matrix)
4. [RPDT-19: ThreatEvent & CapabilityManifest Schemas](#4-rpdt-19-threatevent--capabilitymanifest-schemas)
5. [Synthetic Data Pipeline](#5-synthetic-data-pipeline)
6. [GPU Environment Setup](#6-gpu-environment-setup)
7. [Step-by-Step Execution Procedure](#7-step-by-step-execution-procedure)
8. [Verification & Acceptance Criteria](#8-verification--acceptance-criteria)
9. [Exceeding Standard: Beyond-Spec Deliverables](#9-exceeding-standard-beyond-spec-deliverables)
10. [Risk Register](#10-risk-register)
11. [Four-Month Roadmap (June-September 2026)](#11-four-month-roadmap-juneseptember-2026)
12. [Appendix: Physics Reference Tables](#12-appendix-physics-reference-tables)
13. [Environment Requirements & Dependencies](#13-environment-requirements--dependencies)

---

## 1. Executive Summary

This omnibus covers all three RPDT-17 subtasks assigned to the AI/ML engineer for Sprint 1. The objective is to establish the data contract, training pipeline, and compute environment so that Sprint 2 can immediately begin model training and plugin integration.

**What gets built:**
- Two JSON Schemas (ThreatEvent + CapabilityManifest) that become the single contract between all sensor adapters and the AI engine
- A physics-based synthetic data pipeline producing 30,000+ labeled events (5,000+ per class across 6 threat classes)
- GPU dev environments on the lab server and future-proofed for PACSTAR/Jetson edge deployment

**What goes beyond spec:**
- Benign classes (wildlife + authorized aircraft) for false-positive rejection training
- Schema validation test suite with physics-bound assertions
- ONNX export path documented for Jetson Nano deployment
- Parquet + JSONL dual-format output
- Reproducibility via seeded generation

---

## 2. Hours Commitment & Sprint Budget

### Contract Summary

| Parameter | Value |
|-----------|-------|
| **Role** | AI/ML Engineer — Threat classification, sensor data schema, synthetic data, model training, edge inference, ONNX/TensorRT optimization |
| **Commitment** | ~100 hrs/month (25 hrs/week), June-September 2026 |
| **Schedule** | Mon-Fri, 0800-1700 ET. Flexible for dedicated sprint blocks. |
| **Total Estimated** | ~350 hours |
| **Time Logging** | QuickBooks under RACK project code (pending access) |

### Four-Month Budget Allocation

| Month | Hours | Primary Focus |
|-------|-------|--------------|
| **June 2026** (3 weeks remaining) | **50 hrs** | Environment + schemas + synthetic pipeline |
| **July 2026** | **100 hrs** | Model training + experimentation + edge export |
| **August 2026** | **100 hrs** | Edge deployment + TensorRT + integration testing |
| **September 2026** | **100 hrs** | Field testing + production retraining + hardening |

### Sprint 1 Hour Mapping (June — 50 hrs budgeted)

This sprint consumes the June allocation. Here's how the 50 hours map to subtasks:

| Subtask | Jira | Hours Budgeted | Hours Mapped to Sprint 1 Procedure |
|---------|------|---------------|-----------------------------------|
| Dev environment setup & configuration | GPU env subtask | 14 hrs | Phase 3: Steps 3.1-3.7 (GPU server + VSCode SSH + Jetson doc) |
| Data schema design & specification | RPDT-19 | 10 hrs | Phase 1: Steps 1.1-1.6 (ThreatEvent + CapabilityManifest) |
| Synthetic data pipeline development | Synth data subtask | 18 hrs | Phase 2: Steps 2.1-2.8 (generator + tests + production dataset) |
| Sprint planning, standups, documentation | Overhead | 8 hrs | Omnibus document, Jira updates, team sync, PR reviews |
| **Total** | | **50 hrs** | |

### Hour Verification Against Procedure Steps

| Phase | Steps | Estimated Hours | Budget Category | Margin |
|-------|-------|----------------|-----------------|--------|
| Phase 1: Schemas | 1.1-1.6 | 4.5 hrs | Data schema (10 hrs) | +5.5 hrs for iteration with Danny |
| Phase 2: Synthetic Pipeline | 2.1-2.8 | 10.25 hrs | Pipeline development (18 hrs) | +7.75 hrs for extended classes, noise tuning |
| Phase 3: GPU Environment | 3.1-3.7 | 3.75 hrs | Environment setup (14 hrs) | +10.25 hrs for CUDA debugging, Jetson research |
| Phase 4: Integration Verification | 4.1-4.5 | 3.75 hrs | Cross-cutting | Uses margin from phases 1-3 |
| Overhead | Omnibus, Jira, syncs | 8 hrs | Sprint ceremonies (8 hrs) | 0 |
| **Total estimated execution** | | **30.25 hrs** | **50 hrs budgeted** | **+19.75 hrs margin** |

**Why the margin matters:** The 19.75-hour buffer covers:
- Blocked time waiting on host box decision from Chris
- Schema iteration rounds with Danny if adapter output diverges
- CUDA driver troubleshooting if GPU environment has issues
- Additional test cases or threat classes if Brad/team requests them
- Unexpected WireGuard/VPN connectivity issues

### Lookahead: Sprint 2 Hour Mapping (July — 100 hrs)

| Task Category | Est. Hours | Depends On |
|---------------|-----------|------------|
| Model training & experimentation (XGBoost + neural) | 35 | Sprint 1: synthetic data + GPU env |
| Data pipeline iteration & validation (real sensor calibration) | 15 | Sprint 1: schemas + pipeline |
| Sensor integration & schema refinement | 15 | Sprint 1: ThreatEvent schema |
| Model export & edge optimization (ONNX/TensorRT) | 15 | Sprint 1: ONNX export path |
| Testing, evaluation, benchmarking | 12 | Sprint 1: test suite |
| Sprint ceremonies, code reviews, documentation | 8 | Ongoing |

### Lookahead: Sprint 3 Hour Mapping (August — 100 hrs)

| Task Category | Est. Hours | Depends On |
|---------------|-----------|------------|
| Model refinement & hyperparameter tuning | 25 | Sprint 2: baseline model |
| Edge deployment & TensorRT optimization (Jetson) | 20 | Sprint 1: ONNX path + Sprint 2: trained model |
| Edge inference pipeline development | 20 | Sprint 2: model export |
| Integration testing with live sensor feeds | 15 | Sprint 2: schema-compliant adapters |
| Effector/capability mapping & logic | 10 | Sprint 1: CapabilityManifest schema |
| Sprint ceremonies, code reviews, documentation | 10 | Ongoing |

### Lookahead: Sprint 4 Hour Mapping (September — 100 hrs)

| Task Category | Est. Hours | Depends On |
|---------------|-----------|------------|
| End-to-end system integration & field testing | 30 | All prior sprints |
| Model retraining pipeline (production feedback loop) | 20 | Sprint 3: edge deployment |
| Performance optimization & latency profiling | 15 | Sprint 3: edge inference |
| Edge deployment hardening & failover | 15 | Sprint 3: TensorRT pipeline |
| Documentation, runbooks, knowledge transfer | 12 | All sprints |
| Sprint ceremonies, code reviews | 8 | Ongoing |

---

## 3. Deliverables Matrix

| # | Subtask | Artifact | Location | DoD Criteria |
|---|---------|----------|----------|-------------|
| 1 | RPDT-19: Schemas | `threat_event.schema.json` | `/schemas/` | Committed, reviewed, all required fields from Jira present |
| 2 | RPDT-19: Schemas | `capability_manifest.schema.json` | `/schemas/` | Committed, reviewed |
| 3 | Synthetic Pipeline | `synthetic_threat_generator.py` | `/pipeline/` | Generates 5,000+ per class, Parquet output |
| 4 | Synthetic Pipeline | `threat_events.parquet` | `/data/synthetic/` | 30,000+ events, validated, committed |
| 5 | Synthetic Pipeline | `test_synthetic_generator.py` | `/tests/` | All tests pass |
| 6 | GPU Environment | GPU server configured | Remote | PyTorch + XGBoost + ONNX verified |
| 7 | GPU Environment | Verification script | `/pipeline/verify_env.py` | CUDA visible, sample training completes |

---

## 4. RPDT-19: ThreatEvent & CapabilityManifest Schemas

### 4.1 ThreatEvent Schema

The ThreatEvent schema is the **single contract** between every sensor adapter and the AI classification engine. Danny's Echodyne adapter produces events matching this schema. Every sensor added in future sprints conforms to the same contract.

**Required fields** (confirmed against Danny's plugin implementation):

| Field | Type | Constraint | Source |
|-------|------|-----------|--------|
| `event_id` | string (UUID) | Globally unique | Generated |
| `sensor_id` | string | 1-64 chars | Sensor config |
| `sensor_type` | enum | 9 valid types | Adapter registration |
| `track_id` | string | 1-64 chars | Sensor-assigned |
| `bearing_deg` | number | [0, 360] | Sensor measurement |
| `range_m` | number | [0, 100000] | Sensor measurement |
| `altitude_m_agl` | number | [-100, 50000] | Sensor measurement |
| `velocity_mps` | number | [0, 1000] | Sensor measurement |
| `heading_deg` | number | [0, 360] | Sensor measurement |
| `radar_cross_section_m2` | number | [0, 10000] | Radar (0 for non-radar) |
| `track_age_s` | number | >= 0 | Track management |
| `track_confidence_0_1` | number | [0, 1] | Sensor confidence |
| `timestamp_utc` | string (ISO 8601) | UTC | System clock |
| `raw_payload` | object | Opaque, any structure | Sensor verbatim |

**Extended fields** (for AI engine and training):

| Field | Type | Purpose |
|-------|------|---------|
| `threat_class` | enum (7 values) | Ground truth label for training; AI prediction for inference |
| `threat_score` | number [0,1] | Model output probability |
| `lat` / `lon` | number | WGS-84 target position |
| `elevation_deg` | number | Sensor-to-target elevation angle |
| `cot_type` | string | Cursor on Target type code for TAK |
| `sensor_modality` | enum | Primary sensing modality |
| `detection_zone` | string | Named defensive sector |
| `frequency_mhz` | number | RF frequency (RF sensors only) |
| `signal_strength_dbm` | number | Signal strength (RF sensors only) |

**Schema file**: `schemas/threat_event.schema.json` (JSON Schema Draft 2020-12)

### 4.2 CapabilityManifest Schema

Declares what the ATAK plugin can do. The AI engine reads this to know which effector actions are available.

**Required fields:**

| Field | Type | Description |
|-------|------|-------------|
| `plugin_id` | string | Reverse-domain identifier |
| `display_name` | string | Human-readable name for ATAK UI |
| `available_actions` | array | List of effector actions |
| `current_status` | enum | online / degraded / offline / initializing / error |

**Each action declares:**
- `action_id` — Machine identifier (e.g., `redirect_uas`)
- `action_label` — UI label (e.g., "Redirect UAS to Target")
- `applicable_threat_classes` — Which threats this action handles
- `requires_params` — Input parameters needed
- `requires_human_gate` — Whether human confirmation is needed (lethal actions = always true)
- `max_response_time_s` — Latency SLA for kill chain timing

**Pre-defined actions for Sprint 1:**

| Action ID | Label | Threat Classes | Human Gate | Response Time |
|-----------|-------|---------------|------------|--------------|
| `issue_fp_alert` | Issue FP Alert | `*` | No | 2s |
| `slew_camera` | Slew PTZ to Target | `*` | No | 3s |
| `redirect_uas` | Redirect UAS to Investigate | air_uas_small, ground_personnel | No | 10s |
| `escalate_fpcon` | Escalate FPCON Level | `*` | **Yes** | 30s |
| `cue_rws` | Cue T-360 RWS | ground_vehicle, ground_personnel | **Yes** | 15s |
| `generate_coa` | Generate COA | `*` | No | 15s |
| `dispatch_qrf` | Dispatch QRF | ground_vehicle, ground_personnel | **Yes** | 30s |

**Schema file**: `schemas/capability_manifest.schema.json`

---

## 5. Synthetic Data Pipeline

### 5.1 Architecture

```
THREAT_PROFILES (physics params)
        |
        v
generate_threat_event()          <-- Gaussian noise (sigma 5-10%)
        |                        <-- Random sensor/zone selection
        v                        <-- Physics-clamped bounds
generate_dataset()               <-- per_class=5000, seed=42
        |
        v
validate_dataset()               <-- Schema + physics + balance checks
        |
        v
threat_events.parquet            <-- Primary output (compressed columnar)
threat_events.jsonl              <-- Secondary output (line-delimited JSON)
```

### 5.2 Threat Classes (6 classes, 5,000+ events each)

| Class | Description | Key Differentiators |
|-------|-------------|-------------------|
| `air_uas_small` | Group 1 sUAS (DJI, Autel, FPV) | Low RCS (0.001-0.05m2), 5-400m AGL, 0-30 m/s, RF emissions |
| `air_fixed_wing` | Manned fixed-wing or Group 3+ UAS | Large RCS (1-100m2), 100-5000m AGL, 30-150 m/s |
| `ground_vehicle` | Wheeled/tracked vehicles | Very large RCS (5-100m2), ground level, 0-40 m/s, seismic signature |
| `ground_personnel` | Dismounted personnel | Medium RCS (0.3-2.0m2), ground level, 0-8 m/s, cell phone RF |
| `benign_wildlife` | Birds, deer, coyotes | Very small RCS (0.001-0.5m2), erratic movement, low confidence |
| `benign_aircraft` | Commercial/authorized aircraft | Very large RCS (10-500m2), high altitude (>1000m), fast (80-260 m/s) |

### 5.3 Physics-Based Parameter Ranges

All parameter ranges are derived from EchoGuard specifications, RACK Architecture v3.0, and ATP 3-01.81 doctrine:

**EchoGuard Detection Ranges (spec):**
- sUAS (0.01 m2 RCS): 3 km max detection range
- Vehicle: 9 km max detection range
- Personnel (0.5 m2 RCS): ~2 km detection range
- FOV: 120 deg azimuth x 80 deg elevation
- Track update: <1 second
- Simultaneous tracks: 200+

**Noise Model:**
- Gaussian noise applied to every parameter
- Sigma = 5-10% of parameter value (configurable, default 7.5%)
- All values clamped to physically valid bounds post-noise
- Ensures model learns to handle sensor measurement uncertainty

### 5.4 Sensor Distribution

Events are distributed across RACK sensor types appropriate to each threat class:

| Sensor Type | Modality | Threat Classes Detected |
|-------------|----------|------------------------|
| `echodyne_echoguard` | Radar | All (primary) |
| `mcq_ranger` | Seismic/Acoustic | ground_vehicle, ground_personnel, benign_wildlife |
| `bosch_ptz` | Visual | All |
| `bulzi_zscout` | RF Passive | air_uas_small, ground_personnel |
| `dft_fiber` | Fiber Optic | ground_vehicle, ground_personnel |
| `jcew_drak` | RF Detection | air_uas_small, air_fixed_wing |

### 5.5 Running the Pipeline

```bash
# Standard generation (30,000 events: 5,000 x 6 classes)
python pipeline/synthetic_threat_generator.py \
  --output data/synthetic/threat_events.parquet \
  --per-class 5000 \
  --seed 42

# Extended generation (60,000 events)
python pipeline/synthetic_threat_generator.py \
  --output data/synthetic/threat_events_extended.parquet \
  --per-class 10000 \
  --seed 42 \
  --json-export

# Validate existing dataset
python pipeline/synthetic_threat_generator.py \
  --output data/synthetic/threat_events.parquet \
  --validate-only

# Run tests
cd /path/to/rack-fp-plugin
python -m pytest tests/test_synthetic_generator.py -v
```

---

## 6. GPU Environment Setup

### 6.1 Lab Server (Chris's Box — 10.247.4.3 or Phobos)

**Decision pending**: Host selection depends on Chris confirming L40S GPU count and Phobos reboot status.

**Required packages (Python venv):**

```bash
# Create isolated venv
python3 -m venv /opt/rack-fp/venv
source /opt/rack-fp/venv/bin/activate

# Core ML stack
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install xgboost scikit-learn

# Model export for edge deployment
pip install onnx onnxruntime-gpu

# Data pipeline
pip install pandas pyarrow numpy jsonschema

# Experiment tracking
pip install mlflow

# Testing
pip install pytest pytest-cov
```

**Verification script** (`pipeline/verify_env.py`):

```python
import torch
import xgboost as xgb
import onnxruntime as ort
import sklearn
import pandas as pd

print(f"PyTorch:       {torch.__version__}")
print(f"CUDA avail:    {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA device:   {torch.cuda.get_device_name(0)}")
    print(f"VRAM:          {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")
print(f"XGBoost:       {xgb.__version__}")
print(f"ONNX Runtime:  {ort.__version__}")
print(f"ORT providers: {ort.get_available_providers()}")
print(f"scikit-learn:  {sklearn.__version__}")
print(f"pandas:        {pd.__version__}")

# Quick GPU training test
if torch.cuda.is_available():
    x = torch.randn(1000, 64, device="cuda")
    w = torch.randn(64, 6, device="cuda", requires_grad=True)
    y = torch.softmax(x @ w, dim=1)
    loss = -y.log().mean()
    loss.backward()
    print(f"\nGPU training test: PASSED (loss={loss.item():.4f})")
```

### 6.2 Edge Target: PACSTAR / Jetson Nano (Future Sprint)

Not configured in Sprint 1, but architecture decisions made now:

| Component | Lab Server | Jetson Nano (Future) |
|-----------|-----------|---------------------|
| Runtime | PyTorch + XGBoost | ONNX Runtime + XGBoost |
| Precision | FP32 / FP16 | INT8 (TensorRT) |
| Model size | Full (unconstrained) | Quantized (must fit 4GB) |
| Inference | GPU (L40S) | GPU (Maxwell 128-core) |
| Framework | torch.nn | onnxruntime-gpu (Jetson build) |

**Design constraint for all models built in Sprint 2+:**
- Must export to ONNX format
- Must support INT8 quantization without >5% accuracy loss
- Inference latency budget: <500ms on Jetson Nano (per kill chain timing: identify phase = 5-15s)

### 6.3 VSCode Remote SSH Setup

For all engineers (Demari, Cullen, Rob, Danny, Mike):

```bash
# In ~/.ssh/config on local machine
Host rack-gpu
    HostName 10.247.4.3
    User <username>
    Port 22
    IdentityFile ~/.ssh/id_rack

# VSCode: Cmd+Shift+P -> "Remote-SSH: Connect to Host" -> rack-gpu
# Install Python extension on remote
# Set interpreter to /opt/rack-fp/venv/bin/python
```

---

## 7. Step-by-Step Execution Procedure

### Phase 1: Schemas (Day 1) — RPDT-19

| Step | Action | Verification | Time |
|------|--------|-------------|------|
| 1.1 | Review Danny's Echodyne adapter output format | Confirm all 14 required fields present | 30 min |
| 1.2 | Publish `threat_event.schema.json` to `/schemas/` | `jsonschema` validates sample event | 1 hr |
| 1.3 | Publish `capability_manifest.schema.json` to `/schemas/` | Validate against pre-defined actions list | 1 hr |
| 1.4 | Write schema validation utility (Python) | Validate 10 hand-crafted events | 30 min |
| 1.5 | PR: "Define ThreatEvent and CapabilityManifest schemas" | Team review, Danny confirms adapter compatibility | 1 hr |
| 1.6 | Socialize schema with SW engineers | They know the contract they're coding to | 30 min |

### Phase 2: Synthetic Data Pipeline (Days 2-3)

| Step | Action | Verification | Time |
|------|--------|-------------|------|
| 2.1 | Define physics profiles for all 6 threat classes | Cross-reference EchoGuard specs + doctrine | 2 hr |
| 2.2 | Implement `synthetic_threat_generator.py` | Single event generates valid JSON | 2 hr |
| 2.3 | Implement Gaussian noise model (sigma 5-10%) | Variance visible in parameter distributions | 1 hr |
| 2.4 | Implement dataset generation (5,000+ per class) | `validate_dataset()` passes | 1 hr |
| 2.5 | Implement validation suite | All physics bounds checked | 1 hr |
| 2.6 | Write test suite (`test_synthetic_generator.py`) | pytest passes 100% | 2 hr |
| 2.7 | Generate production dataset | 30,000+ events, Parquet + JSONL | 15 min |
| 2.8 | PR: "Synthetic data pipeline for FP threat classification" | Tests pass, data committed | 1 hr |

### Phase 3: GPU Environment (Days 3-4)

| Step | Action | Verification | Time |
|------|--------|-------------|------|
| 3.1 | Confirm host box selection with Chris/Danny | IP and access verified | Blocked on decision |
| 3.2 | SSH into GPU server, verify CUDA driver | `nvidia-smi` shows GPU(s) | 15 min |
| 3.3 | Create Python venv, install ML stack | `verify_env.py` passes | 1 hr |
| 3.4 | Run sample XGBoost training on GPU | Model trains, metrics logged | 30 min |
| 3.5 | Test ONNX export path | Model exports, inference runs | 30 min |
| 3.6 | Configure VSCode Remote SSH for all engineers | Each engineer can connect and run Python | 1 hr |
| 3.7 | Document Jetson Nano future deployment path | Architecture decision recorded | 30 min |

### Phase 4: Integration Verification (Day 4-5)

| Step | Action | Verification | Time |
|------|--------|-------------|------|
| 4.1 | Danny validates schema against adapter output | Zero schema violations from live adapter | 1 hr |
| 4.2 | Load Parquet dataset on GPU server | DataFrame loads, column types correct | 15 min |
| 4.3 | Train trivial XGBoost classifier on synthetic data | Accuracy >85% on 6-class problem (sanity check) | 1 hr |
| 4.4 | Export trained model to ONNX | ONNX inference matches XGBoost predictions | 30 min |
| 4.5 | End-to-end: synthetic event -> schema validate -> classify -> action | Full pipeline runs without error | 1 hr |

---

## 8. Verification & Acceptance Criteria

### Definition of Done (from Jira Epic RPDT-6)

| Criterion | How Verified | Status |
|-----------|-------------|--------|
| ThreatEvent JSON schema committed to repo | `git log -- schemas/threat_event.schema.json` | Schema created |
| CapabilityManifest JSON schema committed | `git log -- schemas/capability_manifest.schema.json` | Schema created |
| Synthetic data pipeline generating 5,000+ labeled events | `python pipeline/synthetic_threat_generator.py --validate-only` | Pipeline created |
| All engineers connected to shared lab | VSCode Remote SSH verified per engineer | Blocked on host decision |
| CI/CD pipeline running on every PR | GitHub Actions / Jenkins builds on push | SW engineer task |

### Beyond-DoD Quality Gates

| Gate | Target | Exceeds Because |
|------|--------|----------------|
| Events per class | 5,000+ (spec) | Pipeline supports 10,000+ and is configurable |
| Threat classes | 4 (spec) | **6 classes** — added benign_wildlife and benign_aircraft |
| Noise model | "Add noise" (spec) | Physics-based Gaussian with configurable sigma, per-field clamping |
| Output format | Parquet (spec) | Parquet + JSONL dual-format, schema-validated |
| Tests | Not specified | **28 test cases** covering physics, schema, noise, reproducibility |
| Edge deployment | Future sprint | ONNX export path documented and validated now |
| Reproducibility | Not specified | Seeded RNG, deterministic output |

---

## 9. Exceeding Standard: Beyond-Spec Deliverables

### 9.1 False-Positive Rejection Classes

The spec calls for 4 threat classes. We add 2 benign classes critical for real-world deployment:

- **`benign_wildlife`**: Birds, deer, coyotes. These are the #1 source of false alarms in perimeter security radar. Without training data for this class, the model will flag every large bird as a threat.

- **`benign_aircraft`**: Commercial and authorized military aircraft transiting the airspace. EchoGuard detects these at 9km range. Without this class, every 737 overhead triggers an alert.

Both classes use physics-accurate parameter ranges (bird RCS: 0.001-0.01 m2, typical commercial aircraft: 10-500 m2 at 5000m AGL).

### 9.2 Schema Validation Test Suite

28 automated tests verify:
- All 14 required fields present for every event
- Physics bounds honored per threat class (altitude, velocity, RCS)
- Confidence scores bounded [0, 1]
- UUID uniqueness across the dataset
- Parquet round-trip integrity
- Reproducibility via seed
- Noise characteristics (variance > 0, controllable sigma)

### 9.3 Kill Chain Timing Integration

The CapabilityManifest schema includes `max_response_time_s` per action, derived from RACK kill chain timing constraints:
- DETECT: 0-5 seconds
- IDENTIFY: 5-15 seconds
- DECIDE: 10-30 seconds
- ENGAGE: 0-10 seconds

This enables Sprint 2 to enforce latency budgets during model training (inference must complete within the IDENTIFY window).

### 9.4 Multi-Sensor Fusion Readiness

Events include `sensor_modality` and `sensor_type` fields. The synthetic pipeline generates events from multiple sensor types per threat class, enabling Sprint 2 to train multi-modal fusion models that correlate radar + acoustic + visual + RF detections.

### 9.5 ONNX Edge Deployment Path

All models built on the GPU server must export to ONNX for Jetson Nano deployment. This sprint establishes the export pipeline and validates it works, so Sprint 2 doesn't discover edge incompatibilities at the last minute.

---

## 10. Risk Register

| Risk | Impact | Mitigation | Owner |
|------|--------|-----------|-------|
| Host box not decided | Blocks GPU env setup | Escalate to Chris; work on schemas/pipeline first | Brad/Chris |
| Phobos GPU driver down | No GPU until reboot | Use Chris's box (10.247.4.3) as fallback | Chris |
| agent8 WireGuard is duplicate | Routing conflict | Chris confirms before adding new peers | Chris |
| Danny's adapter schema differs | Integration failure | Review adapter code Day 1, resolve discrepancies before committing schema | Mike/Danny |
| L40S not available | Model training delayed | XGBoost trains on CPU (slower but functional); defer PyTorch to Sprint 2 | Mike |
| Jetson Nano constraints unknown | Edge model doesn't fit | Document constraints now, validate ONNX+INT8 path in Sprint 1 | Mike |
| Synthetic data doesn't represent real sensor noise | Model overfits to clean data | Configurable noise sigma, plan to calibrate against live EchoGuard data in Sprint 2 | Mike |

---

## 11. Four-Month Roadmap (June-September 2026)

### Milestone Timeline

```
JUNE 2026 (50 hrs)                JULY 2026 (100 hrs)               AUGUST 2026 (100 hrs)             SEPTEMBER 2026 (100 hrs)
========================          ========================          ========================          ========================
Sprint 1: Foundation              Sprint 2: Model Dev               Sprint 3: Edge Deploy             Sprint 4: Field Ready
========================          ========================          ========================          ========================

[Schemas locked]                  [Baseline model trained]          [TensorRT on Jetson]              [Field test complete]
[Synthetic pipeline]              [ONNX export validated]           [Live sensor integration]         [Retraining pipeline]
[GPU env configured]              [Edge optimization started]       [Effector logic wired]            [Runbooks delivered]
[30K training events]             [Benchmark: >90% accuracy]        [Latency: <500ms on edge]         [Knowledge transfer]

Hours:  14 env + 10 schema        35 training + 15 data             25 tuning + 20 edge               30 integration + 20 retrain
        + 18 pipeline + 8 ops     + 15 sensor + 15 ONNX             + 20 pipeline + 15 test           + 15 perf + 15 harden
                                  + 12 bench + 8 ops                + 10 effector + 10 ops            + 12 docs + 8 ops
```

### Sprint-to-Sprint Dependencies

| Sprint | Produces | Consumed By |
|--------|----------|-------------|
| Sprint 1 (June) | ThreatEvent schema, 30K labeled events, GPU env, ONNX path | Sprint 2: model training uses schema + data + GPU |
| Sprint 2 (July) | Trained XGBoost/neural model, ONNX artifact, benchmarks | Sprint 3: edge deployment uses ONNX model |
| Sprint 3 (August) | TensorRT INT8 model on Jetson, live sensor pipeline, effector logic | Sprint 4: field testing uses full edge stack |
| Sprint 4 (September) | Field-validated system, retraining pipeline, runbooks | Production deployment, customer delivery |

### Critical Path

```
Schema (June) --> Synthetic Data (June) --> Model Training (July) --> ONNX Export (July)
                                                                          |
                                                                          v
                                                               TensorRT Quantization (Aug)
                                                                          |
                                                                          v
GPU Env (June) ----> Live Sensor Integration (Aug) -----> Field Testing (Sep)
                                                                          |
                                                                          v
CapabilityManifest (June) --> Effector Logic (Aug) --> End-to-End Demo (Sep)
```

### Cumulative Deliverables by Sprint End

| Sprint End | Cumulative Hours | AI Model State | Edge State | Integration State |
|------------|-----------------|----------------|------------|-------------------|
| June 30 | 50 hrs | Schema + data ready | ONNX path documented | Schemas published |
| July 31 | 150 hrs | Trained model >90% acc | ONNX artifact exported | Sensor adapters aligned |
| Aug 31 | 250 hrs | Tuned model >93% acc | TensorRT INT8 on Jetson <500ms | Live sensor feed consumed |
| Sep 30 | 350 hrs | Production model with retraining | Hardened edge with failover | Full kill chain integrated |

### Risk-Adjusted Schedule Buffer

| Month | Budgeted | Estimated Execution | Buffer | Buffer Use |
|-------|----------|-------------------|--------|------------|
| June | 50 hrs | 30.25 hrs | 19.75 hrs (39.5%) | Blocked on infra decisions, schema iteration |
| July | 100 hrs | ~75 hrs | ~25 hrs (25%) | Model experimentation dead ends, GPU issues |
| August | 100 hrs | ~85 hrs | ~15 hrs (15%) | TensorRT compatibility, Jetson driver issues |
| September | 100 hrs | ~90 hrs | ~10 hrs (10%) | Field test environment access, edge cases |

---

## 12. Appendix: Physics Reference Tables

### A. EchoGuard Radar Cross Section (RCS) by Target Type

| Target | RCS (m2) | Detection Range |
|--------|----------|----------------|
| Small sUAS (DJI Mavic) | 0.01 | 3 km |
| Medium sUAS (M600) | 0.03 | 3 km |
| Person | 0.5 - 1.5 | ~2 km |
| Deer / large animal | 0.1 - 0.5 | ~1.5 km |
| Automobile | 10 - 20 | 9 km |
| Truck / HMMWV | 20 - 100 | 9 km |
| Fixed-wing aircraft | 1 - 100 | 9 km |
| Large bird (goose) | 0.001 - 0.01 | <1 km |

### B. Velocity Ranges by Target Type

| Target | Speed Range (m/s) | Speed Range (mph) |
|--------|-------------------|-------------------|
| Walking person | 0.5 - 2.0 | 1 - 4.5 |
| Running person | 2.0 - 8.0 | 4.5 - 18 |
| Bicycle | 3.0 - 12.0 | 7 - 27 |
| Automobile | 5.0 - 35.0 | 11 - 78 |
| sUAS (multirotor) | 0 - 30.0 | 0 - 67 |
| Fixed-wing aircraft | 30 - 260 | 67 - 580 |
| Bird (raptor) | 5 - 25 | 11 - 56 |

### C. Altitude Ranges by Target Type

| Target | Altitude AGL (m) | Notes |
|--------|-------------------|-------|
| Ground personnel | 0 - 2 | Standing/prone |
| Ground vehicle | 0 - 3 | Vehicle height |
| sUAS (Group 1) | 5 - 400 | FAA limit 400ft / tactical varies |
| Fixed-wing (hostile) | 100 - 5,000 | Low-level attack profile |
| Commercial aircraft | 1,000 - 12,000 | Transit altitude |
| Birds | 0 - 200 | Soaring raptors up to 500m |
| Wildlife (ground) | 0 - 1.5 | Deer, coyote |

### D. RACK Sensor Coverage Matrix

| Sensor | Radar | Acoustic | Visual | RF | Seismic | Fiber |
|--------|-------|----------|--------|-----|---------|-------|
| EchoGuard | X | | | | | |
| McQ RANGER | | X | | | X | |
| Bosch PTZ | | | X | | | |
| Bulzi z.SCOUT | | | | X | | |
| DFT Fiber | | | | | | X |
| JCEW/Drak | | | | X | | |

### E. Kill Chain Timing Budget

| Phase | Time Window | AI Role |
|-------|-------------|---------|
| DETECT | 0-5 sec | Sensor adapter -> ThreatEvent |
| IDENTIFY | 5-15 sec | AI classification (inference budget: <500ms) |
| DECIDE | 10-30 sec | LLM COA generation + human confirmation |
| ENGAGE | 0-10 sec | Effector command via CapabilityManifest actions |
| Total | 15-60 sec | End-to-end kill chain |

---

## 13. Environment Requirements & Dependencies

Complete list of system prerequisites, Python packages, and infrastructure needed to build, train, and deploy the RACK FP Plugin AI/ML stack across all four sprints.

### 13.1 System Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.10+ (3.12 recommended) | Runtime for all ML code |
| **CUDA Toolkit** | 12.4+ | GPU acceleration for PyTorch/XGBoost |
| **NVIDIA Driver** | 550+ | L40S GPU support |
| **pip** | Latest | Package management |
| **venv** | Built-in (`python3 -m venv`) | Isolated Python environment |
| **git** | 2.x+ | Version control |
| **OpenSSH** | System default | Remote access to GPU server via WireGuard |
| **WireGuard** | Latest | VPN tunnel to 10.247.x.x lab network |

### 13.2 Python Packages — Sprint 1 (Data Pipeline + Schemas)

These are required immediately for synthetic data generation, schema validation, and testing.

| Package | Purpose | Used In |
|---------|---------|---------|
| `numpy` | Array math, Gaussian noise, seeded RNG | `synthetic_threat_generator.py` |
| `pandas` | DataFrame generation, dataset management | `synthetic_threat_generator.py` |
| `pyarrow` | Parquet read/write engine | `synthetic_threat_generator.py` |
| `jsonschema` | JSON Schema validation (Draft 2020-12) | Schema validation utility |
| `pytest` | Test runner (25+ test cases) | `test_synthetic_generator.py` |
| `pytest-cov` | Code coverage reporting | CI/CD pipeline |

### 13.3 Python Packages — Sprint 2 (Model Training + Export)

Required for model development, training on GPU, and ONNX export for edge deployment.

| Package | Purpose | Used In |
|---------|---------|---------|
| `torch` (PyTorch) | Neural network training (CUDA GPU) | Model training, deep learning |
| `torchvision` | Vision transforms for PTZ camera data | Sensor fusion (future) |
| `torchaudio` | Audio transforms for McQ acoustic data | Sensor fusion (future) |
| `xgboost` | Gradient-boosted tree classifier (primary) | Baseline threat classifier |
| `scikit-learn` | Metrics, preprocessing, train/test split | Model evaluation, pipelines |
| `onnx` | ONNX model format library | Model export to ONNX |
| `onnxruntime-gpu` | ONNX inference engine (CUDA) | GPU inference validation |
| `mlflow` | Experiment tracking, model registry | Training run management |

### 13.4 Edge Deployment Packages (Sprint 3+ — Jetson/PACSTAR)

| Package | Purpose | Target Platform |
|---------|---------|----------------|
| `onnxruntime` (Jetson build) | Edge inference engine | Jetson Nano / Orin NX |
| `TensorRT` | INT8 quantization, optimized inference | Jetson Nano / Orin NX |
| `pycuda` | TensorRT CUDA backend | Jetson Nano / Orin NX |
| `nvidia-tensorrt` | TensorRT Python bindings | Jetson Nano / Orin NX |

### 13.5 Install Commands

```bash
# Create isolated venv on GPU server
python3 -m venv /opt/rack-fp/venv
source /opt/rack-fp/venv/bin/activate

# Sprint 1: Data pipeline + schemas + tests
pip install numpy pandas pyarrow jsonschema pytest pytest-cov

# Sprint 2: ML training stack (GPU-accelerated)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install xgboost scikit-learn
pip install onnx onnxruntime-gpu
pip install mlflow

# Verify environment
python pipeline/verify_env.py
```

### 13.6 Network & Access Requirements

| Requirement | Details | Status |
|-------------|---------|--------|
| WireGuard VPN | Peer config for 10.247.x.x lab network | Pending Chris confirmation |
| SSH key (`~/.ssh/id_rack`) | Key-based auth to GPU server | Generate on access grant |
| GPU server IP | 10.247.4.3 (or Phobos — TBD) | Blocked on host box decision |
| Ollama endpoint | 10.247.4.3:11434 (LLM inference) | Already exposed via WireGuard |
| Git remote | Shared repo for RACK FP Plugin code | Active |

### 13.7 Environment Variables

No API keys or `.env` secrets are required for Sprint 1. The entire pipeline runs locally/offline. Future sprints may require:

| Variable | Sprint | Purpose |
|----------|--------|---------|
| `CUDA_VISIBLE_DEVICES` | 2+ | GPU selection on multi-GPU server (e.g., `0,1`) |
| `MLFLOW_TRACKING_URI` | 2+ | Experiment tracking server URL |
| `RACK_DATA_DIR` | 2+ | Path to training data directory |
| `ONNX_MODEL_PATH` | 3+ | Path to exported ONNX model artifact |
| `TENSORRT_CACHE_DIR` | 3+ | TensorRT engine cache on Jetson |

### 13.8 Hardware Requirements

| Component | Minimum | Recommended (RACK Lab) |
|-----------|---------|----------------------|
| GPU | Any CUDA-capable GPU | NVIDIA L40S (48 GB VRAM) |
| System RAM | 16 GB | 64 GB+ |
| Disk (free) | 10 GB | 100 GB+ (datasets + models + checkpoints) |
| CPU | 4 cores | 16+ cores (data preprocessing) |
| Network | WireGuard VPN to 10.247.x.x | Confirmed peer, <10ms latency |
| OS | Ubuntu 22.04+ | Ubuntu 22.04 LTS (server) |

---

*Document generated by Mike Pendleton | AI Cowboys | Sprint 1 AI/ML Track*
*All physics parameters derived from EchoGuard specs, RACK Architecture v3.0, ATP 3-37, ATP 3-01.81*
