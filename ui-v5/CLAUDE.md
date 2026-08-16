# CLAUDE.md — project instructions for Claude Code

## Authority

Read and follow in this order:

1. `AGENTS.md` — repository constitution;
2. scoped `AGENTS.md`, if present;
3. `SKILL.md` — implementation and 25-factor quality workflow;
4. `README.md` and relevant `docs/final/*`;
5. this file — Claude-specific execution guidance.

If instructions conflict, preserve scientific/provenance/safety invariants and ask only when the ambiguity changes the result materially.

## Project summary

DEEPUTIN is a longitudinal face-analysis workstation using 3DDFA_V3, Python/FastAPI and a React UI. It organizes an archive across nine fixed pose bins, extracts reusable Stage 1 artifacts, performs calibrated Stage 2 pair/chronology analysis, creates Stage 3 reports, and supports a quarantined private hypothesis retest layer.

The system presents technical observations. It does not automatically identify a person or prove a theory.

## Target UI

- `ui-v5/screens/` contains design references.
- `ui-v5/` is the only target implementation area.
- Do not redesign by blindly copying one screenshot. Follow `docs/UI_V5_COMPLETE_IMPLEMENTATION_SPEC.md` and the synthesis in `docs/UI_V5_RENDER_REVIEW_19_FACTORS_2026-08-05.md`.
- Do not duplicate the Python pipeline inside `ui-v5`.

Target stack is fixed in `README.md` and `ui-v5/README.md`.

## First actions for every task

1. Run `git status --short --branch`.
2. Locate applicable instructions and source files.
3. Search existing code before proposing a new abstraction.
4. Identify source artifact/schema for every displayed field.
5. Distinguish current behavior from planned behavior.
6. Write a short plan for multi-file or scientific changes.
7. Preserve user changes; never reset unrelated work.

## Repository handling

- Never commit weights, photos, runtime outputs, `.venv`, `node_modules`, build output or credentials.
- Large local files may exist on the owner’s Mac but not in the checkout. Say “not present in this checkout,” not “does not exist.”
- Do not follow or rewrite absolute local symlinks as if portable.
- Do not modify vendored 3DDFA source merely for style.
- Treat backend copies nested under UI directories as removable legacy; canonical scientific logic and new routes belong to root `app6`.
- Use uppercase `AGENTS.md`, `SKILL.md`, `CLAUDE.md`; these names are tool conventions and avoid duplicate case-only files on default macOS APFS.

## Data discipline

For every field rendered or exported, be able to answer:

```text
Which artifact?
Which schema/version?
Which entity type?
Which coordinate space?
Which pose/applicability gate?
Which calibration?
What does missing mean?
Can it enter public output?
```

If any answer is unknown, implement an honest unavailable/limited state instead of a guessed value.

## Scientific invariants

Do not change without explicit method work:

- nine pose bins;
- filename-authoritative date policy;
- raw object-normalized primary geometry;
- trimmed Kabsch without scale;
- same-bin/axis pose applicability;
- visibility intersection;
- null/NaN semantics;
- FDR 0.05;
- calibration/LOPO/contamination boundary;
- absolute return floor;
- private hypothesis isolation;
- `not_a_verdict` public wording.

Do not infer identity from cluster labels, texture diagnostics or threshold exceedance.

## UI v5 execution rules

### Architecture

- React components do not own scientific calculations.
- TanStack Query owns server state.
- Zustand owns transient workspace state.
- URL owns shareable pose/range/run selection.
- Backend profiles/manifests own scientific settings.
- IndexedDB/local storage owns only UI preferences/cache.

### Timeline

- One active pose by default.
- One temporal viewport transform shared by every layer.
- One photo means one X-coordinate.
- Pair, event and interval are separate typed entities.
- DOM for controls/focus/visible thumbnails.
- Canvas for dense metrics/events/bridges.
- Worker for aggregation/geometry.
- Avoid large SVG trees and off-viewport thumbnails.

### Pair analysis

