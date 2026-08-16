# AGENTS / SKILL / CLAUDE — 25-факторная проверка

**Дата:** 2026-08-05  
**Объект:** `AGENTS.md`, `SKILL.md`, `CLAUDE.md`, scoped `app6/AGENTS.md`, изменения `README.md` и `ui-v5/README.md`.

Метод оценки определён в `SKILL.md`: 25 факторов × 4 балла = 100. Production-quality target — ≥98 и отсутствие P0-нарушений.

| ID | Балл | Evidence |
|---|---:|---|
| Q01 Fidelity to request | 4 | Зафиксированы выбранный стек, M1 path и три agent guide файла |
| Q02 Real-data grounding | 4 | Запрет production mocks, обязательный artifact/schema mapping |
| Q03 Provenance | 4 | Source/date/run/schema/reviewer requirements во всех workflows |
| Q04 Entity semantics | 4 | Photo/pair/event/interval/run/private hypothesis разделены |
| Q05 Scientific invariants | 4 | 9 bins, raw space, Kabsch, visibility, FDR, return policy закреплены |
| Q06 Calibration rigor | 4 | LOPO/contamination/main-data tuning/systematic-shift boundaries |
| Q07 Confounders | 4 | Pose, quality, expression, visibility, duplicate/source domain |
| Q08 Missing-data honesty | 4 | null/NaN/excluded/inapplicable ≠ 0 |
| Q09 Forensic wording | 4 | Candidate/cluster/hypothesis не превращаются в verdict |
| Q10 Privacy/security | 4 | Private/public split, auth/RBAC/path/upload/on-chain boundaries |
| Q11 Architecture fit | 4 | Root `app6` canonical; nested backend не получает новую scientific logic |
| Q12 Types/contracts | 4 | OpenAPI-generated client, Pydantic, strict TS, versioned schema |
| Q13 Visual hierarchy | 4 | Timeline/pair/morph/clustering design synthesis закреплён |
| Q14 Contextual controls | 4 | Overlay controls, display/scientific distinction, audit scope |
| Q15 Timeline invariant | 4 | Одна X на photo; pair/event/interval typed separately |
| Q16 Nine-pose workflow | 4 | Один bin default и полный canonical order/policy |
| Q17 Scale/performance | 4 | 1900 photos, Canvas/virtualization/worker и 35k GPU vertices |
| Q18 Apple M1 compatibility | 3 | Архитектура CPU extraction vs WebGL2 GPU корректна; реальный M1 benchmark ещё не выполнен |
| Q19 Accessibility | 4 | Keyboard/focus/non-color/Canvas alternative/reduced motion/zoom |
| Q20 Tests | 3 | Relative-link check и `git diff --check` пройдены; markdown lint/CI ещё не настроены |
| Q21 Determinism | 4 | Stable ordering, no random production result, fingerprints/versioning |
| Q22 Observability | 4 | Error/empty/limited/progress/SSE/context-loss/degraded requirements |
| Q23 Reversibility | 4 | Immutable Stage 1, preview/undo/migrations/audit trail |
| Q24 Documentation | 4 | Root/scoped guides, root/UI README и ссылки синхронизированы |
| Q25 Delivery evidence | 4 | Файлы, ограничения, проверки и P0 status зафиксированы |

## Результат

```text
TOTAL: 98/100
P0 violations: none
Deductions:
- Q18 −1: нужен performance/capability benchmark на реальном MacBook M1.
- Q20 −1: нужен автоматический markdown/link lint в CI.
```

## Выполненные проверки

- все relative Markdown links в новых/изменённых guide files существуют;
- `git diff --check` — PASS;
- сумма весов основной 19-факторной UI rubric — 100;
- case-only duplicate filenames не создавались, что важно для стандартного case-insensitive APFS на macOS.

## Следующие действия для 100/100

1. После появления runnable UI v5 выполнить Chrome + Safari M1 WebGL2 benchmark и context-loss test.
2. Добавить Markdown lint и relative-link checker в CI.
