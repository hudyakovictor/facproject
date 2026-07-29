"""🧭 Портируемое разрешение путей для скриптов FFHQ-detect-face-wrinkles.

DEV_FIX_TZ B4 / P1.14: скрипты содержали fallback-пути вида
`/Users/victorkhudyakov/work/testphoto`, а `compare_two.py` дополнительно
зашивал путь к интерпретатору Python. На другой машине такие скрипты молча
работали не с теми данными (или падали), поэтому fallback-и удалены.

Правила:
  * входные каталоги/файлы задаются ЯВНО аргументами CLI — «догадливого»
    значения по умолчанию, указывающего на чужую машину, больше нет;
  * корни репозиториев вычисляются от расположения файла;
  * интерпретатор берётся из `sys.executable`, а не из строки-константы;
  * `os.chdir` заменён на контекстный менеджер `pushd`, который возвращает
    исходную рабочую директорию даже при исключении.
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

#: Корень FFHQ-detect-face-wrinkles — каталог этого файла.
FFHQ_ROOT: Path = Path(__file__).resolve().parent
#: Корень всего проекта (уровнем выше).
PROJECT_ROOT: Path = FFHQ_ROOT.parent


def tddfa_root() -> Path:
    """🔍 QUERY → Корень 3ddfa_v3 (env `TDDFA_ROOT` → соседний каталог)."""
    env = os.environ.get("TDDFA_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return PROJECT_ROOT / "3ddfa_v3"


def python_executable() -> str:
    """🔍 QUERY → Интерпретатор для дочерних процессов.

    `sys.executable` — тот же интерпретатор, что запустил скрипт, поэтому
    дочерний процесс гарантированно получает то же окружение и те же
    установленные пакеты. Хардкод пути к чужому venv это не обеспечивал.
    """
    return sys.executable


@contextmanager
def pushd(directory: Path) -> Iterator[Path]:
    """🔄 Временно сменить CWD и гарантированно вернуть прежнюю.

    Нужен потому, что апстримный код 3DDFA_V3 грузит веса по относительным
    путям `assets/...`; смена директории ограничена блоком `with`.
    """
    previous = Path.cwd()
    os.chdir(directory)
    try:
        yield Path(directory)
    finally:
        os.chdir(previous)


def require_arg(argv: Sequence[str], index: int, name: str, usage: str) -> Path:
    """🚧 GATE → Обязательный позиционный аргумент-путь.

    Раньше на месте отсутствующего аргумента подставлялся путь к каталогу на
    машине разработчика: на другой машине скрипт либо падал с непонятной
    ошибкой, либо (хуже) обрабатывал не те данные. Теперь отсутствие аргумента
    — явная ошибка с подсказкой по использованию.
    """
    if len(argv) <= index:
        raise SystemExit(f"ошибка: не указан {name}.\nиспользование: {usage}")
    path = Path(argv[index]).expanduser()
    if not path.exists():
        raise SystemExit(f"ошибка: {name} не существует: {path}")
    return path.resolve()


def optional_out_dir(argv: Sequence[str], index: int, default: Path) -> Path:
    """🔍 QUERY → Необязательный выходной каталог (создаётся при необходимости).

    Для ВЫХОДА значение по умолчанию допустимо: оно относительно текущего
    проекта и не указывает на постороннюю файловую систему.
    """
    path = Path(argv[index]).expanduser() if len(argv) > index else default
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()