- Keep A/B selection, range, reference frames and applicability visible.
- Use a virtualized multirow thumbnail browser.
- Identify metric/run/calibration behind any similarity tint.
- Red means threshold state, never “different person.”

### Morphing on MacBook M1

Distinguish Python extraction from browser rendering:

- extraction remains CPU unless MPS is separately validated;
- frontend morphing uses Apple GPU via browser WebGL2/Three.js;
- use BufferGeometry and shader interpolation;
- update a uniform, not vertex arrays in React on each frame;
- WebGPU may be progressive enhancement, never the only path;
- show capability/context-loss/software-fallback states;
- interpolated frames are visualization-only.

### Clustering

- Production clustering runs in Python backend.
- UI renders versioned artifacts and sensitivity results.
- Chronology is default; embedding is secondary; cloud is optional.
- Always display `cluster ≠ identity`.

### Hypotheses

- Private-only.
- Do not fabricate the three-entity mapping if source data does not define it.
- Systematic shift is sensitivity analysis, not agreement optimization.
- Show legacy/current/migration/coverage/uncertainty separately.

### Publication drafts

- Generate a Stage 2 journalist handoff and Stage 3 multi-audience bundle.
- Keep general, technical, skeptical and machine-review layers synchronized through claim IDs.
- Every number keeps denominator and evidence refs.
- Method explanations are independent of investigation results.
- Do not optimize prose for persuasion; optimize for traceability, falsifiability and understandable accuracy.
- Never strengthen candidate status in prose.
- Public-figure examples are method demonstrations only and require rights/provenance.
- AI review does not replace independent human review.
- Follow `docs/PUBLICATION_PIPELINE.md`.

## API work

- Prefer Pydantic response models for new contracts.
- Add version/schema and explicit state.
- Generate/update TypeScript types from OpenAPI.
- Add contract tests for success, missing, malformed and limited cases.
- Keep heavy geometry binary/compressed where possible.
- Use SSE for one-way job progress unless bidirectional streaming is required.
- Validate filesystem containment for all mutations.
- Never expose private/write APIs as public read-only endpoints.

## Testing expectations

Run the smallest relevant set first, then the required gate.

Python baseline:

```bash
python -m compileall -q app6
python -m pytest -q app6/test_module app6/api/tests
```

UI v5 once runnable:

```bash
cd ui-v5
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npm run test:e2e
```

For UI changes, add or update:

- component/unit test;
- MSW contract fixture where necessary;
- Playwright interaction test;
- screenshot for material design changes;
- axe check for new dialogs/controls.

Do not say tests pass unless they were run in this session. Report exact command and result.

## Editing style

- Prefer small cohesive modules.
- Use strict types and discriminated unions.
- Do not introduce `any` at API boundaries.
- Keep scientific names exact; add a human label separately.
- Preserve `None`/null rather than coercing.
- Avoid speculative abstraction before two real uses.
- Comment why a forensic constraint exists, not what a line of code does.
- Update docs when behavior/contract changes.
- Add a decision record for architecture or method changes.

## Tool use

- Use search/grep before broad file reads.
- Do not read large binaries into context.
- Do not run full Stage 1/2 against local datasets unless explicitly requested.
- Do not start long-lived servers with a one-shot shell command.
- Stop preview processes when no longer needed.
- For screenshots, inspect all relevant references, not only one favorite.
- For current external facts, cite authoritative sources; project behavior must come from repository/tests.

## Communication

Default language with the owner: Russian.

A completion message should be concise but include:

1. implemented behavior;
2. files changed;
3. tests and results;
4. data/source contract;
5. limitations or external prerequisites;
6. 25-factor score for substantial deliverables.

Do not overstate readiness. Separate:

- code complete;
- tests complete;
- real-data validation complete;
- external review complete.

## Definition of ready

Before saying “готово”:

- run relevant tests;
- inspect diff/status;
- verify no secret/weight/runtime files;
- verify null/error/limited states;
- verify private/public boundaries;
- verify accessibility and target M1 path for UI rendering;
- complete `SKILL.md` 25-factor self-review;
- require ≥98/100 and no P0 violations for production-ready language.
