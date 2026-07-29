"""Регрессия: digest_file() → make_photo_id() контракт длины хеша (bug 2026-07-29).

`app6.stage1.naming.make_photo_id()` требует ровно 64 hex-символа
(`[0-9a-f]{64}`). До исправления `digest_file()` использовал
`blake2b(digest_size=16)`, дающий 32 символа — то есть каждый реальный
Stage 1 прогон падал бы на первом же фото при построении `photo_id`
(`app6/stage1/engine.py:220-221`). Обнаружено при разработке `app6/api`
(`POST /api/v1/photos/upload`), которое воспроизводит тот же вызов.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app6.stage1.naming import make_photo_id, parse_photo_name
from app6.stage1.utils import digest_file


def test_digest_file_produces_64_hex_chars(tmp_path: Path) -> None:
    sample = tmp_path / "1999_08_09.jpg"
    sample.write_bytes(b"not a real jpeg, just content for hashing")
    digest = digest_file(sample)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_digest_file_output_accepted_by_make_photo_id(tmp_path: Path) -> None:
    """Точное воспроизведение engine.py: parse_photo_name + digest_file → make_photo_id."""
    sample = tmp_path / "1999_08_09.jpg"
    sample.write_bytes(b"not a real jpeg, just content for hashing")
    parsed = parse_photo_name(sample)
    digest = digest_file(sample)
    photo_id = make_photo_id(parsed, digest)
    assert photo_id.startswith("1999_08_09__")


def test_different_content_yields_different_photo_id(tmp_path: Path) -> None:
    """Коллизии контента не должны публиковаться в одну папку с тем же именем даты."""
    a = tmp_path / "1999_08_09.jpg"
    b = tmp_path / "1999_08_09_2.jpg"
    a.write_bytes(b"content A")
    b.write_bytes(b"content B")
    parsed_a, parsed_b = parse_photo_name(a), parse_photo_name(b)
    id_a = make_photo_id(parsed_a, digest_file(a))
    id_b = make_photo_id(parsed_b, digest_file(b))
    assert id_a != id_b


def test_missing_digest_rejected() -> None:
    with pytest.raises(ValueError):
        make_photo_id(parse_photo_name(Path("1999_08_09.jpg")), "short")
