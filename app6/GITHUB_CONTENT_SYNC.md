# Синхронизация контента с GitHub — отчёт
Дата: 2026-07-22 · Ветка: `arena/019f89cd-facproject`

## Проверено (fetch всех refs)
| Источник на GitHub | Содержание | Действие |
|---|---|---|
| PR #4 `arena/019f88e2-facproject` (MERGED) | squash-коммит `c5b7834` = **только патч 01/27** (патчи 02–27 никогда не пушились — «все изменения локальные») | весь остальной контент восстановлен из `app6/PR.md` и запушен нашей веткой (коммит `ba323f8`) |
| PR #3 `arena/019f8624` (MERGED) | app7 rewrite | входит в линию pr4; отличий от нашего дерева нет |
| PR #1 `arena/019f7783` (MERGED) | uv_module Ultra v3.2 | входит в линию pr4; отличий от нашего дерева нет |
| PR #2 `arena/019f8451` (CLOSED) | глубокий аудит + 4 audit-скрипта + документы | контент-архив принят в `FINAL_REPORTS/` (13 файлов); бинарный zip не включён |

## Древо-сверка `origin/pr4 → HEAD`
Единственный недостающий файл: **`app6/README_SKIN_V3.md`** (правила skin-пайплайна v3: A20/S40/W14/Q) — терялся при переименовании в `PR.md` в коммите `4912d67`. **Восстановлен** из `origin/pr4`.

## pose_policy_v3_9bins.csv
Три версии сверены: наша == вмерженная (origin/pr4). Версия из закрытого PR #2 отличается только CRLF-окончаниями строк — наша версия авторитетна, не заменялась (CSV используется `stage1/skin/pipeline.py`).

## Принятый контент из закрытого PR #2 (rapports, не код)
- `FINAL_REPORTS/AUDIT_DEEP/` — DEEP_AUDIT_REPORT.md, FINAL_BRIEF.md (контракты артефактов, pose-логика, left/right симметрия, preview-vs-numeric)
- `FINAL_REPORTS/ANALYST_PREPARATION/` — AUDIT_ANALYST_REPORT.md, METRIC_GAPS.md (пробелы метрик: skin fingerprint, wrinkle_stability, chronology_normalization, identity_score), ZONE_ATLAS_MAP.md
- `FINAL_REPORTS/PROJECT_PREPARATION/` — CHRONOLOGY_SETUP.md, 9_ANGLES_SCHEME.md, DATASET_STRUCTURE.md, TEST_200_SELF.md
- `FINAL_REPORTS/PIPELINE_AUDIT/` — check_projection.py, check_metrics_identity.py, check_zone_coverage.py, check_profile_zones.py (компилируются ✓)

## Открытые доработки, выявленные в принятых документах (не регрессии, а feature-gaps)
1. Нет «отпечатка кожи» (skin fingerprint / individual profile) — метрика-агрегат для идентификации.
2. Нет `wrinkle_stability_score` (стабильность морщин между фото).
3. Нет `chronology_normalization` для кожных признаков (временное сглаживание).
4. Нет `identity_score` / same_person_probability как итоговой метрики.
5. Preview-рендеры шире numeric evidence (визуально можно неверно интерпретировать покрытие).
6. Различающееся определение domain между модулями (geometry/support/evidence слои) — требуется единый словарь (см. DEEP_AUDIT §2.2).
