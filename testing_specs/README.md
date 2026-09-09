# testing_specs — как запустить тест без весов и реального датасета

> Папка создана чтобы по ссылке на GitHub без весов человек понял как собрать синтетический тест и запустить пайплайн одной командой. Полный датасет (16k фото) лежит локально в `/Volumes/SDCARD/photo/main` и `/Volumes/SDCARD/storage/stage1` и в репо **не входит**.

## Что проверяет этот тест

На примере **одной фото** (напр. `1999_08_16(2).jpg`) — проверяется весь пайплайн `Stage1 → Stage2_v2` без установки весов. Имена с `()` вида `1999_08_16(2).jpg` уже поддерживаются `app6/stage1/naming.py:17,31` (`_COPY_SUFFIX` ловит `(2)`), каноническое имя `1999_08_16_2`.

## Окружение

Все команды — строго через `app6/README.md:2`:

```
/Users/victorkhudyakov/work/.venv/bin/python
```

`.venv` — симлинк на `deeputin` (`python 3.10.20, torch 1.12.1, cv2 5.0`). Пропатчен `app6/stage1/engine.py:18` для `UTC` на `3.10`.

Если `.venv` нет — пересоздать и поставить зависимости или сделать симлинк на рабочий `deeputin`:

```bash
rm -rf /Users/victorkhudyakov/work/.venv
ln -s /opt/homebrew/Caskroom/miniconda/base/envs/deeputin /Users/victorkhudyakov/work/.venv
```

## Вариант A — синтетика без весов (рекомендуется для проверки извне)

Не требует ни весов (`3ddfa_v3/assets/*.pth`), ни реальных фото. Генерирует Stage1-дерево из детерминированного лица.

```bash
# 1. Сгенерировать синтетический Stage1 (6 дат × 3 бинa × 2 фото/день = 36 фото) с инжектом изменения 0.01 после 2012-03-05
/Users/victorkhudyakov/work/.venv/bin/python -m app6.stage2_v2.fixtures /tmp/fixture_s1 --per-day 2 --change 0.01

ls /tmp/fixture_s1 | head -5
cat /tmp/fixture_s1/main_timeline.csv | head

# 2. Прогнать Stage2_v2 (быстро, max 5 пар на бин)
/Users/victorkhudyakov/work/.venv/bin/python -c "
import sys
sys.path.insert(0, 'app6/stage2_v2')
from stage2_v2 import pipeline, params
from pathlib import Path
p = params.builtin('default').replace(max_pairs_per_bin=5, bootstrap_iterations=200)
result = pipeline.run(Path('/tmp/fixture_s1'), p, project_root=Path('.'))
print('pairs', len(result.pairs), 'skipped', len(result.skipped))
print('noise', result.noise['status'])
written = pipeline.write_artifacts(result, Path('/tmp/stage2_synth'))
print('artifacts -> /tmp/stage2_synth', [w.name for w in written])
"

ls /tmp/stage2_synth
cat /tmp/stage2_synth/analysis_manifest.json | head -30
```

Ожидаемо: `pairs >0`, `noise no_reference` если нет same-day пар достаточно, иначе `ok`. Все 11 артефактов пишутся (`analysis_manifest.json`, `params.json`, `pair_metrics.json/csv` и т.д.) — те же 33 имени что у legacy `stage2`.

## Вариант B — одна реальная фото (с весами)

Если есть доступ к весам и к `/Volumes/SDCARD`:

```bash
# 1. Подготовить одну фото с правильным именем (скобки уже ок)
mkdir -p /tmp/test_one_photo_input
cp "/Volumes/SDCARD/photo/main/1999_08_16(2).jpg" /tmp/test_one_photo_input/

# проверка парсинга имени
/Users/victorkhudyakov/work/.venv/bin/python -c "from app6.stage1.naming import parse_photo_name; from pathlib import Path; print(parse_photo_name(Path('/tmp/test_one_photo_input/1999_08_16(2).jpg')))"

# 2. Прогнать Stage1 (требует 3DDFA + mesh_core_cython, может падать на numpy 2.x — используйте синтетику если падает)
/Users/victorkhudyakov/work/.venv/bin/python app6/run_stage1.py --project-root . --input /tmp/test_one_photo_input --output /tmp/test_one_photo_output --device cpu --limit 1 --overwrite

ls /tmp/test_one_photo_output
ls /tmp/test_one_photo_output/1999_08_16_2__*

# 3. Вместо шага 2 можно сразу использовать уже просчитанный Stage1
ls /Volumes/SDCARD/storage/stage1 | head
ls /Volumes/SDCARD/storage/stage1/1999_08_16_2__b4b20d62330a

# 4. Прогнать Stage2_v2 на реальном Stage1 (ограничиваем для скорости)
/Users/victorkhudyakov/work/.venv/bin/python -c "
import sys
sys.path.insert(0, 'app6/stage2_v2')
from stage2_v2 import pipeline, params
from pathlib import Path
p = params.builtin('default').replace(max_pairs_per_bin=5, bootstrap_iterations=200)
result = pipeline.run(Path('/Volumes/SDCARD/storage/stage1'), p, project_root=Path('.'))
print(result.manifest()['pairs'])
pipeline.write_artifacts(result, Path('/tmp/stage2_real_one'))
"
```

## Что в папке весь датасет

- Исходники: `/Volumes/SDCARD/photo/main` — 1909 обработанных (из 16k+ исходных), имена вида `YYYY_MM_DD` и `YYYY_MM_DD(2).jpg` → каноникал `YYYY_MM_DD_2`
- Stage1 вывод: `/Volumes/SDCARD/storage/stage1` — `main_timeline.csv` + по папке на фото (`reconstruction.npz`, `info.json`, `validation.json`)
- Веса: `/Users/victorkhudyakov/work/3ddfa_v3/assets` (`face_model.npy`, `net_recon.pth`, `large_base_net.pth` + retinaface)

В репо они не входят (`app6/README.md:27` — «весов нет»), поэтому для внешней проверки используйте **Вариант A**.

## Быстрая проверка что всё ок

```bash
/Users/victorkhudyakov/work/.venv/bin/python app6/run_stage1.py --help | head -10
/Users/victorkhudyakov/work/.venv/bin/python -m app6.stage2_v2.fixtures --help
ls app6/stage2_v2/README.md
```

Если человек скачает репо по ссылке — достаточно выполнить команды из **Варианта A**, скачать артефакты из `/tmp/stage2_synth` и запустить `ls`/`cat` как выше.
