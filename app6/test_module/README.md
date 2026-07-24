# 🧪 test_module — сценарные тесты и ворота для пайплайна app6

## Расположение

Модуль лежит в `work/test_module/` (рядом с `app6/`).
Фото калибровочного датасета ожидаются по путям:
`work/calibration_dataset/photos/person_XX/frame_XXXXXX.jpg`
Углы головы берутся из `all_calibration_index.csv` (943 кадра, 7 человек).

## Разовая подготовка (когда фото выложены)

```bash
cd work
python -m test_module.runner pool          # индекс кадров: углы + наличие фото
python -m test_module.runner gen           # 21 сценарий → test_module/builds/
python -m test_module.runner build --all   # раскладка фото по tests/<base>/<variant>/
python -m test_module.runner cache --run   # ЕДИНСТВЕННЫЙ медленный шаг: stage1 по ~60 уникальным кадрам, ОДИН раз
```

Пока фото нет, работают `gen`, `pool` (с предупреждением) и `build --all --plan` — планы без копирования.

## Прогон тестов

```bash
python -m test_module.runner run --all --mode fast   # сборка stage1 из кэша + честные Stage 2/2B/3 + чекер
python -m test_module.runner report                  # сводка ✅/❌ → runs/summary.csv
python -m test_module.runner coverage                # карта: какая функция какими тестами закрыта
```

В FAST-режиме пропускается только извлечение геометрии (Stage 1) — оно берётся из кэша.
Само сравнение пар (Stage 2 → 2B → 3) всегда считается заново по-настоящему.

## 🚪 Ворота и интеграция с пайплайном

Каждая стадия пайплайна привязана к блокам сценариев (`registry.py: STAGE_GATES`),
а конкретные функции app6 — к конкретным сценариям (`registry.py: FUNCTION_MAP`).

```bash
python -m test_module.runner gate --stage stage2 --run             # прогнать ворота ядра анализа
python -m test_module.runner gate --stage stage2 --priority P1     # только главные тесты (быстрее)
```

Код возврата 0 = ворота открыты, 1 = закрыты — удобно для скриптов и CI.

Запуск реального анализа с автоматическими воротами перед каждой стадией:

```bash
python test_module/run_gated_pipeline.py --input <фото> --output <результаты> --priority P1
```

Если тесты стадии красные — стадия НЕ запустится, пока код/сценарий не починен.

## Как добавить свой сценарий

Скопируйте любой JSON из `builds/`, поменяйте `id`, `frames` и `expect`.
Типы проверок: `no_red_pairs`, `pair_status`, `pair_status_not`, `status_present`,
`status_absent`, `baseline_return_events`, `fdr_significant_fraction_max`, `corroboration`.

## Ограничения v1 и план

- Фаза 2: автопроверка HTML-отчёта stage3; сценарий на alpha_exp=NaN.
- Фаза 3: FULL-дымовые тесты stage1 (имена файлов, дубли, битые фото), аугментации.
- Кожные метрики не тестируются — заморожены до отдельного тестирования кожи (P0-4).
- Для FULL-режима проверьте, что stage1 обходит подпапки источников (src_a/src_b/...).
- ВАЖНО: сценарии по corroboration/rate/FDR рассчитаны на app6 С применённым
  `app6_audit_fixes.patch`. На непропатченном коде они ДОЛЖНЫ падать —
  это демонстрация того, что ворота ловят баги.
