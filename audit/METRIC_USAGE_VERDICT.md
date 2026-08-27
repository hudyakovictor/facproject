# DEEPUTIN — Вердикт: какие метрики реально нужны

**Дата:** 2026-08-27  
**Метод:** grep по всему app6/ — где вычисляется, где потребляется, что сломается

---

## ИТОГ: из 100 метрик

```
  ┌────────────────────────────────────────────────────┐
  │ 82 НЕОБХОДИМЫ ─ используются в вычислениях/gates   │ ████████████████
  │  6 МОЖНО УДАЛИТЬ ─ 0 потребителей                  │ █
  │ 12 МОЖНО АГРЕГИРОВАТЬ ─ дублируют другие           │ ██
  └────────────────────────────────────────────────────┘
```

---

## ❌ 6 МЕTRIK МОЖНО УДАЛИТЬ (0 реальных потребителей)

| # | Метрика | Семья | Почему можно удалить |
|---|---------|-------|---------------------|
| 1 | **ldm106_max** | landmark | Только в metric_registry. Нигде не читается |
| 2 | **ldm134_max** | landmark | Только в metric_registry. Нигде не читается |
| 3 | **angle_noise_ldm134_rmse** | pair | 0 упоминаний ВЕЗДЕ — даже не вычисляется |
| 4 | **angle_noise_ldm106_rmse** | pair | 0 упоминаний ВЕЗДЕ — даже не вычисляется |
| 5 | **ldm106_anchor_count** | landmark | Только записывается в row. Нигде не читается |
| 6 | **descriptor_landmark_fraction** | descriptor | Только записывается. Нигде не читается |

**Экономия:** -6 метрик, -6 полей в CSV, -6 записей в каталоге.

---

## ⚠️ 12 МЕТРИК МОЖНО АГРЕГИРОВАТЬ (дублируют другие)

| # | Метрика | Дублирует | Предложение |
|---|---------|-----------|-------------|
| 7 | ldm106_median | ldm106_rmse | Объединить в `ldm106_summary` |
| 8 | ldm106_p95 | ldm106_rmse | Объединить в `ldm106_summary` |
| 9 | ldm134_median | ldm134_rmse | Объединить в `ldm134_summary` |
| 10 | ldm134_p95 | p95_point_z (z-score) | Уже есть z-score, raw p95 дублирует |
| 11 | common_visible106 | common_visible134 | Оставить только 134 (суперсет) |
| 12 | coverage106 | coverage134 | Оставить только 134 |
| 13 | ldm134_alignment_trimmed_count | alignment_policy | policy уже описывает |
| 14 | alignment106_trimmed_count | alignment_policy | policy уже описывает |
| 15 | alignment134_residual_before_median | alignment_policy | diagnostically only |
| 16 | alignment134_residual_after_median | alignment_policy | diagnostically only |
| 17 | mesh_alignment_residual_before_median | mesh_anchor_fraction | diagnostically only |
| 18 | mesh_alignment_residual_after_median | mesh_anchor_fraction | diagnostically only |

**Экономия:** -12 отдельных полей → +3 агрегированных = -9 net.

---

## ✅ 82 МЕТРИКИ НЕОБХОДИМЫ (реально используются)

### Критические (12) — определяют status:

| # | Метрика | Где потребляется | Что сломается без неё |
|---|---------|-----------------|----------------------|
| 1 | p95_point_z | motion.score(), persistence, change_points, UI | Status не определён |
| 2 | significant_point_fraction | motion.score(), UI | Status не определён |
| 3 | coherent_motion_fraction | motion.score(), change_points | Status не определён |
| 4 | descriptor_significant_fraction | descriptor.score(), persistence | Descriptor upgrade не работает |
| 5 | descriptor_p95_z | descriptor.score() | Descriptor z-score |
| 6 | descriptor_top_families | UI, lead_pairs | Журналист не видит что изменилось |
| 7 | chronology_rate_z | chronology, change_points | Темп не определён |
| 8 | chronology_rate_status | chronology→status upgrade | Rapid/persistent не определяется |
| 9 | cross_bin_support_pose_count | corroboration, change_points | Corroboration не работает |
| 10 | evidence_state | change_points, Stage 3 | Отчёт не строится |
| 11 | status | ВСЕ | Система не работает |
| 12 | days_delta | chronology, UI, narrative | Хронология не работает |

### Ограничивающие (8):

