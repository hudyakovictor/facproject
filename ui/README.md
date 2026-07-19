# Forensic Calibration & Face Comparison UI

Готовый локальный React-интерфейс включён вместе с production bundle `dist/`.

## Запуск на MacBook M1

Из корня проекта:

```bash
source .venv/bin/activate
python ui/launcher.py
```

Откроется `http://127.0.0.1:8765`. Node/npm для обычного запуска не нужны: собранный React bundle уже включён. Для изменения исходников:

```bash
cd ui
npm install
npm run build
```

## Реализовано

- System Doctor;
- Calibration Studio с запуском реального `run_calibration.py`;
- матрица 9 ракурсов и 13 зон;
- конфигурационные presets/macro controls;
- Comparison Lab для двух готовых Stage-1 записей;
- локальный Python API;
- Kabsch alignment identity-only meshes;
- геометрические RMSE/P95/max;
- WebGL fixed-topology morph с независимыми Geometry mix и Texture mix;
- identity-only / identity+expression controls;
- region selector;
- отображение Analysis UV и Synthetic UV с разной семантикой;
- local jobs, progress/status и настройки;
- исходники React/TypeScript, CSS и собранный `dist/`.

UI используется для калибровки конфигов и тестовых A/B сравнений. Основной датасет обрабатывается headless через `run_main_analysis.py`.

## Файлы

```text
ui/
  src/main.tsx
  src/styles.css
  server.py
  launcher.py
  build.mjs
  package.json
  dist/
  FUNCTIONAL_SPEC_RU.md
  ARCHITECTURE_RU.md
  NAVIGATION_AND_STATES.json
```

Synthetic UV всегда маркируется как visual-only и не используется в skin metrics.
