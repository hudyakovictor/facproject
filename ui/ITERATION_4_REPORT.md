# Iteration 4 — Pipeline Canvas 80/20 core

## Decision
The iteration deliberately prioritised the hard architectural 20% that unlocks most user value: stable graph semantics, large-graph layout, source-linked journalist nodes, confidence-aware edges, semantic zoom and safe local layout persistence. Cosmetic controls and minor interactions are deferred.

## Delivered
- deterministic backend canvas DTO for stage/module/function/artifact nodes;
- confirmed versus heuristic call and artifact edges;
- presets for Full, Stage1, Geometry, Calibration, Evidence, Testing and Blockers;
- React Flow dark canvas with ELK layered layout, minimap, fit, pan, zoom and selection;
- semantic zoom that removes expensive detail at overview scale;
- journalist-first titles with technical names, status text and badges;
- color-independent accessible node labels and keyboard focus;
- safe atomic layout store constrained to `ui/.data/layouts`;
- restored and exposed status/test/catalog/source APIs plus new canvas/layout APIs.

## Deferred low-leverage polish
Collapse animation, full command palette, segmented readiness bars, runtime-observed rings and wiring the save-layout button. Backend persistence and graph contracts are already in place.

## Verification
- backend: 32/32 PASS;
- app6 regression: 65/65 PASS;
- frontend syntax: 6/6 PASS;
- deterministic graph, 500+ node scale and safe persistence tests: PASS;
- app6 source unchanged.

Overall readiness: 28/100.
