"""🔒 GUARD → Проверка целостности калибровки, кода, модели и конфигурации.

ТЗ п.11: перед прогоном сверять `dataset_hash`, `code_hash`, `model_hash`,
`config_hash` и блокировать запуск при расхождении. Аудит (D8) показал: хеши
вычисляются в `stage1/engine.py` и пишутся в манифест, но `run_preflight.py`
не сверял их ни разу — подмена калибровочного набора между прогонами прошла бы
незамеченной, а результаты выглядели бы сопоставимыми.

Политика fail-closed: отсутствующий ключ — такой же отказ, как и несовпадение.
Молча пропустить непроверенный хеш опаснее, чем остановить прогон.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Iterable

from app6.stage1.utils import sha256_file, sha256_paths

INTEGRITY_SCHEMA: Final[str] = "deeputin-integrity-guard-v1.0"

#: Хеши, обязательные для воспроизводимого прогона.
REQUIRED_HASH_KEYS: Final[tuple[str, ...]] = ("dataset_hash", "code_hash", "model_hash", "config_hash")


class IntegrityError(RuntimeError):
    """Расхождение или отсутствие обязательного хеша целостности."""


def verify_integrity_hashes(
    expected: dict[str, str],
    actual: dict[str, str],
    *,
    required_keys: Iterable[str] = REQUIRED_HASH_KEYS,
    strict: bool = True,
) -> dict[str, Any]:
    """🔒 GUARD → Сверить ожидаемые и фактические хеши.

    Args:
        expected: эталонные значения (например, из манифеста прошлого прогона).
        actual: значения текущего окружения.
        required_keys: ключи, обязательные к проверке.
        strict: при True расхождение поднимает `IntegrityError`.

    Returns:
        Отчёт с полями `status`, `per_key`, `mismatched`, `missing`.

    Raises:
        IntegrityError: при `strict=True` и любом расхождении или пропуске.
    """
    per_key: dict[str, dict[str, Any]] = {}
    mismatched: list[str] = []
    missing: list[str] = []

    for key in required_keys:
        want = expected.get(key)
        have = actual.get(key)
        if want is None or have is None:
            per_key[key] = {"status": "missing", "expected": want, "actual": have}
            missing.append(key)
            continue
        ok = str(want) == str(have)
        per_key[key] = {"status": "match" if ok else "mismatch",
                        "expected": str(want)[:16], "actual": str(have)[:16]}
        if not ok:
            mismatched.append(key)

    status = "ok" if not mismatched and not missing else "blocked"
    report = {"schema": INTEGRITY_SCHEMA, "status": status, "per_key": per_key,
              "mismatched": mismatched, "missing": missing,
              "checked_key_count": len(per_key)}
    if strict and status != "ok":
        raise IntegrityError(
            f"проверка целостности не пройдена: несовпадения={mismatched} отсутствуют={missing}"
        )
    return report


def compute_dataset_hash(index_path: Path) -> str:
    """🔢 Хеш калибровочного набора по его индексу.

    Индекс перечисляет все записи набора, поэтому его содержимое однозначно
    определяет состав калибровки.
    """
    path = Path(index_path)
    if not path.is_file():
        raise FileNotFoundError(f"индекс калибровки не найден: {path}")
    return sha256_file(path)


def compute_code_hash(project_root: Path, patterns: Iterable[str] = ("app6/stage1/*.py", "app6/stage2/*.py")) -> str:
    """🔢 Хеш исполняемого кода стадий (провенанс прогона)."""
    root = Path(project_root)
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(root.glob(pattern)))
    if not files:
        raise FileNotFoundError(f"нет файлов кода под {root} по шаблонам {list(patterns)}")
    return sha256_paths(files, root)