| # | Метрика | Где потребляется | Что сломается |
|---|---------|-----------------|---------------|
| 13 | quality_limited | evidence_state() | quality_limited не определяется |
| 14 | calibration_limited | evidence_state(), engine.py | calibration_limited не определяется |
| 15 | pose_leakage_limited | evidence_state(), engine.py | pose_leakage не определяется |
| 16 | date_provenance_limited | evidence_state() | date_conflict не определяется |
| 17 | near_duplicate_pair | evidence_state() | duplicate gate не работает |
| 18 | quality_texture_score_a/b | quality_limited computation | quality gate не работает |
| 19 | matched_calibration_sets | calibration_limited, UI | calibration coverage |
| 20 | expression_influence | evidence, narrative | expression context |

### Системные (62) — обеспечивают работу pipeline:

| Группа | Кол-во | Зачем нужны |
|--------|-------:|-------------|
| **ldm134_rmse/p95** | 2 | PRIMARY_CALIBRATION_METRICS, angle_noise, pose_leakage |
| **identity_only_ldm134_rmse** | 1 | PRIMARY_CALIBRATION_METRICS, angle_noise |
| **identity_only_motion_rmse** | 1 | expression_influence, pose_leakage |
| **alpha_id/exp_l2** | 2 | alpha_chronology, evidence |
| **alpha_id/exp_robust_z** | 2 | calibration |
| **mesh_rmse/p95/point_to_plane** | 3 | mesh calibration, mesh_score |
| **mesh_max_robust_z** | 1 | mesh calibration, persistence |
| **mesh остальные** | 14 | mesh calibration, mesh_zones, mesh_shape |
| **primary_robust_z** | 1 | evidence, change_points |
| **baseline_return_*** | 4 | baseline_return module |
| **cross_bin_independent_source** | 1 | corroboration, evidence |
| **biological_rate_z** | 1 | chronology, narrative |
| **pose_distance** | 1 | calibration, pose_leakage, evidence, angle_noise |
| **same_day** | 1 | chronology |
| **pair_index** | 1 | chronology sorting, checkpoint |
| **common_visible134** | 1 | evidence (min 60 check) |
| **angle_noise_uncompensated** | 1 | evidence alternative_reasons |
| **texture_image_status** | 1 | evidence visualization_only |
| **texture_pair_status** | 1 | evidence, texture_pair |
| **texture_image_usable_zone_count** | 1 | evidence |
| **descriptor_status/top_counts** | 2 | persistence, lead_pairs |
| **median/significant_point_count** | 2 | motion summary |
| **quality/calibration internal** | 8 | stratum, gate, visibility |
| **expression internal** | 5 | gate, mimiс control |

---

## 📊 ИТОГОВАЯ ТАБЛИЦА

| Категория | Было | Удалить | Агрегировать | Оставить |
|-----------|-----:|--------:|-------------:|---------:|
| Критические | 12 | 0 | 0 | **12** |
| Ограничивающие | 8 | 0 | 0 | **8** |
| Информативные | 10 | 0 | 0 | **10** |
| Визуализация (texture) | 19 | 0 | 0 | **19** |
| Служебные | 51 | 6 | 12 | **33** |
| **ИТОГО** | **100** | **6** | **12** | **82** |

**Чистый результат:** 100 → 82 метрики (−18, или −18%).

---

## ⚠️ ЧТО НЕЛЬЗЯ УДАЛЯТЬ (даже если кажется лишним)

| Метрика | Кажется лишней | На самом деле |
|---------|---------------|---------------|
| ldm134_rmse | "Есть же p95_point_z" | PRIMARY_CALIBRATION_METRICS + angle_noise + pose_leakage |
| ldm106_rmse | "Есть же ldm134" | angle_noise COMPENSABLE_METRICS + UI spec |
| pose_distance | "Есть же pose_bin" | Calibration distance guard + pose_leakage + evidence |
| same_day | "Есть же days_delta" | chronology same_day_structural_conflict detection |
| mesh_p95 | "Есть же mesh_rmse" | mesh calibration (отдельный noise model) |
| common_visible134 | "Служебная" | evidence: min 60 check → alternative_reasons |

---

## 🎯 РЕКОМЕНДАЦИЯ

1. **Удалить 6 метрик** (ldm*_max, angle_noise_ldm*, ldm106_anchor_count, descriptor_landmark_fraction)
2. **Агрегировать 12 метрик** в 3 summary поля
3. **Оставить 82 метрики** как есть
4. **Для журналиста:** трансформировать 12 критических → 5 текстовых сущностей
5. **Texture 19 метрик:** оставить для будущего pose normalization

**Итого: 82 метрики в системе, журналист видит 12 в понятном формате.**

