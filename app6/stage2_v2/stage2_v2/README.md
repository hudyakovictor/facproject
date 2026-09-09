# stage2_v2 - rebuilt Stage 2

A replacement for `app6/stage2` that consumes **exactly the same Stage 1 output**
and produces **exactly the same artifact filenames**, but with one source of
truth for configuration, an admin panel, and the ability to run without model
weights.

See `AUDIT.md` for the list of bugs this replaces.

## Quick start

```bash
cd /path/to/project            # the directory that contains app6/

# 1. Generate a synthetic Stage 1 tree (no weights, no photos needed)
python -m app6.stage2_v2.fixtures /tmp/fixture_s1 --per-day 2 --change 0.01

# 2. Open the admin panel against it
python -m app6.stage2_v2.admin_server \
    --profiles ./stage2_profiles \
    --stage1 /tmp/fixture_s1 \
    --port 8770
# then open 127.0.0.1:8770 in a browser
```

Against real data, point `--stage1` at your Stage 1 output root
(`/Volumes/SDCARD/storage/stage1`).

## The admin panel

Stdlib `http.server` only - no FastAPI, no uvicorn, no pip install. It runs
anywhere Python 3.11+ runs, including CI and a bare venv.

The UI is **generated from the parameter registry**. Declaring a new `ParamSpec`
in `params.py` is the only step needed to expose it in the panel, with its
bounds, unit, default, blast radius and rationale.

| Feature | What it does |
|---|---|
| Grouped parameter editor | All 83 parameters in 12 groups, each showing bounds, default, unit, impact tag and *why* the default is what it is |
| Live validation | Server-side, through the identical code path the pipeline uses, so the UI cannot save something the pipeline would reject |
| Diff panel | Every deviation from defaults, colour-coded by blast radius, with a warning when a change invalidates an existing checkpoint |
| Derived values | Shows computed quantities such as the pitch and roll budgets implied by `max_yaw_gap_deg` |
| Profiles | Named JSON profiles on disk, plus built-in `default`, `strict_evidence`, `exploratory`, `fast_smoke` |
| Stage 1 survey | Reads the index and `validation.json` only, so it stays fast on thousands of photos; reports incomplete records and missing files |
| Dry run | *The reason this panel exists.* Answers "if I tighten the yaw gate, how much data do I lose?" before committing to a multi-hour job. Reports planned pairs per pose bin and any blocking condition, such as an unusable temporal axis |
| Config identity | `hash` for the full config, `resume_hash` for only the parameters that invalidate a checkpoint |

HTTP API, if you prefer to script it or mount it inside the existing FastAPI app
(`app6/api`) - it is plain JSON in, JSON out:

```
GET    /api/registry            the full parameter registry
GET    /api/profiles            list profiles
GET    /api/profiles/{name}     load one
POST   /api/profiles/{name}     save one   {values, notes}
DELETE /api/profiles/{name}     delete one
POST   /api/validate            {values} -> {valid, errors, hash, derived, diff}
POST   /api/diff                {left, right | values}
GET    /api/stage1?root=...     survey a Stage 1 output tree
POST   /api/dry-run             {values | profile, stage1_root}
GET    /api/health
```

## Design rules

1. **One source of truth.** Every threshold is a `ParamSpec` in `params.py`.
   No module-level magic numbers. This is what makes the admin panel possible
   and what prevented the three-way `MIN_ALIGNMENT_QUALITY` split from recurring.
2. **The Stage 1 contract is data, not folklore.** `contract.py` declares every
   file, field and array Stage 2 reads. Guessing a key name - the bug that
   silently marked every pair `quality_limited` - is now impossible.
3. **Fail loudly or fail closed, never fail silently.** A missing contract field
   is an error on that record, not a `0.0` default. Missing QC excludes a photo
   rather than assuming it is good.
4. **Errors are per record.** One bad photo is recorded and skipped with a
   reason; it cannot abort a run.
5. **Evidence limits accumulate.** They are a growing set, never reassigned, so
   a downgraded pair cannot be silently promoted.
6. **Every decision is explainable.** A gate records the parameter value that
   produced its verdict.
7. **Runnable without the world.** `fixtures.py` means the stage is testable
   with nothing but numpy.

## Files

| File | Status | Purpose |
|---|---|---|
| `contract.py` | done | Frozen Stage 1 output contract: files, fields, NPZ keys, pose bins, mesh constants |
| `params.py` | done | 83-parameter registry: validation, cross-checks, hashing, profiles, diff |
| `admin_server.py` | done | Admin HTTP server, Stage 1 survey, dry-run planner |
| `admin_ui.html` | done | Self-rendering admin UI |
| `fixtures.py` | done | Synthetic Stage 1 generator with optional injected change |
| `AUDIT.md` | done | Bug audit |
| `loader.py` | to port | Strict Stage 1 reader; collects per-record violations instead of raising |
| `geometry.py` | to port | Trimmed Kabsch (no scale), zonal residuals, metrics - pure numpy |
| `gates.py` | to port | Pose, expression, quality, visibility, same-day gates, all `Params`-driven |
| `noise.py` | to port | Equal-person median-of-quantiles calibration model |
| `stats.py` | to port | BH / BY FDR, bootstrap CI, z and p approximations without scipy |
| `pipeline.py` | to port | Orchestrator; writes the same 33 artifact filenames |
| `report.py` | to port | Artifact writers |

## Porting the measurement core

The scaffolding above is deliberately first, because it is what makes porting
the rest safe. For each legacy module:

1. Replace every module-level constant with a `ParamSpec` lookup. If it is not
   in the registry yet, add it there first.
2. Read Stage 1 through `contract.py` names only.
3. Return a result object carrying the reason and the parameter value behind
   every verdict, rather than mutating shared state.
4. Add a fixture test: build a synthetic tree with a known injected change and
   assert the module finds it, and that it finds nothing when the injected
   magnitude is zero.

`scipy` is not required anywhere - the legacy code only used it for statistics
that are a few lines of numpy (BH/BY step-up, MAD-based robust z, normal tail
approximations).

## Notes on the environment

Built and verified against the synthetic fixture with numpy 2.5.2 on Python
3.13. Not verified against real Stage 1 data: the archive contains no model
weights, no calibration photos and no `/Volumes/SDCARD/storage` runtime, and
`scipy` / `pytest` / `fastapi` were unavailable, so the legacy suite in
`app6/test_module` could not be run. Re-verify locally with
`/Users/victorkhudyakov/work/.venv/bin/python`.
