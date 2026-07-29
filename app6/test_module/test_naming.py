"""Регрессия `app6/stage1/naming.py` — граничные случаи имён фотографий.

DEV_FIX_TZ P2.13 / P3.22: раньше `parse_photo_name` и `make_photo_id` не имели
ни одного теста на граничные случаи, хотя дата из имени файла — ПЕРВИЧНЫЙ
источник хронологии всего проекта (`app6/AGENTS.md`: «EXIF не является
временной шкалой проекта»). Ошибка разбора имени здесь означает неверную
датировку кадра во всех последующих стадиях, поэтому поведение фиксируется
тестами, а не подразумевается.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app6.stage1.naming import make_photo_id, parse_photo_name

VALID_DIGEST = "a" * 64


# --------------------------------------------------------------------------
# Разбор даты
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("filename", "expected_iso", "expected_stem"),
    [
        ("2000_06_14.jpg", "2000-06-14", "2000_06_14"),
        # Ведущие нули необязательны во входе, но обязательны в canonical_stem:
        # иначе один и тот же день порождал бы два разных photo_id.
        ("1999_8_9.jpg", "1999-08-09", "1999_08_09"),
        ("2015_12_31.png", "2015-12-31", "2015_12_31"),
        # Суффикс ракурса сохраняется — папка называется точно как фото.
        ("2025_03_27_y5p10r0.jpg", "2025-03-27", "2025_03_27_y5p10r0"),
        ("2000_06_14_y-30p-9r3.jpg", "2000-06-14", "2000_06_14_y-30p-9r3"),
    ],
)
def test_parses_valid_names(filename: str, expected_iso: str, expected_stem: str) -> None:
    parsed = parse_photo_name(Path(filename))
    assert parsed.date_iso == expected_iso
    assert parsed.canonical_stem == expected_stem


@pytest.mark.parametrize(
    "filename",
    [
        "photo.jpg",                # нет даты вовсе
        "2000-06-14.jpg",           # дефис вместо подчёркивания — не наш формат
        "2000_13_01.jpg",           # несуществующий месяц
        "2000_02_30.jpg",           # несуществующий день
        "1899_06_14.jpg",           # год вне поддерживаемого диапазона 19xx/20xx
        "",                         # пустое имя
        ".jpg",                     # только расширение
    ],
)
def test_rejects_invalid_names(filename: str) -> None:
    with pytest.raises(ValueError):
        parse_photo_name(Path(filename))


# --------------------------------------------------------------------------
# Копии и нормализация
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("filename", "expected_sequence"),
    [
        ("2000_06_14.jpg", 1),
        ("2000_06_14 (2).jpg", 2),
        ("2000_06_14_3.jpg", 3),
        ("2000_06_14-copy.jpg", 1),
    ],
)
def test_copy_suffix_sequence(filename: str, expected_sequence: int) -> None:
    assert parse_photo_name(Path(filename)).sequence == expected_sequence


def test_double_underscores_and_spaces_normalised() -> None:
    """Разные написания одного кадра не должны расходиться в photo_id."""
    assert parse_photo_name(Path("2000_06_14__y5.jpg")).canonical_stem == "2000_06_14_y5"
    assert parse_photo_name(Path("2000_06_14 y5.jpg")).canonical_stem == "2000_06_14_y5"


def test_trailing_underscore_is_normalised_away() -> None:
    """P3.22 (DEV_FIX_TZ): завершающее `_` не порождает отдельный photo_id.

    `2000_06_14_.jpg` и `2000_06_14.jpg` — одна и та же дата без суффикса,
    поэтому canonical_stem обязан совпадать: иначе один кадр мог бы дважды
    попасть в хронологию под двумя идентификаторами.
    """
    with_underscore = parse_photo_name(Path("2000_06_14_.jpg"))
    plain = parse_photo_name(Path("2000_06_14.jpg"))
    assert with_underscore.canonical_stem == plain.canonical_stem == "2000_06_14"
    assert with_underscore.date_iso == plain.date_iso


# --------------------------------------------------------------------------
# photo_id
# --------------------------------------------------------------------------

def test_photo_id_includes_content_digest_prefix() -> None:
    parsed = parse_photo_name(Path("2000_06_14.jpg"))
    assert make_photo_id(parsed, VALID_DIGEST) == f"2000_06_14__{'a' * 12}"


def test_photo_id_without_digest_falls_back_to_stem() -> None:
    parsed = parse_photo_name(Path("2000_06_14.jpg"))
    assert make_photo_id(parsed, None) == "2000_06_14"


def test_photo_id_rejects_malformed_digest() -> None:
    parsed = parse_photo_name(Path("2000_06_14.jpg"))
    for bad in ("short", "z" * 64, "A" * 63):
        with pytest.raises(ValueError):
            make_photo_id(parsed, bad)


def test_photo_id_is_case_insensitive_for_digest() -> None:
    """Один и тот же файл не должен получить два id из-за регистра хэша."""
    parsed = parse_photo_name(Path("2000_06_14.jpg"))
    assert make_photo_id(parsed, "A" * 64) == make_photo_id(parsed, "a" * 64)


def test_different_content_never_shares_photo_id() -> None:
    """Ключевой инвариант: разные байты — разные каталоги публикации."""
    parsed = parse_photo_name(Path("2000_06_14.jpg"))
    first = make_photo_id(parsed, "a" * 64)
    second = make_photo_id(parsed, "b" * 64)
    assert first != second
