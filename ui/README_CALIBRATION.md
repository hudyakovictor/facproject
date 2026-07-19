# UI Калибровки — Same Person Same Day

## Зачем нужен

На GitHub `3DDFA-V3` нет UI. Для твоего ТЗ журналиста предполагалось что ты сделаешь калибровку на своих фото за один день, чтобы система выучила что такое "одно и то же лицо" по коже.

**Старая идея UI:**
- Загружаешь 9 папок ракурсов, по 5-10 фото в каждой, все — ты за один день
- Система считает mole_count, pore_density и проверяет что они похожи
- Если UI использует `valid_mask = весь face` — будет шум от губ/глаз

**Новая правильная логика после моих правок до 95+:**

1. **Skin mask из `--seg`**: анализируем только `annotation[7]` — кожа, а не `valid = весь меш`. В UI теперь `uv_skin_mask` вместо `valid_mask`.

2. **MoleTracker с KDTree**: раньше просто считали `mole_count` по фото, теперь кластеризуем родинки в UV пространстве с радиусом 12px через `cKDTree`. Для одного лица за один день должно быть 2-4 уникальных кластера, все стабильные, аномалий 0. Если у тебя в frontal 3 родинки, а в left_30 тоже 3 и те же UV — система видит same face.

3. **CrossPoseValidator**: матрица 9x9 — сравнивает каждый ракурс с каждым. Overlap аналитических масок должен быть >30% и `mole_match_ratio >=0.6`. Для одного лица за один день — 0.9-1.0.

4. **Калибровка порогов**: на основе твоих данных система предлагает:
   - `mole_matching_radius` = max drift твоих родинок между ракурсами + 4px margin (обычно 8-12px)
   - `pore_density tolerance` = mean ± 2*std твоих данных за один день (например 45±5). Если у Путина 1999-2026 std в 4x больше — флаг.

## Запуск

### Вариант A: Gradio UI (рекомендуется на M1)

```bash
pip install gradio
python ui/calibration_app.py --face_model 3DDFA-V3/assets/face_model.npy --sym_map assets/symmetry_map.npz --uv_size 256
```

Открой http://127.0.0.1:7860

В поле вставь путь к папке:
```
calibration_same_day/
  frontal/
    you_frontal_01.jpg
    you_frontal_02.jpg
    ...
  left_15/
    you_left15_01.jpg
  ...
  right_60_90/
```

Нажми Run Calibration. Получишь:

- Verdict: HIGH - Same person: True
- Total unique moles: 3, stable: 3, anomalies: 0
- Cross-pose matrix
- Suggested thresholds JSON

Сохрани `calibration_profile.json`.

### Вариант B: CLI без UI (для теста без фото)

```bash
# Создадим mock папку для теста
mkdir -p /tmp/cal_test/frontal /tmp/cal_test/left_30 /tmp/cal_test/right_30
# Скопируй туда свои фото или запусти mock mode (без 3DDFA весов он сгенерирует синтетические родинки)
python ui/calibration_core.py --root /tmp/cal_test --out /tmp/cal_profile.json --face_model assets/face_model_dummy_skin.npy
```

Mock mode — без `3DDFA-V3/assets/face_model.npy` и `net_recon.pth` он сгенерирует детерминированные родинки (2 штуки в одних местах) чтобы проверить логику трекера. Для реальной калибровки нужны веса.

## Как использовать профиль для Путина

1. Твой профиль — baseline одного лица: pore_density std = 0.5, max mole drift = 4px, cross-pose match = 0.95

2. Запусти `dataset_manager.py` для Путина:

```bash
python src/dataset_manager.py --input_root putin_raw --output_root putin_sorted --face_model 3DDFA-V3/assets/face_model.npy --device mps
```

3. Сравни:

```python
# Твой baseline
my_std = 0.5
# Путин frontal 1999-2026
putin_df = pd.read_csv("putin_sorted/dataset_index.csv")
putin_frontal = putin_df[putin_df['pose']=='frontal']
print(putin_frontal['pore_density'].std()) # если 2.5 → в 5x больше твоего → не одно лицо или тяжелый ретушь

# Mole tracking
# Твой: 3 stable moles
# Путин: mole_tracking_report.json → stable 12, anomalies 5 → флаг
```

## Что править в старом UI если он был

Если у тебя был прототип UI который:

- использовал `uv_valid_mask` вместо `uv_skin_mask` → замени на `uv_skin_mask`
- считал `mole_count` без кластеризации → замени на `MoleTracker`
- не имел `CrossPoseValidator` → добавь матрицу 9x9
- пороги были хардкод `radius=10` → теперь бери из `calibration_profile.json -> suggested_thresholds -> mole_matching_radius`

Все это уже реализовано в `ui/calibration_core.py` и `ui/calibration_app.py`.
