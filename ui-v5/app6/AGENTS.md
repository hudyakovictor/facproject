# app6/AGENTS.md — scoped backend rules

Сначала прочитать [`../AGENTS.md`](../AGENTS.md) и [`../SKILL.md`](../SKILL.md). Этот файл уточняет правила только для `app6/` и не отменяет корневые инварианты.

## Scope

`app6` — канонический scientific/backend source:

- Stage 1 — immutable extraction artifacts;
- Stage 2 — calibrated pair/chronology measurements;
- Stage 2B — private corroboration/retest;
- Stage 3 — report/publication artifacts;
- API — typed read/write boundary для UI.

Новая scientific logic не должна жить в backend-копии внутри UI-директории; единственный source of truth — корневой `app6`.

## Stage 1

- Один `net_recon` inference на фото.
- Дата main dataset — filename authority.
- Все eligible inputs учитываются как success/failure/exact duplicate.
- Photo output публикуется атомарно только после validation.
- Resume проверяет source/code/config/model compatibility.
- Raw/object-normalized/identity-only/visualization spaces называются явно.
- Missing artifact не заменяется пустым массивом или zero score.
- UI/filter/job не мутирует завершённый Stage 1 root.

Изменение Stage 1 schema требует полного re-extract либо explicit migration; старые и новые rows не смешиваются.

## Stage 2

- Primary: raw object-normalized + trimmed Kabsch, no scale.
- Pair: same pose bin + axis-specific gate + visibility intersection.
- Min points и calibration coverage публикуются.
- Quality/expression/provenance limitation влияет через явно выбранную policy: gate, stratification или downgrade. Комментарий и код должны совпадать.
- FDR и effective number of tests сохраняются.
- Main chronology не используется как скрытый calibration training set.
- Pair planner deterministic.
- Every excluded/skipped pair имеет reason.
- Cluster/hypothesis computation не добавляется в core score без method decision.

## Stage 2B/private

- Private input fail-closed и opt-in.
- Prior overlap не называется independent confirmation.
- Legacy threshold/posterior не переиспользуется как current truth.
- Output не импортируется Stage 3/public API.
- Retest status сохраняет pending/inconclusive, если current data недостаточно.

## Stage 3/public

- Observation отдельно от interpretation.
- `not_a_verdict` обязателен.
- Public safety lint блокирует build при unsupported assertive statements.
- Private fields и raw private hypotheses не экспортируются.
- JSON/CSV — source of truth; HTML/PDF/Markdown — representation.
- Missing/excluded отображаются явно.
- Stage 2 создаёт `journalist_handoff.json` с denominators/evidence refs.
- Stage 3 создаёт plain-language, technical, skeptical и machine-review drafts из одного claims ledger.
- Method explainer не зависит от результатов основного расследования.
- Редакционная правка не может усилить `candidate` без нового evidence/review.
- Каждый draft помечен как human-review-required и входит в digest manifest.
- Полный контракт: `docs/PUBLICATION_PIPELINE.md`.

## API

- Новый endpoint получает Pydantic request/response model, schema version и tests.
- Research endpoint не имеет synthetic fallback.
- 404/409/422 различаются по смыслу.
- Все filesystem mutations проверяют path containment.
- GET не мутирует evidence.
- Heavy mesh data передаётся compressed/binary, когда контракт будет мигрирован.
- OpenAPI diff синхронизируется с UI types.
- Private/write API не публикуется через public read-only deployment.

## macOS M1

- Stage 1 CPU — текущий baseline.
- Не включать MPS без parity tests и renderer verification.
- Browser WebGL2 morphing относится к UI, а не к Python device policy.
- Не добавлять CUDA-only assumption в общие contracts.

## Required verification

Минимум для backend diff:

```bash
python -m compileall -q app6
python -m pytest -q app6/test_module app6/api/tests
```

Scientific change дополнительно требует scenario/calibration/determinism evidence согласно `../SKILL.md`.

Перед завершением выполнить 25-факторный self-review. Production-ready claim разрешён только при ≥98/100 и отсутствии P0 violations.
