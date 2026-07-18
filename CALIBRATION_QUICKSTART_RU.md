# Два запуска: калибровка → основной анализ

После установки зависимостей и добавления весов 3DDFA_V3 дальнейшая работа выполняется двумя командами.

## 1. Калибровка на ваших approximately 200 фотографиях

Фотографии могут называться произвольно и лежать во вложенных папках. Все они должны показывать одного человека и быть сняты в один день.

```bash
source .venv/bin/activate
python run_calibration.py \
  --input /путь/к/моим_200_фото \
  --output runs/my_calibration \
  --device cpu
```

Команда автоматически:

1. создаёт безопасную staging-структуру, не изменяя оригиналы;
2. выполняет 3DDFA_V3/UV/Skan для всех фото;
3. распределяет фото по девяти pose bins;
4. группирует почти одинаковые burst-кадры по perceptual hash;
5. делит группы на calibration/validation/test без утечки near-duplicates;
6. калибрует каждый `pose_bin × anatomical_zone` отдельно;
7. определяет quality/noise/coverage/source-resolution gates;
8. оценивает нормальные same-day отклонения ridge density, длины, числа ветвей, median length и detector consensus;
9. калибрует branch correspondence;
10. проверяет false-anomaly rate на отложенном test split;
11. создаёт `calibration_profile.json`, `calibration_report.json` и `calibration_split.csv`.

Если held-out проверка не проходит, команда завершается кодом 3. Основной анализ по умолчанию откажется использовать такой профиль.

## 2. Основной датасет 1999–2026

В основном наборе сохраняются исходные даты в именах `YYYY_MM_DD[_N].jpg`.

```bash
python run_main_analysis.py \
  --input /путь/к/датасету_1999_2026 \
  --calibration runs/my_calibration \
  --output runs/main_analysis \
  --device cpu
```

Команда автоматически выполняет Stage 1, применяет только прошедший calibration profile, строит pose/zone-хронологию кожи и запускает Stage 2 с same-day calibration Stage 1 в качестве базовой линии.

## Критерий допуска

Профиль считается прошедшим первичную проверку, когда held-out test содержит не менее 20 допустимых пар, а false-anomaly rate не превышает `max(2%, 2 × target)`. По умолчанию target равен 1%.

Группа `pose × zone` получает рабочую модель только при наличии минимум 8 независимых фотографий и 20 calibration-пар. Недостаточно представленные ракурсы получают `uncalibrated_zone`, а не вымышленный результат.
