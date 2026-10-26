# app9/validation — проверка метрик идентичности на калибровке

Один протокол, одна таблица, без пар «до/после починки». Скрипты читают данные и
импортируют `app8`/`morphing`, поэтому запускать из корня репозитория:

```bash
cd /Users/victorkhudyakov/work
PYTHONPATH=/Users/victorkhudyakov/work python app9/validation/advisor_tests.py
```

Кэши (регенерируемые, в git не входят, лежат в `/Users/victorkhudyakov/work/.runtime`):

| кэш | что содержит | как пересоздать |
|---|---|---|
| `level_cache/frames.jsonl` | 606 реконструкций `calibration_rakurs`: углы, R, облака cam/two_d/canon (106 точек, max-radius=1), v17 | `level_extract.py [bin...]`, ~46 CPU-минут |
| `calib_cache/features.jsonl` | признаки `/Volumes/SDCARD/calibration` (7 персон) | `calib_metrics.py` |
| `rakurs_cache/features.jsonl` | признаки `/Volumes/SDCARD/calibration_rakurs` | `rakurs_noise.py` |
| `hyp_cache/`, `disc_cache/`, `band_transfer/` | признаки гипотез и перенос между бинами | `hypotheses_check.py`, `robustness_check.py` |

## Скрипты

| файл | назначение |
|---|---|
| `advisor_tests.py` | мини-тесты 1–8 по замечаниям ревьюера (Procrustes, rotneg на правильном входе, блочный пол, RMS-нормировка, расстояние между людьми, ICC, детрендинг по yaw, минимальная видимая добавка) |
| `advisor_verify.py` | сверка отдельных чисел предыдущих отчётов |
| `level_extract.py` | выгрузка кадров: `vertices_camera` / `vertices_2d_orig` / `vertices_identity_only` + v17 |
| `level_verify.py` | парный тест «ровняет ли выравнивание»: каждое состояние против своего ровного эталона |
| `honest_baseline.py` | честная база 3-way формы: grouped CV, кластерный бутстрап, резидуализация по позе |
| `calib_metrics.py` | метрики и null-тесты на `/Volumes/SDCARD/calibration` |
| `calib_probe.py`, `metric_probe.py` | зонды отдельных метрик |
| `rakurs_noise.py` | null-калибровка уровня шума по ракурсам |
| `fold_diagnostic.py` | диагностика grouped CV: покрытие классов в фолдах, приоры, train-1-блок-на-человека |
| `hypotheses_check.py` | анатомия ldm106, 22 univariate-метрики, Procrustes-подмножества |
| `robustness_check.py` | страты устойчивости метрик по ракурсу/окклюзии |
| `procrustes_standard.py` | эталонная реализация Procrustes для сверки |
| `frontal_17_check.py` | 17 метрик формы только на фронтале |
| `mp_identity_probe.py` | MediaPipe-блок метрик сквозь те же гейты |
| `pose_canon_test.py`, `pose_in_mesh_probe.py` | проверка, остаётся ли поза в mesh после canonicalization |

## Что известно на сегодня

- Двойной поворот в проде подтверждён числами: `full_pose_correction_matrix` применяется к
  `vertices_identity_only`, у которого позы уже нет (`app8/reconstruction.py`, `app6/stage1/reconstruction.py`).
  Ratio на фронтале: `canon` 3.00, `canon × R_corr` 7.66, правильный вход `cam × Fz × R_corr` 2.98.
- Выравнивание (снятие позы + центр/масштаб, без доворота) убирает ~85% ракурсной дисторсии;
  эта доля от выбора пола не зависит, потому что считается как отношение `d_canon / d_cam`.
- Честный пол на `calibration_rakurs` построить нельзя: ровные кадры каждого человека — один
  непрерывный прогон. Диапазон `canon` ratio 1.25–3.0.
- Нормировка: max-radius неустойчив (зависит от одной крайней точки), прод-хронология app6
  использует RMS; при RMS порядок состояний сохраняется.
- `report/advisor_tests.json` — числа тестов 1–8.
