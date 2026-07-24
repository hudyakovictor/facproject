# Unified development gates

`test_module` now contains two layers in one gate:

1. **Synthetic prerequisites** based on `assets/face_model.npy` — asset topology, nine pose bins, exact rotation recovery, visibility-mask roundtrip, rigid alignment, same/different synthetic identity separation, and chronology edge contracts.
2. **Real-photo scenarios** — the existing 21 scenarios × 5 person variants.

Synthetic results are numerical regression checks only. They are not real-photo accuracy estimates and must not set forensic thresholds. UV is checked only for rendering/correspondence compatibility and is excluded from Stage 2 evidence.

## Gate levels

- `smoke`: synthetic prerequisites + the smallest real-photo scenario only (`S20_minimal_pair_v00`). This level is automatically enforced by low-level stage entry points while development gates are enabled.
- `quick`: synthetic prerequisites + P1 real scenarios, variant `v00` only.
- `stage`: synthetic prerequisites + all five variants of P1 scenarios. `run_gated_pipeline.py` uses this level.
- `release`: synthetic prerequisites + all 105 scenarios.

## Commands

Run from `/Users/victorkhudyakov/work` with the project interpreter:

```bash
PY=/Users/victorkhudyakov/work/.venv/bin/python

$PY -m app6.test_module.runner synthetic
$PY -m app6.test_module.runner gate --stage stage1 --run --level quick
$PY -m app6.test_module.runner gate --stage stage2 --run --level smoke
$PY -m app6.test_module.runner gate --stage stage2 --run --level quick
$PY -m app6.test_module.runner gate --stage stage2 --run --level stage
$PY -m app6.test_module.runner gate --stage stage2 --run --level release
```

## Temporary pipeline integration

`run_stage1.py`, `run_stage2.py`, `run_stage2b.py`, and `run_stage3.py` call `pipeline_guard.enforce_stage()` before starting. Test subprocesses set `APP6_TEST_CONTEXT=1`, preventing recursive gates.

The switch is `app6/test_module/gate_policy.json`:

```json
{"enabled": true, "auto_level": "quick"}
```

When development acceptance is complete, disable the temporary guards by changing only:

```json
{"enabled": false}
```

Emergency one-run bypass:

```bash
APP6_DEV_GATES=0 $PY app6/run_stage2.py ...
```

The bypass must not be used for production evidence runs.

## Required preparation for real scenarios

```bash
$PY -m app6.test_module.runner pool
$PY -m app6.test_module.runner gen
$PY -m app6.test_module.runner build --all
$PY -m app6.test_module.runner cache --run --device cpu
```

The checker now fails rather than passing vacuously when a required pair, FDR population, or pair table is absent. Explicit source groups in corroboration scenarios are preserved.
