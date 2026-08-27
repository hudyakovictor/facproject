# DEEPUTIN — Распределение 100 метрик по полезности (30 анализов)

**Дата:** 2026-08-27  
**Статус:** ✅ ЗАВЕРШЕНО  
**Основа:** 30 анализов кода — status chain, evidence, change_points, UI, narrative

---

## 🎯 ГЛАВНЫЙ ВЫВОД

Из 100 метрик **только 12 определяют результат**, **8 ограничивают**, **10 несут детали**, **19 визуализация**, **51 служебные**.

```
100 метрик:
  ┌──────────────────────────────────────────────────┐
  │ 12 КРИТИЧЕСКИХ ──── определяют status/evidence   │ ████
  │  8 ОГРАНИЧИВАЮЩИХ ── блокируют evidence          │ ███
  │ 10 ИНФОРМАТИВНЫХ ─── несут детали для журналиста │ ██
  │ 19 ВИЗУАЛИЗАЦИЯ ──── texture (не evidence)       │ ██
  │ 51 СЛУЖЕБНАЯ ─────── raw/internal (не нужны)     │ ████████████
  └──────────────────────────────────────────────────┘
```

---

## 📋 РЕЗУЛЬТАТЫ 30 АНАЛИЗОВ

### БЛОК 1: Информационная ценность (анализы 1-6)

| # | Анализ | Результат |
|---|--------|-----------|
| 1 | **Landmark → status** | Status = motion_score134['status']. Критерии: significant_fraction (<0.08→noise, ≥0.15+coherent≥0.45+p95≥3.5→candidate) |
| 2 | **Descriptor → status** | Может ПОВЫСИТЬ status: descriptor_jump_candidate → coherent_jump_candidate. 13 семейств shape |
| 3 | **Mesh → status** | ❌ НЕ влияет на status. Вычисляется отдельно, записывается в mesh_pair_metrics.csv |
| 4 | **Texture → evidence** | ❌ ПОЛНОСТЬЮ исключена (visualization_only). 19 метрик не входят в evidence |
| 5 | **Chronology → status** | Может ПОВЫСИТЬ: rapid_change → persistent_rapid. chronology_rate_z в change_points |
| 6 | **Quality → gating** | quality_limited = qmin<0.35 OR weak_quality → evidence_state="quality_limited" |

### БЛОК 2: Цепочка определения status (анализы 7-12)

```
Status determination chain:
  1. motion_score134['status']     ← PRIMARY (p95_point_z, significant_fraction, coherent_motion)
  2. descriptor upgrade            ← UPGRADE (descriptor_jump_candidate → coherent_jump_candidate)
  3. persistence check             ← UPGRADE (coherent_jump + successor p95≥3.0 → persistent_geometric_change)
  4. chronology upgrade            ← UPGRADE (rapid_change + persistence → persistent_rapid_change)
  
  Gate overrides (понижают):
  5. quality_limited               ← DOWNGRADE (evidence_state = "quality_limited")
  6. calibration_limited           ← DOWNGRADE (evidence_state = "calibration_limited")
  7. pose_leakage_limited          ← DOWNGRADE (evidence_state = "pose_leakage_limited")
  8. date_provenance_limited       ← DOWNGRADE (evidence_state = "date_provenance_limited")
```

### БЛОК 3: Что видит журналист (анализы 13-18)

| # | Анализ | Результат |
|---|--------|-----------|
| 13 | **HTML таблица "Все сравнения"** | 10 колонок: date, pose_bin, pair_type, photo_a→b, days, sig_fraction, p95_z, descriptors, rate_status, status |
| 14 | **HTML таблица "Кандидаты"** | 7 колонок: date, pose_bin, pair, days, p95_z, rate_status, status |
| 15 | **Timeline** | p95_point_z по датам, color-coded по status |
| 16 | **Motion maps** | ldm134_point_z + ldm134_vectors (SVG визуализация) |
| 17 | **Narrative** | 6 параграфов о МЕТОДЕ (не о конкретных парах!) |
| 18 | **Evidence packet** | 81 метрика (все кроме texture) |

### БЛОК 4: Что нужно для журналистских сущностей (анализы 19-24)

