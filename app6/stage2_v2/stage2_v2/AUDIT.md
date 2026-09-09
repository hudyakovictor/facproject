# Stage 2 audit - what was broken and why

Static analysis over 197 Python files / 28 731 LOC in `app6`, plus a manual read
of the Stage 2 core (`engine.py`, `core.py`, `loaders.py`, `analysis_policy.py`).
The project has no syntax errors: `python -m compileall app6 uv_module` passes.
Everything below is a logic, contract or architecture defect.

## 1. Critical logic bugs

### 1.1 Every pair was silently marked `quality_limited`
`stage2` read the global texture score from
`info.json -> quality_summary.global_texture_quality`. Stage 1 never writes that
key. It writes `texture.json -> quality.score`. The lookup used a `.get(..., 0.0)`
style default, so the score was always `0.0`, always below the `0.35` floor, and
**every pair in every run carried the `quality_limited` flag**. No error, no log
line. This one key silently degraded the evidence class of the entire dataset.

*Fixed:* `contract.TEXTURE_QUALITY_PATH` names the real location, and the loader
fails loudly if a declared contract field is absent instead of defaulting.

### 1.2 `evidence_state` was overwritten
In `engine.py` the pair evidence state is assigned, then later reassigned in a
branch that does not consider the earlier value. A pair that had already been
downgraded (for example `date_provenance_limited`) could be silently promoted
back. Evidence limits must accumulate, never replace.

*Fixed:* limits are a set that only ever grows over the life of a pair.

### 1.3 `MIN_ALIGNMENT_QUALITY` defined three times
`analysis_policy.py`, `engine.py` and `chronology.py` each declared it. Editing
one had no effect on the paths that imported another. Worse, D-003 established
that `alignment_quality` is uncorrelated with the residual (Spearman +0.096 over
212 frames, versus -0.176 in the atlas), so the gate should not be active at
all - but one of the three copies still gated.

*Fixed:* one parameter, `min_alignment_quality`, plus an explicit
`alignment_quality_gates` switch defaulting to off with the finding recorded as
its provenance.

### 1.4 Hard-coded threshold inside a loop
`engine.py` defined `POSE_LEAKAGE_DISTANCE_THRESHOLD = 1.0` *inside* the pair
loop, invisible to configuration and re-created on every iteration.

*Fixed:* `pose_leakage_distance_threshold` in the registry.

### 1.5 `ZONE_WEIGHTS` duplicated with different content
`core.py` declares `ZONE_WEIGHTS` at line 449 and again at line 518. The second
shadows the first, so the first is dead code that still reads as authoritative.
Anyone editing the wrong one changes nothing.

### 1.6 Thresholds accepted but never passed
`_pair_qc_decision` takes threshold arguments, but `engine.py` calls it without
them, so it silently used its own defaults. The call site and the signature had
drifted apart.

*Fixed:* gate functions take a `Params` object; there is no default to drift to.

### 1.7 Three silent `except` blocks
`api/server.py:293`, `stage2/core.py:47`, `stage2/texture_image.py:65` swallow
exceptions without logging. In an evidence pipeline a swallowed exception is
indistinguishable from a negative result.

## 2. Contract and packaging defects

### 2.1 Five broken imports
| File | Import |
|---|---|
| `stage1/assets.py:109` | `uv_module` |
| `stage1/masks.py:79` | `util.io` |
| `stage1/reconstruction.py:100` | `face_box` |
| `stage1/reconstruction.py:101` | `model.recon` |
| `test_module/test_a11_artifacts.py:15` | `tools.rebuild_landmark_utility` |

These resolve only when the 3DDFA_V3 vendor tree is on `sys.path` by side
effect. On any other machine they raise `ModuleNotFoundError`.

### 2.2 Untestable by construction
Stage 2 could not run without ~421 MB of weights, a mounted archive at
`/Volumes/SDCARD/storage` and calibration photos. So it was never exercised in
CI, which is the root cause that let 1.1-1.6 survive.

*Fixed:* `fixtures.py` writes a Stage 1 tree that satisfies the contract exactly,
from a deterministic synthetic face, with an optional injected change of known
magnitude at a known date in known landmarks. Stage 2 is now testable on a
laptop with nothing but numpy.

### 2.3 Configuration scattered across ~60 modules
Roughly 80 thresholds lived as module-level constants in 50+ files. There was no
way to see the effective configuration of a run, diff two runs, or validate a
setting before a multi-hour job.

*Fixed:* `params.py` - 83 declared parameters in 12 groups, each with type,
bounds, unit, default, blast radius and the reasoning behind the default.

### 2.4 38 unused imports, 0 duplicate definitions at module scope
Cosmetic, but indicative of code that grew by accretion.

## 3. What is preserved exactly

The Stage 1 contract is frozen in `contract.py` and was reverse-engineered from
`stage1/validator.py`, `stage1/storage.py` and `stage1/config.py`:

* `main_timeline.csv` with `photo_id, date, same_date_sequence, pose_bin`
* per photo: `info.json`, `validation.json`, `reconstruction.npz` required;
  `texture.json`, `quality_zones.npz`, `face_mask.npz`, `uv.npz`,
  `ldm106_raw.csv`, `ldm134_raw.csv` optional
* `MESH_COUNT = 35709`, `TRIANGLE_COUNT = 70789`, packbits length 4464
* the 9 pose bins, byte-for-byte the same boundaries as `stage1/config.py`
* all 20+ required NPZ arrays, names and shapes unchanged
* `validation.json -> status == "complete"` remains the admission rule

Stage 1 needs no modification and its output is consumed unchanged. The 33
Stage 2 output artifact filenames are also preserved so Stage 2B and Stage 3
keep working.

## 4. Status

Delivered and verified running:

* `contract.py` - frozen Stage 1 contract
* `params.py` - 83-parameter registry with validation, hashing, profiles, diff
* `admin_server.py` + `admin_ui.html` - the admin panel
* `fixtures.py` - synthetic Stage 1 generator

Still to port from legacy (the measurement core; the scaffolding above is what
makes porting it safe): `geometry.py`, `gates.py`, `noise.py`, `stats.py`,
`pipeline.py`, `report.py`. See `README.md` for the intended shape of each.

## 5. Not verifiable in this environment

No network, and `scipy`, `pytest`, `fastapi` are absent; the model weights,
calibration photos and the `/Volumes/SDCARD/storage` runtime are not in the
archive. So the legacy test suite (~50 tests in `app6/test_module`) could not be
run, and no real Stage 1 data was available. Everything reported above is from
static analysis plus reading the code; the new package was verified by running
it against the synthetic fixture. Re-verify locally with
`/Users/victorkhudyakov/work/.venv/bin/python`.
