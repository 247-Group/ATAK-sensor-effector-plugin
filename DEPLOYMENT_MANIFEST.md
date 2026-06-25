# RACK FP Plugin — Sprint 1 Deployment Manifest

**Epic**: RPDT-6 | **Parent Task**: RPDT-17 | **Sprint**: Sensor & Effector Sprint 1
**Date**: 2026-06-23 | **Engineer**: Mike Pendleton

---

## Artifact Inventory

| # | Artifact | Path | Status |
|---|----------|------|--------|
| 1 | ThreatEvent JSON Schema | `schemas/threat_event.schema.json` | Complete |
| 2 | CapabilityManifest JSON Schema | `schemas/capability_manifest.schema.json` | Complete |
| 3 | Synthetic Threat Generator | `pipeline/synthetic_threat_generator.py` | Complete |
| 4 | Schema Validation Utility | `pipeline/schema_validator.py` | Complete |
| 5 | GPU Environment Verifier | `pipeline/verify_env.py` | Complete |
| 6 | ONNX Edge Export Pipeline | `pipeline/export_to_edge.py` | Complete |
| 7 | TensorRT Optimization Script | `scripts/optimize_tensorrt.sh` | Complete |
| 8 | Venus Server Setup Script | `scripts/setup_venus.sh` | Complete |
| 9 | Synthetic Dataset (Parquet) | `data/synthetic/threat_events.parquet` | Generated |
| 10 | Synthetic Dataset (JSONL) | `data/synthetic/threat_events.jsonl` | Generated |
| 11 | Sprint 1 AI/ML Technical Omnibus | `docs/SPRINT1_AI_ML_OMNIBUS.md` | Complete |

---

## Data Contract Schemas

### ThreatEvent (`schemas/threat_event.schema.json`)

- **Standard**: JSON Schema Draft 2020-12
- **Required fields**: 14 (event_id, sensor_id, sensor_type, track_id, bearing_deg, range_m, altitude_m_agl, velocity_mps, heading_deg, radar_cross_section_m2, track_age_s, track_confidence_0_1, timestamp_utc, raw_payload)
- **Extended fields**: 11 (threat_class, threat_score, lat, lon, elevation_deg, cot_type, sensor_modality, detection_zone, frequency_mhz, signal_strength_dbm)
- **Threat classes**: 7 (air_uas_small, air_fixed_wing, ground_vehicle, ground_personnel, benign_wildlife, benign_aircraft, unknown)
- **Sensor types**: 9 (echodyne_echoguard, mcq_ranger, bosch_ptz, bulzi_zscout, dft_fiber, jcew_drak, weartak, spotd, synthetic)

### CapabilityManifest (`schemas/capability_manifest.schema.json`)

- **Required fields**: 4 (plugin_id, display_name, available_actions, current_status)
- **Pre-defined actions**: 7 (issue_fp_alert, slew_camera, redirect_uas, escalate_fpcon, cue_rws, generate_coa, dispatch_qrf)
- **Human Gate actions**: 3 (escalate_fpcon, cue_rws, dispatch_qrf)

---

## Synthetic Data Pipeline

### Generation Parameters

| Parameter | Value |
|-----------|-------|
| Events per class | 5,000 (configurable, `--per-class`) |
| Total events | 30,000+ |
| Threat classes | 6 |
| Random seed | 42 (deterministic, `--seed`) |
| Noise sigma | 7.5% (configurable, `--noise`) |
| Output formats | Parquet + JSONL |

### Physics-Based Parameters

| Class | RCS (m2) | Altitude (m AGL) | Velocity (m/s) | Sensors |
|-------|----------|-------------------|----------------|---------|
| air_uas_small | 0.001-0.05 | 5-400 | 0-30 | radar, RF, visual |
| air_fixed_wing | 1-100 | 100-5,000 | 30-150 | radar, visual |
| ground_vehicle | 5-100 | 0-3 | 0-40 | radar, seismic, visual |
| ground_personnel | 0.3-2.0 | 0-2 | 0-8 | radar, seismic, RF, visual |
| benign_wildlife | 0.001-0.5 | 0-200 | 0-25 | radar, seismic, visual |
| benign_aircraft | 10-500 | 1,000-12,000 | 80-260 | radar, visual |

### CLI Commands

```bash
# Generate full dataset (30K events, Parquet + JSONL)
python pipeline/synthetic_threat_generator.py \
  --output data/synthetic/threat_events.parquet \
  --per-class 5000 --seed 42 --json-export

# Validate existing dataset
python pipeline/synthetic_threat_generator.py \
  --output data/synthetic/threat_events.parquet \
  --validate-only

# Extended dataset (60K events)
python pipeline/synthetic_threat_generator.py \
  --output data/synthetic/threat_events_extended.parquet \
  --per-class 10000 --seed 42 --json-export
```

---

## Test Suite

### Test Files and Counts

| File | Tests | Coverage |
|------|-------|---------|
| `tests/test_synthetic_generator.py` | 25 | Event generation, physics bounds, class balance, noise, reproducibility, Parquet round-trip |
| `tests/test_schema_validator.py` | 21 | JSON schema validation, batch validation, physics bounds |
| `tests/test_physics_bounds.py` | 30 | Speed of sound, biological limits, ground entities, aircraft physics, RCS consistency, coordinates |
| `tests/test_edge_export.py` | 8 | Feature/class constants, ONNX export, ORT inference, batch inference |
| **Total** | **84** | |

