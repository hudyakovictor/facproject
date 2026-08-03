# Production UI — strict research mode

This build contains no generated research dataset and never substitutes unavailable pipeline artifacts.

Required backend behavior:
- `/api/v1/timeline` must return `source_mode: research`; any other mode is rejected.
- Stage 1 image/detail/mesh endpoints must resolve every timeline photo id.
- Stage 2 pair/run endpoints and Stage 3 report endpoints remain authoritative.

Failure policy: missing network, artifact, schema, geometry, calibration or report is displayed as unavailable. No scientific value is synthesized by the UI.