| # | Сущность | Какие метрики нужны | Есть в коде? |
|---|----------|---------------------|--------------|
| 19 | **Карточка пары** | p95_z, sig_fraction, coherent, descriptor_families, days_delta, status | ✅ Все есть |
| 20 | **Уровень уверенности** | cross_bin_support, quality_limited, calibration_limited, persistence | ✅ Все есть |
| 21 | **Тезис (3 шага)** | Шаг1: p95_z+sig_fraction; Шаг2: cross_bin+quality; Шаг3: confidence | ✅ Все есть |
| 22 | **Эпоха** | date_b (год), status, p95_z, chronology_rate | ✅ Все есть |
| 23 | **Наблюдение** | photo_b, pose_bin, cross_bin_support | ✅ Все есть |
| 24 | **Альтернативы** | quality_limited, calibration_limited, pose_leakage, date_provenance | ✅ Все есть |

### БЛОК 5: Классификация (анализы 25-30)

| # | Анализ | Результат |
|---|--------|-----------|
| 25 | **Метрики определяющие status** | 4: p95_point_z, significant_fraction, coherent_motion, descriptor_status |
| 26 | **Метрики повышающие status** | 3: descriptor_jump, persistence_check, chronology_rate |
| 27 | **Метрики ограничивающие** | 5: quality_limited, calibration_limited, pose_leakage, date_provenance, near_duplicate |
| 28 | **Метрики несущие детали** | 10: days_delta, descriptor_families, cross_bin, matched_calibration, identity_only_rmse, expression_influence, mesh_rmse, alpha_id/exp, biological_rate |
| 29 | **Метрики визуализации** | 19 texture + motion_maps (ldm134_vectors/z) |
| 30 | **Метрики служебные** | 51: raw rmse/median/max, anchor, alignment, angle_noise, visibility_gate, zone details |

---

## 🗺️ ФИНАЛЬНАЯ КАРТА: 100 метрик → 5 уровней полезности

### УРОВЕНЬ 1: КРИТИЧЕСКИЕ (12 метрик) — определяют status/evidence

| # | Метрика | Семья | Роль | Доходит до журналиста? |
|---|---------|-------|------|------------------------|
| 1 | **p95_point_z** | landmark | PRIMARY: определяет candidate vs noise | ✅ В таблице + timeline |
| 2 | **significant_point_fraction** | landmark | PRIMARY: % точек выше шума | ✅ В таблице |
| 3 | **coherent_motion_fraction** | landmark | PRIMARY: согласованность движения | ✅ В change_points |
| 4 | **descriptor_significant_fraction** | descriptor | UPGRADE: может повысить status | ❌ Только в evidence |
| 5 | **descriptor_p95_z** | descriptor | UPGRADE: сила дескрипторного сигнала | ❌ Только в evidence |
| 6 | **descriptor_top_families** | descriptor | ДЕТАЛИ: какие shape изменились | ✅ В таблице |
| 7 | **chronology_rate_z** | pair | UPGRADE: аномальный темп | ✅ В change_points |
| 8 | **chronology_rate_status** | pair | UPGRADE: within_expected/rapid/persistent | ✅ В таблице |
| 9 | **cross_bin_support_pose_count** | pair | CONFIDENCE: подтверждение в других ракурсах | ✅ В change_points |
| 10 | **evidence_state** | pair | ИТОГ: финальный evidence статус | ✅ В таблице (как "status") |
| 11 | **status** | landmark | ИТОГ: measurement status | ✅ Через evidence_state |
| 12 | **days_delta** | pair | КОНТЕКСТ: временной промежуток | ✅ В таблице |

### УРОВЕНЬ 2: ОГРАНИЧИВАЮЩИЕ (8 метрик) — блокируют evidence

| # | Метрика | Семья | Роль | Доходит до журналиста? |
|---|---------|-------|------|------------------------|
| 13 | **quality_limited** | quality | GATE: качество недостаточно | ⚠️ Через evidence_state |
| 14 | **calibration_limited** | pair | GATE: калибровка недостаточна | ⚠️ Через evidence_state |
| 15 | **pose_leakage_limited** | pair | GATE: утечка позы в метрики | ⚠️ Через evidence_state |
| 16 | **date_provenance_limited** | pair | GATE: конфликт дат | ⚠️ Через evidence_state |
| 17 | **near_duplicate_pair** | pair | GATE: дубликат | ⚠️ Через evidence_state |
| 18 | **quality_texture_score_a/b** | quality | INPUT: качество фото | ❌ Только в evidence |
| 19 | **matched_calibration_sets** | pair | INPUT: сколько calibration datasets | ❌ Только в evidence |
| 20 | **expression_influence** | quality | КОНТЕКСТ: влияние мимики | ❌ Только в evidence |

