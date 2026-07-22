#!/usr/bin/env python3
"""🏭 FACTORY → Генератор страницы FUNCTION_STATUS_LOG.md из кода.

🚪 ENTRY POINT: python -m app6.scripts.build_function_status_log
🔗 DEPENDS ON: AST-скан app6/**/*.py + STATUS_AUDIT.py
💡 NOTE: страница генерируемая — ручные правки будут перезаписаны.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app6"
OUT = APP / "FUNCTION_STATUS_LOG.md"

EMOJI_STATUS = {"✅": "✅ VERIFIED", "⚠️": "⚠️ IN PROGRESS", "❌": "❌ KNOWN ISSUE",
                "🔬": "🔬 EXPERIMENTAL", "🗑️": "🗑️ DEPRECATED"}
ROLE_EMOJI = ["🎯", "🔗", "💡", "🚨", "📊", "🏭", "🚪", "🔄", "📝", "📤", "⚙️",
              "🔢", "🔍", "🚧", "📝", "🔀", "🔒", "📜", "📦"]


def _is_own(p: Path) -> bool:
    s = str(p)
    return (p.suffix == ".py" and "__pycache__" not in s and ".backup_audit" not in s
            and "3ddfa" not in s and "FFHQ" not in s)


def scan() -> dict:
    rows: dict[str, list[dict]] = {}
    for p in sorted(APP.rglob("*.py")):
        if not _is_own(p):
            continue
        rel = p.relative_to(ROOT).as_posix()
        src = p.read_text(encoding="utf-8", errors="replace")
        lines = src.splitlines()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body_src = ast.get_source_segment(src, node) or ""
            logs = re.findall(r"log_status\(\s*[\"'][^\"']+[\"']\s*,\s*[\"']([^\"']+)[\"']", body_src)
            doc = ast.get_docstring(node) or ""
            above = []
            ln = node.lineno - 2
            while ln >= 0 and len(above) < 6:
                t = lines[ln].strip()
                if t.startswith("#"):
                    above.append(t)
                    ln -= 1
                else:
                    break
            region = doc + " " + " ".join(above)
            status = sorted({EMOJI_STATUS[e] for e in EMOJI_STATUS if e in region})
            roles = [e for e in ROLE_EMOJI if e in region]
            rows.setdefault(rel, []).append({
                "name": node.name, "line": node.lineno,
                "log_status": sorted(set(logs)), "emoji_status": status,
                "roles": roles, "public": not node.name.startswith("_"),
            })
    return rows


def fmt_status(func: dict) -> str:
    parts = []
    if func["log_status"]:
        parts.append("log: " + ", ".join(func["log_status"]))
    if func["emoji_status"]:
        parts.append(" ".join(func["emoji_status"]))
    return "; ".join(parts) if parts else "—"


def main() -> int:
    rows = scan()
    total = sum(len(v) for v in rows.values())
    covered = sum(1 for v in rows.values() for f in v if f["log_status"] or f["emoji_status"] or f["roles"])
    out = [
        "# FUNCTION STATUS LOG — app6",
        "",
        "> ⚙️ СГЕНЕРИРОВАНО АВТОМАТИЧЕСКИ: `python -m app6.scripts.build_function_status_log`.",
        "> Ручные правки будут перезаписаны. Декларативный аудит — в `STATUS_AUDIT.py`,",
        "> правила статусов — в `CONVENTIONS.py`, рантайм-флоу — в `stage1/status_logger.py`.",
        "",
        "## Поток статусов",
        "",
        "```",
        "🔴 need_testing → ✅ complete → 🚪 closed",
        "дополнительно: ⚠️ in_progress · 🚫 blocked · ❌ error · 🔬 experimental · 🗑️ deprecated",
        "```",
        "",
        f"## Покрытие: {covered}/{total} функций имеют статус-маркеры "
        f"({100.0 * covered / max(total, 1):.1f}%)",
        "",
        "| Модуль | Функция | Строка | Статус(ы) | Роли |",
        "|---|---|---:|---|---|",
    ]
    for rel, funcs in rows.items():
        for f in funcs:
            roles = " ".join(f["roles"]) if f["roles"] else "—"
            vis = "" if f["public"] else " 🔒"
            out.append(f"| `{rel}` | `{f['name']}`{vis} | {f['line']} | {fmt_status(f)} | {roles} |")
    out += [
        "",
        "## Как добавлять статус функции",
        "",
        "1. В коде: `log_status(\"func_name\", \"need_testing\", detail)` в начале тела функции",
        "   (ПОСЛЕ docstring — иначе docstring теряется для help()/IDE).",
        "2. Комментарием рядом с def по системе CONVENTIONS (✅/⚠️/❌/🔬/🗑️ + роли 🎯/🔗/…).",
        "3. Обновить декларативный блок в `STATUS_AUDIT.py`.",
        "4. Перегенерировать эту страницу (см. заголовок).",
        "",
    ]
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} with {total} functions from {len(rows)} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
