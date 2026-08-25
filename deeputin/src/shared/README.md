# Shared contract layer

`contracts.ts` is the single vocabulary for page IDs, semantic block definitions, source references, measurement states, limitations and evidence contexts.

Every `BlockDefinition` lists `elements` owned by one self-contained feature. These elements may include its controls, filters, views, inspectors, captions, legends, source context, limitations and actions.

`PageBlueprint.tsx` renders the page purpose and semantic blocks without choosing columns, widths, heights or a permanent panel arrangement. `PlaceholderBlock.tsx` presents the same empty state and contract on every page.

A visual block may be replaced without changing its page-level `BlockDefinition`, ownership boundary or source-key vocabulary. Data adapters preserve `source_mode: research`, `not_a_verdict: true`, canonical coordinate spaces and explicit limitation/status fields. The renderer intentionally contains no source data, calculations or verdict logic.
