# DEEPUTIN app6

⚠️ Все команды запуска должны использовать явный путь к интерпретатору:  
`/Users/victorkhudyakov/work/.venv/bin/python`

Полностью переписанный этап 1 для 3DDFA_V3. Главная цель — один раз извлечь и атомарно сохранить все дорогие данные, после чего этапы анализа и визуализации не запускают нейросеть повторно.

## Что исправлено

- один вызов `net_recon` на фотографию;
- корректные `alpha_alb` и `alpha_sh`;
- identity+expression и identity-only mesh;
- object/normalized/canonical/camera/image-224 representations;
- LDM106/LDM134 и официальные vertex indices;
- front-facing, renderer и combined visibility полного mesh;
- исходные восемь semantic channels;
- skin+nose mask с явной policy и без пространственно ложного resize fallback;
- UV analysis, beauty, observed mask, confidence, original mask и triangle visibility;
- hash-based photo ID;
- строгие даты только из `YYYY_MM_DD[_N]`;
- atomic directory commit;
- validator и hash-aware resume;
- технический QA без verdict и искусственного overall score;
- correspondence-based reprojection checks.

## Обязательные assets

В корне проекта должны находиться:

- `assets/face_model.npy`;
- `assets/net_recon.pth` либо `assets/net_recon_mbnet.pth`;
- `assets/large_base_net.pth`.

В приложенном пользовательском архиве этих весов нет; app6 завершит работу до batch run с понятной ошибкой, а не создаст частичные результаты.

## Имена фотографий

Допустимы только:

```text
1999_01_11.jpg
1999_01_11_2.jpg
1999_01_11_3.png
```

EXIF сохраняется и сравнивается как corroboration, но никогда не заменяет authoritative дату из имени файла.

## MacBook M1

Используйте CPU. Bundled renderer 3DDFA_V3 не поддерживает MPS как полноценный backend: MPS попадает в ветку nvdiffrast. `--device auto` на macOS автоматически выбирает CPU. Conda не обязательна.

## Smoke run

```bash
 /Users/victorkhudyakov/work/.venv/bin/python app6/run_stage1.py \
  --project-root . \
  --input dataset/main \
  --output results/app6_smoke \
  --device cpu \
  --limit 2 \
  --fail-fast
```

Повторите ту же команду: обе записи должны быть пропущены валидным resume.

## Batch gates

 ```bash
 # 10 фото
 /Users/victorkhudyakov/work/.venv/bin/python app6/run_stage1.py --input dataset/main --output results/stage1_v2 --device cpu --limit 10 --fail-fast

 # 100 фото — убрать fail-fast, чтобы оценить error rate
 /Users/victorkhudyakov/work/.venv/bin/python app6/run_stage1.py --input dataset/main --output results/stage1_v2 --device cpu --limit 100

 # полный набор
 /Users/victorkhudyakov/work/.venv/bin/python app6/run_stage1.py --input dataset/main --output results/stage1_v2 --device cpu
 ```

Не запускайте полный набор, пока 100-photo gate не завершился без structural validation errors.

## Тесты без весов

```bash
/Users/victorkhudyakov/work/.venv/bin/python -m unittest discover \
  -s app6/test_module -p 'test*.py' -v
```

## Этап 2 и правила разработки

Актуальные backend-правила описаны в [`app6/AGENTS.md`](AGENTS.md), а полный
25-факторный workflow — в [`../SKILL.md`](../SKILL.md). Фактический статус
подтверждается regression/contract tests из `app6/test_module/` и
`app6/api/tests/`; отсутствующий в текущем checkout инструмент нельзя считать
пройденным gate.

Для планирования небольших сценариев используется `app6/run_scenario_planner.py`.
Обязательные scenario truth cases и release gates перечислены в
[`../docs/final/07_TESTING_AND_ACCEPTANCE.md`](../docs/final/07_TESTING_AND_ACCEPTANCE.md).

Минимальная проверка:

```bash
$PY -m compileall -q app6
$PY -m pytest -q app6/test_module app6/api/tests
```

Полный Stage 1/2 E2E запускается только при явном доступе к локальным весам,
фото и calibration artifacts. Их отсутствие в конкретном checkout не означает,
что они отсутствуют в локальной среде владельца, и не разрешает synthetic
fallback в production API.

