"""🔄 CALLBACK (pytest) → целостность статус-системы: STATUS_FLOW, STATUS_AUDIT ↔ код.

🎯 CRITICAL → регрессия на ошибки AUDIT-5/6: запрещает возврат расхождений
(статусы вне STATUS_FLOW, orphan-записи аудита, рассинхрон статусов, дубли log_status).
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app6"

STATUS_MAP = {
    "🔴 need_testing": "need_testing", "✅ COMPLETE": "complete", "✅ complete": "complete",
    "🚪 CLOSED": "closed", "⚠️ IN PROGRESS": "in_progress", "🗑️ DEPRECATED": "deprecated",
    "🔬 EXPERIMENTAL": "experimental",
}


def _own_modules():
    for p in sorted(APP.rglob("*.py")):
        s = str(p)
        if "__pycache__" in s or "3ddfa" in s or "STATUS_AUDIT" in p.name:
            continue
        try:
            yield p, ast.parse(p.read_text(encoding="utf-8", errors="replace")), p.read_text(encoding="utf-8", errors="replace")
        except SyntaxError:
            continue


def _code_statuses():
    """function-name -> status из первого log_status() в теле."""
    out = {}
    for _p, tree, src in _own_modules():
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seg = ast.get_source_segment(src, n) or ""
                m = re.search(r'log_status\(\s*"[^"]+"\s*,\s*"([^"]+)"', seg)
                if m and n.name not in out:
                    out[n.name] = m.group(1)
    return out


def _audit_statuses():
    sa = (APP / "STATUS_AUDIT.py").read_text(encoding="utf-8")
    return {m.group(1).split(".")[-1]: m.group(2)
            for m in re.finditer(r'"([A-Za-z_][A-Za-z0-9_.]*)":\s*\{"status":\s*"([^"]+)"', sa)}


class StatusRegistryTests(unittest.TestCase):
    def test_log_statuses_within_status_flow(self):
        from app6.stage1.status_logger import STATUS_FLOW
        bad = []
        for p, _t, src in _own_modules():
            for m in re.finditer(r'log_status\(\s*"[^"]+"\s*,\s*"([^"]+)"', src):
                if m.group(1) not in STATUS_FLOW:
                    bad.append(f"{p.relative_to(ROOT)}: {m.group(1)}")
        self.assertEqual([], bad, "statuses outside STATUS_FLOW (see AUDIT-6 B1)")

    def test_status_audit_names_exist_in_code(self):
        declared = _audit_statuses()
        defined = set()
        for _p, tree, _s in _own_modules():
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    defined.add(n.name)
        missing = sorted(fn for fn in declared if fn.split(".")[-1] not in defined)
        self.assertEqual([], missing, "STATUS_AUDIT declares names absent from code")

    def test_audit_matches_code_status(self):
        declared = _audit_statuses()
        coded = _code_statuses()
        mism = []
        for fn, dst in declared.items():
            want = STATUS_MAP.get(dst)
            got = coded.get(fn)
            if want is not None and got is not None and got != want:
                mism.append(f"{fn}: audit={dst} code={got}")
        self.assertEqual([], mism, "STATUS_AUDIT/code status mismatch (see AUDIT-6 C1)")

    def test_no_orphan_code_statuses(self):
        declared = _audit_statuses()
        coded = _code_statuses()
        orphans = sorted(set(coded) - set(declared))
        self.assertEqual([], orphans, "functions log status but missing from STATUS_AUDIT")

    def test_no_duplicated_log_status_calls(self):
        """log_status, идущий дважды подряд с идентичными аргументами (регрессия AUDIT-5 B1)."""
        bad = []
        for p, tree, src in _own_modules():
            lines = src.splitlines()
            for i in range(len(lines) - 1):
                if "log_status(" in lines[i]:
                    def full(idx):
                        buf = []
                        while idx < len(lines):
                            buf.append(lines[idx].strip())
                            t = " ".join(buf)
                            if t.count("(") <= t.count(")"):
                                return " ".join(t.split()), idx
                            idx += 1
                        return " ".join(" ".join(buf).split()), idx
                    s1, j = full(i)
                    if j + 1 < len(lines) and "log_status(" in lines[j + 1]:
                        s2, _ = full(j + 1)
                        if s1 == s2:
                            bad.append(f"{p.relative_to(ROOT)}:{i + 1}")
        self.assertEqual([], bad, "duplicated adjacent log_status (patch double-apply)")


if __name__ == "__main__":
    unittest.main()
