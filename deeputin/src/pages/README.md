# Page ownership and implementation rule

Each file in this directory is a top-level page blueprint. The initial registry has exactly seven files:

- `Timeline.tsx` — Archive Explorer, Timeline Map and selection journal;
- `PhotoDetail.tsx` — overview/artifacts, pose/quality and landmarks/surface;
- `Compare.tsx` — Pair Detail/data-first, visual comparison/Morphing and zones/evidence;
- `Research.tsx` — Zone Atlas, Casework, Corroboration and motion/persistence review;
- `Methodology.tsx` — pipeline/quality/gates, calibration/metrics and integrity;
- `Report.tsx` — Run Summary/evidence and narrative/sources/export;
- `Publications.tsx` — authoring, Evidence Map and reader/QA/export.

A page file owns only:

- the page purpose and primary question;
- the ordered list of semantic blocks required by the specification;
- each block's complete `elements`, data-key comments and source references;
- the boundary of one feature and its controls, views, context, limitations and actions.

The current implementation replaces every registered block with a page-owned detail renderer. Each renderer keeps its controls, source request, visualization/table, measurement gates, limitation context, empty/error state and permitted actions together. The shared `PageBlueprint` remains compatible with an empty block for any future contract item that is not yet implemented.

Data is requested only from the calculated API/artifact endpoints listed by the corresponding block. A response is never replaced with a mock fallback; missing fields and unavailable artifacts remain explicit. Deep links may carry the selected photo or pair without creating additional routes.

Do not add `Upload`/`Ingestion`, fixture rows, fake metrics, fake photographs, inferred verdicts or placeholder data. The interface visualizes data calculated outside this runtime.
