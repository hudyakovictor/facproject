# Selected patch decisions

- Primary geometry is `object-normalized raw`; chronology/aligned arrays are diagnostic only.
- `alignment_quality` is descriptive pending renewed calibration and is not silently used as a release gate.
- Temporal detectors run only on a validated evidence time axis.
- Legacy H0/H1/H2 posteriors are quarantined and cannot enter current evidence.
- Texture and UV remain secondary visualization channels unless a separate validation promotes them.
- Hard-negative validation is holdout-only and never tunes thresholds.