### УРОВЕНЬ 3: ИНФОРМАТИВНЫЕ (10 метрик) — несут детали для журналиста

| # | Метрика | Семья | Роль | Доходит до журналиста? |
|---|---------|-------|------|------------------------|
| 21 | **identity_only_motion_rmse** | landmark | ДЕТАЛИ: движение без мимики | ❌ Только в evidence |
| 22 | **alpha_id_l2** | landmark | ДЕТАЛИ: BFM identity change | ❌ Только в evidence |
| 23 | **alpha_exp_l2** | landmark | ДЕТАЛИ: BFM expression change | ❌ Только в evidence |
| 24 | **mesh_rmse** | mesh | ДЕТАЛИ: 3D surface change | ⚠️ В UI spec |
| 25 | **mesh_point_to_plane_rmse** | mesh | ДЕТАЛИ: surface normal change | ❌ Только в evidence |
| 26 | **mesh_max_robust_z** | mesh | ДЕТАЛИ: max z по mesh | ❌ Только в evidence |
| 27 | **primary_robust_z** | pair | ДЕТАЛИ: primary zone z-score | ❌ Только в evidence |
| 28 | **baseline_return_opposite_fraction** | descriptor | ДЕТАЛИ: возврат к baseline | ❌ Только в evidence |
| 29 | **cross_bin_independent_source_count** | pair | ДЕТАЛИ: независимые источники | ❌ Только в evidence |
| 30 | **biological_rate_z** | pair | ДЕТАЛИ: биологический темп | ⚠️ В narrative (счётчик) |

### УРОВЕНЬ 4: ВИЗУАЛИЗАЦИЯ (19 метрик) — texture, не evidence

| # | Метрика | Семья | Роль | Доходит до журналиста? |
|---|---------|-------|------|------------------------|
| 31-49 | **texture_image_max_***, **texture_structure_***, **quality_zone_*** | texture | ВИЗУАЛИЗАЦИЯ | ❌ Исключены Stage 3 |

### УРОВЕНЬ 5: СЛУЖЕБНЫЕ (51 метрика) — raw/internal

| # | Группа | Кол-во | Роль |
|---|--------|-------:|------|
| 50-55 | ldm106/134_rmse/median/max | 6 | Raw distance metrics |
| 56-57 | ldm106/134_anchor_count | 2 | Anchor policy details |
| 58-61 | alignment_*_trimmed_count, residual_* | 4 | Alignment internals |
| 62-63 | alpha_id/exp_robust_z | 2 | Alpha z-scores |
| 64-65 | median_point_z, significant_point_count | 2 | Redundant with p95/fraction |
| 66-68 | mesh_median/p95, common/visible/fit counts | 5 | Mesh internals |
| 69-75 | mesh_point_to_plane_median/p95/signed, alignment_residual | 5 | Mesh internals |
| 76-80 | mesh_anchor_fraction, mesh_calibrated_*, mesh_shape_* | 5 | Mesh calibration details |
| 81-85 | pair_index, same_day, pose_distance, common_visible, coverage | 5 | Pair metadata |
| 86-90 | quality_zone_common/usable, quality_status_a/b, stratum | 5 | Quality internals |
| 91-95 | forehead_wrinkle, expression_gate_*, visibility_gate_* | 5 | Gate internals |
| 96-100 | angle_noise_*, descriptor_landmark_fraction/top_counts | 5 | Internal diagnostics |

---

## 🎯 РЕШЕНИЕ: Как распределить с максимальным эффектом

### Для ЖУРНАЛИСТА (12 метрик → 5 агрегированных сущностей):

