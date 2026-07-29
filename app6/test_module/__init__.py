"""📦 PACKAGE → Независимый тестовый контур app6.

Контур обязателен по `app6/AGENTS.md`: любое изменение критического модуля
должно иметь тест, способный это изменение опровергнуть.

Состав:
  - `pipeline_guard`     — гейт последовательности стадий (Stage 1 → 2 → 2B → 3);
  - `archive_adapter`    — превращает опубликованный архив ландмарок в записи Stage 2;
  - `scenarios`          — реестр сценариев (A→B→A, смена ракурса, дрейф и т.д.);
  - `runner`             — `python -m app6.test_module.runner execute` —
    обязательная лестница минимальных запусков из `app6/AGENTS.md`;
  - `synthetic_archive`  — генератор синтетического 7×9×3 архива для
    regression-теста самого `runner`, когда реальный архив недоступен.

Каталоги `cache/`, `runs/`, `builds/`, `tests/` игнорируются git и создаются
рантаймом; сами модули контура версионируются.
"""
from __future__ import annotations

__all__ = ["pipeline_guard", "archive_adapter", "scenarios", "runner", "synthetic_archive"]
