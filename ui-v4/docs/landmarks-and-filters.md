# UI v4.4 — quality, authenticity, expression and aligned LDM shifts

## New timeline filters/tracks

The per-pose metric menu now includes backend-sourced fields only:

- quality status and score;
- authenticity status and score;
- expression magnitude;
- jaw-open degree, detected flag and ratio;
- smile detected flag;
- a combined `Aligned LDM 106 + 134` adjacent-pair track.

Status/boolean values use categorical blocks rather than misleading interpolated lines. Missing fields are gray and never converted to zero. `Authenticity` is labeled as a source field and is not calculated by the UI.

## Combined landmark shift track

For each adjacent pair in the selected pose, the UI loads real pair metrics and renders two compact blocks: LDM106 and LDM134. Colors are controlled by `settings.landmark_shift`:

- green: value ≤ tolerance;
- orange: tolerance < value ≤ suspect;
- red: value > suspect;
- gray: backend did not provide the metric.

The tooltip names both photo IDs and exact values. The track explicitly marks thresholds as calibrated or diagnostic.

## Photo Lab

Photo Lab includes separate LDM106 and LDM134 tabs with `raw`, `aligned`, and `original` spaces, a point plot and numeric XYZ table. Chronology is shown from the real `info.json` chronology section.

The optional backend patch exposes only allowlisted landmark files through `/api/v1/photos/{id}/landmarks/{106|134}/{raw|aligned|original}`.
