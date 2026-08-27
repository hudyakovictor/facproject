"""🔢 Number Formatting — русская локализация чисел.

Правила:
  - Десятичный разделитель: запятая (,)
  - Разделитель тысяч: пробел ( )
  - Auto precision: больше цифр → меньше знаков

Форматы:
  percentage: 0.9955 → "99,6%"
  z_score:    3.7148 → "3,7"
  distance:   0.0028 → "2,80 мм"
  ratio:      0.9071 → "0,907"
  count:      1234   → "1 234"
  days:       97     → "97 дн."
  bf:         45.2   → "45,2"
"""
from __future__ import annotations

import math
from typing import Optional


def fmt(value: float, format_type: str = "auto", precision: Optional[int] = None) -> str:
    """
    Format a number for Russian locale.
    
    Args:
        value: Number to format
        format_type: "auto" | "percentage" | "z_score" | "distance_mm" | "ratio" | "count" | "days" | "bf"
        precision: Override auto precision
    
    Returns:
        Formatted string
    """
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "—"
    
    value = float(value)
    
    if format_type == "percentage":
        return _fmt_percentage(value, precision)
    elif format_type == "z_score":
        return _fmt_z_score(value, precision)
    elif format_type == "distance_mm":
        return _fmt_distance(value, precision)
    elif format_type == "ratio":
        return _fmt_ratio(value, precision)
    elif format_type == "count":
        return _fmt_count(value)
    elif format_type == "days":
        return _fmt_days(value)
    elif format_type == "bf":
        return _fmt_bf(value, precision)
    elif format_type == "angle":
        return _fmt_angle(value, precision)
    else:
        return _fmt_auto(value, precision)


def _auto_precision(value: float) -> int:
    """Determine precision based on magnitude."""
    abs_val = abs(value)
    if abs_val == 0:
        return 2
    elif abs_val >= 100:
        return 0
    elif abs_val >= 10:
        return 1
    elif abs_val >= 1:
        return 2
    elif abs_val >= 0.1:
        return 3
    elif abs_val >= 0.01:
        return 4
    else:
        return -1  # scientific


def _apply_locale(s: str) -> str:
    """Apply Russian locale: dot → comma."""
    return s.replace(".", ",")


def _add_thousands_spaces(s: str) -> str:
    """Add spaces as thousands separator."""
    if "." in s:
        integer_part, decimal_part = s.split(".", 1)
    elif "," in s:
        integer_part, decimal_part = s.split(",", 1)
        return _add_thousands_spaces_int(integer_part) + "," + decimal_part
    else:
        return _add_thousands_spaces_int(s)
    
    return _add_thousands_spaces_int(integer_part) + "," + decimal_part


def _add_thousands_spaces_int(s: str) -> str:
    """Add spaces to integer part."""
    negative = s.startswith("-")
    digits = s.lstrip("-")
    
    result = ""
    for i, d in enumerate(reversed(digits)):
        if i > 0 and i % 3 == 0:
            result = " " + result
        result = d + result
    
    return "-" + result if negative else result


def _fmt_auto(value: float, precision: Optional[int]) -> str:
    """Auto format."""
    p = precision if precision is not None else _auto_precision(value)
    
    if p == -1:
        # Scientific notation
        s = f"{value:.2e}"
        return _apply_locale(s)
    
    s = f"{value:.{p}f}"
    return _apply_locale(s)


def _fmt_percentage(value: float, precision: Optional[int]) -> str:
    """Format as percentage (value is 0-1)."""
    pct = value * 100
    p = precision if precision is not None else 1
    s = f"{pct:.{p}f}%"
    return _apply_locale(s)


def _fmt_z_score(value: float, precision: Optional[int]) -> str:
    """Format z-score."""
    p = precision if precision is not None else 1
    s = f"{value:.{p}f}"
    return _apply_locale(s)


def _fmt_distance(value: float, precision: Optional[int]) -> str:
    """Format distance in mm."""
    if value < 0.01:
        # Convert to micrometers
        um = value * 1000
        s = f"{um:.0f} мкм"
    else:
        p = precision if precision is not None else 2
        s = f"{value:.{p}f} мм"
    return _apply_locale(s)


def _fmt_ratio(value: float, precision: Optional[int]) -> str:
    """Format ratio."""
    p = precision if precision is not None else 3
    s = f"{value:.{p}f}"
    return _apply_locale(s)


def _fmt_count(value: float) -> str:
    """Format count with thousands separator."""
    s = f"{int(value)}"
    return _add_thousands_spaces_int(s)


def _fmt_days(value: float) -> str:
    """Format days."""
    d = int(value)
    if d == 1:
        return "1 день"
    elif 2 <= d <= 4:
        return f"{d} дня"
    else:
        return f"{d} дн."


def _fmt_bf(value: float, precision: Optional[int]) -> str:
    """Format Bayes Factor."""
    if value >= 1000:
        return f"{value:.0f}"
    p = precision if precision is not None else 1
    s = f"{value:.{p}f}"
    return _apply_locale(s)


def _fmt_angle(value: float, precision: Optional[int]) -> str:
    """Format angle in degrees."""
    p = precision if precision is not None else 1
    s = f"{value:.{p}f}°"
    return _apply_locale(s)


def fmt_ci(lower: float, upper: float, format_type: str = "auto") -> str:
    """Format confidence interval."""
    l = fmt(lower, format_type)
    u = fmt(upper, format_type)
    return f"95% ДИ: {l} — {u}"
