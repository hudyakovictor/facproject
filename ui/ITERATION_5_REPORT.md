# Iteration 5 — Policy-driven Readiness Engine (80/20 core)

Implemented the high-leverage decision core before approval UI polish.

## Delivered
- eight evidence dimensions: implementation, unit, synthetic, integration, real_photo, calibration, docs, observability;
- policies: utility, critical_stage1, calibration, evidence, visual_only;
- gate logic without arithmetic averaging;
- explicit statuses from discovered through release_ready/failing;
- calibration cannot become green after unit-only success;
- synthetic is explicitly contract/regression evidence, not forensic accuracy;
- visual-only policy does not require forensic dimensions;
- blocker propagation without falsely marking dependants as failed;
- deterministic snapshots keyed by function fingerprints;
- `/api/readiness` and readiness-aware `/api/canvas`;
- node inspector with policy, explanation, missing dimensions and blockers.

## Real app6 result
447 functions: 367 implemented_unverified, 67 calibration_required, 10 release_ready, 2 synthetic_verified, 1 experimental. These are engineering readiness states, not identity conclusions.

## Verification
37/37 backend tests; 65/65 app6 regression; 6/6 frontend syntax; app6 unchanged.

Overall readiness: 34/100. Manual approval editor/import wiring is deliberately deferred; stale-hash-safe engine input and config schema exist.
