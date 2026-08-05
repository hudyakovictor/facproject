# UI v4.3

## Single-row thumbnails

Each pose panel renders photographs in exactly one horizontal row. A monotonic deconfliction layout preserves chronological order and shifts close records to the right so cards never overlap. Thumbnail size remains continuous from 30×30 to 150×150 px. Thumbnails contain only the image; anomalies stay in their own track.

## Readability

The minimum practical font sizes for controls, rulers, metric labels, settings, JSON and data-management tables were raised to 10–13 px, with primary headings at 24–30 px.

## Per-photo upload validation

The Settings page accepts multiple files and produces an independent checklist for every returned `photo_id`:

- backend storage;
- Stage 1 timeline record;
- one of nine pose bins;
- quality threshold;
- confidence threshold;
- smile threshold/detection;
- jaw-open threshold/detection;
- 106 landmarks;
- 134 landmarks;
- face mask;
- UV texture;
- texture JSON;
- BFM mesh;
- active skin zones.

Statuses are `Проходит`, `Не проходит`, `Ожидает`, or `Нет данных`. Missing Stage 1 outputs are never reported as a successful zero. Each photo can be rechecked after extraction and opened in Photo Lab.
