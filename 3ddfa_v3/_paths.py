"""🧭 Портируемое разрешение путей для вспомогательных скриптов 3DDFA_V3.

DEV_FIX_TZ B3 / P1.13 / P2.14: скрипты `preview.py`, `test_uv_*.py` содержали
абсолютные пути вида `/Users/victorkhudyakov/work/3ddfa_v3` и выполняли
глобальный `os.chdir()`. На любой другой машине (и в CI) они не запускались,
а глобальная смена рабочей директории ломала все относительные пути в
остальной части процесса.

Здесь пути вычисляются от расположения самого файла, с возможностью
переопределения переменными окружения и аргументами CLI. Смена директории
локализована в контекстном менеджере `pushd`, который всегда возвращает
исходную CWD — даже при исключении.

Апстримный код 3DDFA_V3 (`model/recon.py`, `face_box/__init__.py`) загружает
веса по ОТНОСИТЕЛЬНЫМ путям `assets/...`, поэтому корень репозитория обязан
быть текущей директорией именно на время этих вызовов. `pushd` — это способ
удовлетворить требование апстрима, не оставляя побочного эффекта на весь
процесс.
"""
from __future__ import annotations

import argparse
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

#: Корень 3ddfa_v3 — каталог, в котором лежит этот файл.
TDDFA_ROOT: Path = Path(__file__).resolve().parent
#: Корень всего проекта (на уровень выше 3ddfa_v3).
PROJECT_ROOT: Path = TDDFA_ROOT.parent


def ffhq_root() -> Path:
    """🔍 QUERY → Корень FFHQ-detect-face-wrinkles.

    Порядок: переменная окружения `FFHQ_ROOT` → соседний каталог в проекте.
    """
    env = os.environ.get("FFHQ_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return PROJECT_ROOT / "FFHQ-detect-face-wrinkles"


def wrinkle_checkpoint(ffhq: Path | None = None) -> Path:
    """🔍 QUERY → Путь к весам UNet для морщин (`res/cp/wrinkle_model.pth`)."""
    env = os.environ.get("WRINKLE_CHECKPOINT")
    if env:
        return Path(env).expanduser().resolve()
    return (ffhq or ffhq_root()) / "res" / "cp" / "wrinkle_model.pth"


@contextmanager
def pushd(directory: Path) -> Iterator[Path]:
    """🔄 Временно сменить рабочую директорию и гарантированно вернуть прежнюю.

    Заменяет разбросанные по скриптам голые `os.chdir(...)` (P2.14): смена
    директории теперь ограничена блоком `with` и не «протекает» дальше по
    коду, где относительные пути значили бы уже совсем другое.
    """
    previous = Path.cwd()
    os.chdir(directory)
    try:
        yield Path(directory)
    finally:
        os.chdir(previous)


def require(path: Path, what: str) -> Path:
    """🚧 GATE → Проверить существование входа и дать понятную ошибку.

    Молчаливое падение на отсутствующем файле в глубине пайплайна хуже, чем
    явное сообщение с указанием, какой аргумент/переменную задать.
    """
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise FileNotFoundError(
            f"{what} не найден: {resolved}. Укажите путь явно аргументом CLI "
            f"или переменной окружения (см. --help)."
        )
    return resolved.resolve()


def add_common_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """🏭 FACTORY → Общие CLI-аргументы вспомогательных скриптов."""
    parser.add_argument("--ffhq-root", type=Path, default=None,
                        help="корень FFHQ-detect-face-wrinkles (по умолчанию: соседний каталог проекта)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="каталог для результатов (по умолчанию: <ffhq-root>/uv_wrinkle_test)")
    parser.add_argument("--checkpoint", type=Path, default=None,
                        help="веса UNet морщин (по умолчанию: <ffhq-root>/res/cp/wrinkle_model.pth)")
    parser.add_argument("--device", default=None, choices=["cuda", "mps", "cpu"],
                        help="устройство инференса (по умолчанию: автовыбор)")
    return parser


def resolve_device(requested: str | None = None) -> str:
    """🔍 QUERY → Выбрать устройство инференса.

    На macOS MPS НЕ считается валидированным backend рендеринга
    (`app6/AGENTS.md`), поэтому он выбирается только по явному запросу.
    """
    if requested:
        return requested
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"