### Run Tests

```bash
cd rack-fp-plugin

# All tests
python -m pytest tests/ -v

# Physics bounds only
python -m pytest tests/test_physics_bounds.py -v

# Schema validation only
python -m pytest tests/test_schema_validator.py -v

# With coverage
python -m pytest tests/ -v --cov=pipeline --cov-report=term-missing
```

---

## Edge Deployment Pipeline

### ONNX Export

```bash
# Export MLP threat classifier to ONNX
python pipeline/export_to_edge.py --model-type mlp --output models/threat_classifier.onnx

# Export XGBoost classifier (Sprint 2)
python pipeline/export_to_edge.py --model-type xgboost --output models/threat_classifier_xgb.onnx
```

### TensorRT Optimization (on target device)

```bash
# FP16 (recommended for Jetson Nano)
bash scripts/optimize_tensorrt.sh models/threat_classifier.onnx --fp16

# INT8 (maximum speed, requires calibration)
bash scripts/optimize_tensorrt.sh models/threat_classifier.onnx --int8

# Benchmark
trtexec --loadEngine=models/tensorrt/threat_classifier_fp16.trt \
        --shapes=features:1x10 --iterations=1000
```

### Target Performance

| Platform | Precision | Target Latency | Kill Chain Budget |
|----------|-----------|---------------|-------------------|
| L40S (lab) | FP32/FP16 | <1ms | N/A (training) |
| Jetson Orin NX | FP16 | <10ms | IDENTIFY: 5-15s |
| Jetson Nano | FP16/INT8 | <500ms | IDENTIFY: 5-15s |

---

## Venus Server Setup

### Discovery (read-only)

```bash
# SSH to venus and run discovery
ssh venus.247grp.net
bash scripts/setup_venus.sh discover
```

### Full Setup (requires root)

```bash
sudo bash scripts/setup_venus.sh setup
bash scripts/setup_venus.sh verify
```

### Setup Actions

1. Disable NVMe swap (anti-pattern with 1TB RAM)
2. Configure firewall (Ollama restricted to 10.247.4.3 + localhost)
3. Optimize 9p mounts with `cache=mmap`
4. Create/configure Python venv at `/opt/venv/ml-rack`
5. Install Sprint 1 + Sprint 2 ML dependencies
6. Verify GPU (L40S) and CUDA 12.x

---

## Schema Validation Utility

```python
from pipeline.schema_validator import (
    validate_threat_event,
    validate_capability_manifest,
    validate_events_batch,
    validate_physics_bounds,
)

# Single event
errors = validate_threat_event(event_dict)

# Physics bounds (beyond schema)
issues = validate_physics_bounds(event_dict)

# Batch
results = validate_events_batch(list_of_events)
# -> {"total": 30000, "valid": 30000, "invalid": 0, "errors": []}
```

---

## Directory Structure

```
rack-fp-plugin/
  schemas/
    threat_event.schema.json          # ThreatEvent data contract
    capability_manifest.schema.json   # CapabilityManifest data contract
  pipeline/
    synthetic_threat_generator.py     # Physics-based synthetic data generator
    schema_validator.py               # JSON Schema + physics validation
    verify_env.py                     # GPU environment verification
    export_to_edge.py                 # ONNX export for Jetson/PACSTAR
  scripts/
    optimize_tensorrt.sh              # TensorRT FP16/INT8 optimization
    setup_venus.sh                    # Venus server provisioning
  tests/
    test_synthetic_generator.py       # Generator + physics + reproducibility
    test_schema_validator.py          # Schema validation + physics bounds
    test_physics_bounds.py            # Comprehensive physics assertions
    test_edge_export.py               # ONNX export + ORT inference
    conftest.py                       # Test configuration
  data/synthetic/
    threat_events.parquet             # 30K+ labeled events (columnar)
    threat_events.jsonl               # 30K+ labeled events (streaming)
  models/                             # ONNX + TensorRT artifacts (Sprint 2+)
  docs/
    SPRINT1_AI_ML_OMNIBUS.md          # Full technical omnibus
  DEPLOYMENT_MANIFEST.md              # This file
```

---

## Beyond-Spec Deliverables

| Requirement | Spec | Delivered | Delta |
|-------------|------|-----------|-------|
| Threat classes | 4 | **6** (+ 2 benign) | +50% |
| Events per class | 5,000 | **5,000+** (configurable to 10K+) | Exceeds |
| Output format | Parquet | **Parquet + JSONL** | Dual format |
| Noise model | "Add noise" | **Physics-based Gaussian (7.5% sigma, configurable)** | Physics-bound |
| Test suite | Not specified | **84 tests** (physics, schema, export, reproducibility) | N/A |
| Reproducibility | Not specified | **Seeded RNG** (deterministic output) | N/A |
| Edge deployment | Future sprint | **ONNX export + TensorRT scripts** | Sprint ahead |
| Schema validation | Not specified | **JSON Schema + physics bounds validator** | N/A |
| Server setup | Manual | **Automated scripts** (discover/setup/verify) | N/A |
| Benign classes | Not specified | **Wildlife + authorized aircraft** | False-positive rejection |
| Kill chain timing | Not specified | **max_response_time_s** in CapabilityManifest | Integrated |

---

*Generated 2026-06-23 | AI Cowboys | RACK FP Plugin Sprint 1*
