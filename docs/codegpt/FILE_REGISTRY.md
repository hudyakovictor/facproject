# File Registry — итерация «Release Gates» (обновлено глубоким анализом 2026-08-03)

Статусы: P=planned, G=generated, V=verified. Обновляется после каждой генерации.

## Python — тесты и инструменты
| Файл | Назначение | Зависит от | Статус |
|---|---|---|---|
| app6/api/tests/test_health_timeline.py | health/timeline/photos endpoints | server.py | P |
| app6/api/tests/test_compare_mesh.py | compare, full_mesh, compare/upload | compare.py, bfm_topology | P |
| app6/api/tests/test_jobs_settings_data.py | jobs, settings, data/clear | jobs.py, settings.py | P |
| app6/api/tests/test_calibration_noise.py | calibration health/match/subtract_noise | calibration.py, noise_calibration | P |
| app6/api/tests/test_report_ui_fields.py | report, run/summary, ui_fields, info_keys | report.py | P |
| app6/api/tests/test_upload_provenance.py | upload/delete, безопасность имён, провенанс | server.py | P |
| app6/api/tests/test_portability.py | фиксация ER-131/132: settings/upload/jobs на Linux-путях | settings.py, server.py | P |
| app6/api/tests/conftest.py | фикстуры: tmp-корни, клиент, синтетические записи | — | P |
| tests/e2e_fixture/build_synthetic_stage1.py | генерация детерминированного синтетического Stage1 | schemas | P |
| tests/e2e_fixture/build_synthetic_stage2.py | синтетический analysis_manifest + пары | stage2 контракты | P |
| tests/e2e_fixture/snapshot_check.py | сравнение golden snapshots API/report/export | — | P |
| tests/determinism/run_twice.py | двойной прогон + hash quartet сравнение | e2e_fixture | P |
| tools/public_term_lint.py | FORBIDDEN_PUBLIC_TERMS по JSON/CSV/HTML/print | — | P |

## Портируемость API (IT-9) — целевые файлы
| Файл | Назначение | Зависит от | Статус |
|---|---|---|---|
| app6/api/settings.py | _settings_path: env-first (DEEPUTIN_PROJECT_ROOT), fallback runs/; параметр project_root больше не мёртвый | — | P |
| app6/api/server.py | дефолты uploads/jobs/clear через env + runs/; _require_removable_output с DEEPUTIN_STORAGE_ROOT | settings.py | P |
| app6/run_calibration.py | DEFAULT_OUTPUT env-first | — | P |

## Калибровочный адаптер (IT-4b)
| Файл | Назначение | Зависит от | Статус |
|---|---|---|---|
| app6/stage2/loaders.py | load_calibration_from_info_json(): info.json + normalization → Record | — | P |
| tools/build_calibration_index.py | генерация all_calibration_index.csv из sidecar-датасета | loaders | P |
| app6/test_module/test_calibration_adapter.py | 943 Records, 7 персон, 9 бинов, координаты = raw-normalized | loaders | P |

## UI
| Файл | Назначение | Зависит от | Статус |
|---|---|---|---|
| ui-v3/package-lock.json | воспроизводимая установка | package.json | P |
| ui-v3/src/lib/api.ts | fix fetchRunKeys → run/artifacts | — | P |
| ui-v3/src/pages/RunPage.tsx | согласование с контрактом | api.ts | P |
| ui-v3/src/test/*.test.tsx | базовые vitest-тесты страниц v3 | страницы v3 | P |
| ui-v3/vitest.config.ts | vitest setup | vite.config.ts | P |

## Чистка ссылок/дрейфа (IT-8)
| Файл | Назначение | Зависит от | Статус |
|---|---|---|---|
| app6/scripts/project_readiness.py | реальный entry (compileall, pytest, ui build, веса) — закрывает ER-141 | — | P |
| 3ddfa_v3/3DDFA-V3 (gitlink) | удалить gitlink+симлинк; код уже вендорен в 3ddfa_v3/ | git | P |
| 3ddfa_v3/atlas/pose_policy_v3_9bins.csv | удалить устаревшую копию (канон — app6/atlas) | — | P |
| app6/stage3/engine.py | narrative из manifest/metric_catalog — закрывает ER-144 | metric_registry | P |
| app6/CONVENTIONS.py | актуализация (raw primary, без run_skin_stage1) | — | P |
| docs/final/02, 05 | per-bin yaw gate 2–12° + производные pitch/roll — закрывает ER-137 | — | P |

## CI и документация
| Файл | Назначение | Зависит от | Статус |
|---|---|---|---|
| .github/workflows/gates.yml | pytest, ruff, ui-v2/v3, lint, determinism, calibration harness | все выше | P |
| README.md | актуализация путей/команд; «основное место» atlas | — | P |
| docs/final/00_README.md | снять устаревшее утверждение про UI | — | P |
| docs/codegpt/*.md | реестры CodeGPT | — | G (эти файлы) |

## Файлы проекта, которые НЕ меняются в итерации (существующие, verified)
app6/test_module/* (87 зелёных), app6/api/* (кроме settings/server в IT-9), ui-v2/* (248 зелёных),
docs/final/* (кроме 02/05/00), tools/acceptance_*.py, 3ddfa_v3/{model,util,face_box} (вендор), uv_module/*.

## Приватный слой (IT-18)
| Файл | Назначение | Зависит от | Статус |
|---|---|---|---|
| app6/private_hypothesis_seed/* | Замороженный снимок seed (ledger+retest+README), изолирован от Stage3/API | — | V (данные), 🔄 (governance) |
| app6/stage2/private_hypothesis.py | Ретест приватных гипотез; интеграция legacy_bridge в _retest_record | legacy_bridge | P |
| app6/stage2/legacy_bridge.py | Нормализация bin/photo_id legacy→current (сейчас мёртвый код) | naming.parse_photo_name | P |
| app6/stage2/leads.py | load_leads/pair_leads (lead_registry) | — | P |
| app6/stage2b/engine.py | Corroboration statuses; fail-closed; переименование «prior_overlap_strong» | leads | P |
| app6/run_stage2b.py | CLI; fail-closed при отсутствии prior-root | stage2b.engine | P |
| app6/test_module/test_private_hypothesis.py | retest-ветки, candidate_keys, manifest | private_hypothesis | P |
| app6/test_module/test_leads_bridge.py | leads load/pair, bridge bin-map, normalize_photo_id | leads, legacy_bridge | P |
| app6/test_module/test_stage2b.py | statuses, fail-closed, изоляция от Stage3 | stage2b.engine | P |