| Сущность | Из каких метрик | Формат для журналиста |
|----------|-----------------|----------------------|
| **Сила сигнала** | p95_point_z + significant_fraction + coherent_motion | "X% точек сместились согласованно, сила Yσ" |
| **Тип изменения** | descriptor_top_families + identity_only_motion | "Изменились [скулы/челюсть/лоб], без влияния мимики" |
| **Темп** | days_delta + chronology_rate_status + biological_rate_z | "За N дней — [нормальный/аномальный/биологически невероятный] темп" |
| **Подтверждение** | cross_bin_support + persistence + matched_calibration | "Подтверждено в M ракурсах, устойчиво в соседних парах" |
| **Ограничения** | quality_limited + calibration_limited + pose_leakage + date_provenance | "Данные [достаточны/ограничены] из-за [качество/калибровка/позa/даты]" |

### Для АНАЛИТИКА (30 метрик → evidence packet):

Все 12 критических + 8 ограничивающих + 10 информативных = 30 метрик.

### Для РЕВЬЮЕРА (81 метрика → evidence packet):

Все кроме 19 texture (visualization_only).

### Для СИСТЕМЫ (100 метрик → pair_metrics.csv):

Все 100 метрик для полноты и воспроизводимости.

---

## 📊 МАТРИЦА: Метрика × Роль

```
                    Определяет  Ограничивает  Несёт     Визуали-  Служебная
                    status      evidence      детали    зация     
Landmark (25)       ████ (4)    —             ███ (5)   —         █████████ (16)
Descriptor (10)     ██ (3)      —             █ (2)     —         ████ (5)
Mesh (20)           —           —             ███ (3)   —         ██████████████ (17)
Texture (19)        —           —             —         ███████ (19) —
Quality (10)        —           ███ (4)       █ (1)     —         ████ (5)
Pair (16)           ████ (4)    ███ (4)       █ (1)     —         ██████ (7)
```

---

## 📊 МАТРИЦА: Метрика × Получатель

```
                    Журналист  Аналитик  Ревьюер  Система
Критические (12)    ✅ ВСЕ     ✅        ✅        ✅
Ограничивающие (8)  ⚠️ 5/8    ✅        ✅        ✅
Информативные (10)  ❌ 0/10   ✅        ✅        ✅
Визуализация (19)   ❌ 0/19   ❌        ✅        ✅
Служебные (51)      ❌ 0/51   ❌        ❌        ✅
```

**Проблема:** Журналист видит только 12 из 100 метрик (12%), причём в raw формате (числа).

---

## 🔧 ЧТО НУЖНО СДЕЛАТЬ

### P0: Трансформатор 12 критических → 5 журналистских сущностей

```python
def pair_to_journalist(row: dict) -> dict:
    """Трансформация raw метрик в журналистский формат."""
    return {
        "signal_strength": format_signal(row),      # "43% точек сместились, сила 4.2σ"
        "change_type": format_change(row),           # "Изменились скулы и челюсть"
        "tempo": format_tempo(row),                  # "За 180 дней — аномальный темп"
        "corroboration": format_corroboration(row),  # "Подтверждено в 3 ракурсах"
        "limitations": format_limitations(row),      # "Качество ограничено"
    }
```

### P1: Добавить 10 информативных в журналистский слой

- identity_only_motion → "без влияния мимики"
- alpha_id_l2 → "BFM identity изменился"
- mesh_rmse → "3D поверхность изменилась"
- baseline_return → "возврат к прежнему состоянию"

### P2: Агрегировать 51 служебную в summary

- Вместо 6 ldm raw → "Landmark RMSE: 0.008 (в пределах шума)"
- Вместо 5 mesh internals → "Mesh zones: 12/20 измерены"
- Вместо gate internals → "Все гейты пройдены"

---

## 📋 ИТОГОВАЯ ТАБЛИЦА

| Уровень | Метрик | Роль | Действие |
|---------|-------:|------|----------|
| **1. Критические** | 12 | Определяют результат | ✅ Трансформировать в 5 журналистских сущностей |
| **2. Ограничивающие** | 8 | Блокируют evidence | ✅ Добавить в "Ограничения" журналиста |
| **3. Информативные** | 10 | Несут детали | ✅ Добавить в детальный тезис |
| **4. Визуализация** | 19 | Texture | ⚠️ Оставить для pose normalization (следующий этап) |
| **5. Служебные** | 51 | Raw/internal | ❌ Агрегировать в summary, не показывать |

**Итого: 30 метрик несут ценность, 70 — служебные/визуализация.**

