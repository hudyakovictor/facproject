# Validation against known ground truth

Everything below was produced by running this pipeline on synthetic data whose
answer was known in advance, using `app6.stage2_v2.fixtures`. The fixture
injects a displacement of known size, at known landmark indices, after a known
date. That makes it possible to ask the only question that matters about a
detector: does it find what is there, and does it stay quiet about what is not?

These are not reassuring results, and they are recorded in full because the
failures are more useful than the successes.

## Experiment 1 - global residual, 2 photos per day

Fixture: 36 photos, 6 dates, 3 pose bins, per-day 2, 1 percent displacement
at landmarks 60-76 after 2012-03-05.

Result: 45 pairs measured, 45 scored, 0 significant.

The injected change was real, present, and completely missed. Worse, the
cross-date pairs spanning the change scored negative z values, several below
-4, meaning their residuals were smaller than same-day noise.

Diagnosis: the global RMSE averages over all 134 landmarks. A change confined
to 17 of them moves that average by almost nothing. This is not a threshold
that needs tuning; averaging dilutes a localised change by construction, and
no cut-off on the diluted number can recover it.

Consequence: per-zone scoring was added, each zone against its own same-day
null, with zone tests corrected in their own family.

## Experiment 2 - zone scoring, 2 photos per day

Fixture: unchanged from experiment 1.

Result: 2 pairs flagged, both in zone brow_ridge_L, at q = 9e-04 and q = 1e-05.

Both were false positives, and confidently so:

| | Ground truth | Reported |
|---|---|---|
| Interval | after 2012-03-05 | 1999-2003, and 1999-2022 |
| Zone | ligament_orbital_L (14/14 overlap) | brow_ridge_L (0 overlap) |

The 1999-2003 interval contains no injected change whatsoever. The zone that
did contain the change was not flagged at all. So the run produced a false
positive in the wrong zone and the wrong decade, a false negative in the right
one, and attached q-values that looked authoritative.

Diagnosis: the zone null was built from 6 same-day pairs and produced
mad_sigma = 9e-05 against a median of 4.8e-03 - a scale roughly 2 percent of
its own median. MAD over 6 points is a very unstable scale estimate and
collapses by chance. Dividing by a collapsed sigma manufactures large z from
nothing. The original min_reference_pairs = 5 permitted this.

Consequence: three guards, all exposed as tunable parameters rather than
buried constants.

- min_zone_reference_pairs (20) - a zone null below this yields no p-value.
- sigma_confidence_percentile (84) - score against an upper percentile of a
  bootstrapped sigma, not the point estimate, so uncertainty in the scale
  enters the score conservatively.
- min_sigma_to_median_ratio (0.05) - refuse a sigma implausibly small next to
  its own median, the signature of a collapsed estimate.

## Experiment 3 - guards active, 2 photos per day

Fixture: unchanged.

Result: all 6 zone nulls refused as insufficient_reference (n = 6 < 20). Zone
FDR skipped. 0 findings.

This is the correct behaviour. With two photos per day there is not enough
same-day data to know what the method's own error looks like, so no claim is
possible in either direction. The pipeline now says that instead of inventing
a number.

## Experiment 4 - guards active, 8 photos per day

Fixture: 144 photos, per-day 8, giving 28 same-day pairs per date per bin,
above the floor of 20. Same 1 percent injection after 2012-03-05.

Result: 6 usable zone nulls, 50 zone tests, 1 pair flagged:
2012-03-05 -> 2017-11-21, zone orbit_L, z = 3.25, q = 0.029.

Mixed, and the split matters.

- Dating: correct. The flagged interval is exactly the injection boundary.
  None of the other intervals fired. The change was placed in the right place
  in time.
- Zone attribution: wrong. orbit_L fired; the injection sits in
  ligament_orbital_L (14/14 overlap) and cheekbone_L (3/12). A neighbouring
  zone was blamed.

Diagnosis: alignment is global and rigid. A displacement at 17 landmarks
perturbs the whole fit, and the residual redistributes into adjacent zones.
Point count aggravates it: ligament_orbital_L has 14 landmarks against 29 in
orbit_L, so leaked residual lands preferentially where there are more points
to average over.

## What this validation establishes

1. The method can date a change. On adequately powered data it put the change
   in the correct interval and stayed quiet elsewhere.
2. The method cannot attribute a change to a specific anatomical zone. It
   named an adjacent zone. Any sentence of the form "the change is in the
   orbital ligament" is not supported by this pipeline, and the draft
   generator must not produce one.
3. Statistical power is a hard precondition, not a nice-to-have. The same code
   on the same signal produced a confident false positive at 2 photos per day
   and a correct date at 8. Same-day photo density, not total photo count, is
   the binding constraint.
4. A q-value from this pipeline means nothing without checking the n behind
   its null. Experiment 2 reported q = 1e-05 for pure noise.

## Reproducing

    python -m app6.stage2_v2.fixtures /tmp/fx --per-day 8 --change 0.01 \
        --change-after 2012-03-05
    python -m app6.stage2_v2.cli run --stage1 /tmp/fx --output /tmp/out \
        --profile default --report --synthetic

To reproduce the false positive of experiment 2, set
min_zone_reference_pairs = 5, sigma_confidence_percentile = 50, and
min_sigma_to_median_ratio = 0.0, and rebuild the fixture with per-day 2. That
combination is preserved as a warning, not as a usable profile.

## Not validated

Everything here uses a synthetic face built from an ellipsoid with Gaussian
noise. It shares no properties with real photographic error: no compression
artefacts, no lighting variation, no expression, no reconstruction failure, no
mis-dating. These experiments test the statistics, not the reconstruction, and
certainly not the pipeline's behaviour on real photographs. Nothing here
licenses a claim about any real person.
