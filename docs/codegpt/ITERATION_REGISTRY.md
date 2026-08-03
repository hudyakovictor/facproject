# Iteration Registry — DEEPUTIN «Release Gates» (обновлено глубоким анализом 2026-08-03)

| Итерация | Цель | Требования | DoD |
|---|---|---|---|
| IT-0 | Baseline: venv, тесты, аудит состояния | R-G01, R-G02 | pytest 87/87, ruff-профиль зафиксирован, реестры созданы |
| IT-1 | API runtime tests всех 36 маршрутов | R-D01, R-D02, R-D04, R-D05 | app6/api/tests зелёный, критичные пути покрыты; тесты ловят ER-131/132/134 |
| IT-2 | ruff = 0 в app6 | R-G01 | `ruff check app6` без ошибок, compileall pass |
| IT-3 | ui-v3 воспроизводимость + контракт + тесты | R-E02, R-E03, R-E05, R-E07, R-D07 | package-lock.json, tsc, build, vitest зелёные; run/keys исправлен |
| IT-4 | Golden synthetic E2E fixture + snapshot | R-E06, R-G05, R-C04 | 9 bins, конфликты, NULL, step, return; snapshot API/report/export |
| IT-4b | Калибровочный адаптер info.json→Record + индекс | R-B06, R-B07, R-B08 | 943 Records, calibration health 200, harness LOPO/contamination в CI |
| IT-5 | Public-term lint на финальных артефактах | R-F01…R-F03 | JSON/CSV/HTML/print pass; блокирует publication build |
| IT-6 | Determinism harness | R-G04 | два прогона → одинаковые hash quartet |
| IT-7 | CI (GitHub Actions) все gates | R-G03 | workflow зелёный на push; nightly real E2E по secrets (опционально) |
| IT-8 | Документация и «мёртвые ссылки» | R-G06, R-G07, R-G08, R-G09, R-G10 | README/docs/CONVENTIONS актуальны; gitlink удалён; narrative из данных; docs согласованы с per-bin gate |
| IT-9 | Портируемость API-дефолтов | R-D05, R-D06 | все маршруты отвечают на Linux без env-хаков; settings персистентны в runs/ |

Порядок: IT-0 → IT-1 → IT-2 (независимы после IT-0) → IT-3 → IT-4 → IT-4b → IT-5 → IT-6 → IT-7 → IT-8 → IT-9.
IT-9 может идти параллельно IT-1 (тесты фиксируют баги, IT-9 их закрывает).
После каждой итерации обновляются все реестры и Context Capsule.

## Итерации, добавленные по итогам 100 пунктов ТЗ-листа
| Итерация | Цель | Пункты ТЗ-листа | DoD |
|---|---|---|---|
| IT-10 | Statistical rigor: FDR↔evidence, empirical null, freeze OP, ESS/cluster, event units | I01, I02, I03, I05, T01, T02, T03, T04, T10, U10 | тесты порогов, единый operating point, ESS в API/отчёте |
| IT-11 | UV/visibility: backface=0, angle_threshold, coverage-gated valid, confidence cross-frame, symmetry, raw texture, test suite | R01, R02, R03, R08, R09, S01, S02, S06, S09, R07 | UV test suite зелёный; visibility-инварианты |
| IT-12 | Security/auth: DELETE traversal, auth, bind, upload magic bytes, retention | L01, L02, K04, X03, ER-170/171/182 | OWASP-чек, auth-тесты, audit-лог |
| IT-13 | Data integrity: assets hash manifest, hash-pinned downloader, BFM cache hash, index hashes, immutable snapshots | C02, C04, X04, Q10, G10, X03 | hash-манифест в CI, golden bundle immutable |
| IT-14 | Evidence semantics: vocabulary, prior policies, evidence elevation rules, calibration=true, settings validation | K03, M05, AA01, K07, Y01, X06, Y03, Z10, W05 | lint и policy-тесты; no fabricated flags |

## Изменения по решению пользователя (2026-08-03)
- IT-11 (UV) — ОТМЕНЕНА (CD-124): UV только визуализация; анализ кожи по face_mask.png.
- IT-13 — сокращена: остаются C01 (calibration bundle) и C03 (portable CPU renderer); hash-части (C02/C04/X04/Q10) отменены (CD-122).
- Из плана удалены: C02, C04, C05, D02, E04, Q01, Q02, Q10, R01-R03, R07-R09, S01-S02, S06, S09, X01, X02, X04.
- Добавлены:
  | IT-15 | UI-P0: 3D-инспектор, workspace пары, рендер данных, настройки-форма, починка RunPage | UI-1…UI-5 | v3 зелёный (tsc+build+vitest), RunPage работает |
  | IT-16 | UI-P1: таймлайн v2-класса, analytics-режимы, noise calibration, provenance, upload, data management | UI-6…UI-11 | страницы v3 отрендерены, JSON в advanced |
  | IT-17 | UI-P2: ErrorBoundary, хоткеи, i18n/theme, статус пайплайна, candidate-легенда, глобальный поиск | UI-12…UI-16 | a11y-гейт, i18n ru/en |

## IT-18 — Приватный слой гипотез (private_hypothesis_seed) — ДОБАВЛЕНА
| Итерация | Цель | Файлы | DoD |
|---|---|---|---|
| IT-18 | Полный охват приватного слоя: интеграция legacy_bridge, тесты retest/leads/stage2b, управление seed, формулировки AA01/AA02, guard изоляции | private_hypothesis.py, legacy_bridge.py, leads.py, stage2b/engine.py, run_stage2b.py, test_module/test_private_hypothesis.py, test_module/test_stage2b.py, test_module/test_leads_bridge.py, .gitignore, private_hypothesis_seed/README_PRIVATE.md | ER-190…195 закрыты; тесты зелёные; seed изолирован от Stage3/API (guard-тест); status «prior_overlap_strong»; fail-closed prior-root |
