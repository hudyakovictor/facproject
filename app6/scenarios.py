"""Versioned truth labels for chronology-validation scenarios.

These scenarios test a *pipeline response*, not a claim about a photographed
person.  A/B/C are deliberately abstract identities assigned by the archive
adapter; dates used in a scenario are synthetic ordering labels.
"""
from __future__ import annotations
from typing import Final

SCENARIO_SCHEMA: Final[str] = "deeputin-scenario-registry-v1.0"

# Expected events are intentionally expressed as measurement states rather than
# a conclusion such as "different person".  This preserves the forensic scope
# of the production report.
SCENARIOS: Final[dict[str, dict[str, object]]] = {
    "S01": {"pattern": "AAAAAA", "question": "Does a stable same-source sequence remain quiet?",
            "expect": "no persistent transition; false-positive rate is measured"},
    "S02": {"pattern": "AAAABB", "question": "Is one sustained step localized at the A→B boundary?",
            "expect": "one transition candidate at boundary 4; no return"},
    "S03": {"pattern": "AABBAA", "question": "Is a return after a temporary alternate source detected?",
            "expect": "two transitions and one A→B→A return candidate"},
    "S04": {"pattern": "ABABAB", "question": "Does the chronology flag rapid alternation without merging it into drift?",
            "expect": "high transition density / flicker; no monotonic-drift claim"},
    "S05": {"pattern": "AAABBBCCC", "question": "Can two sustained steps be separated and dated?",
            "expect": "two localized transition candidates, at A→B and B→C"},
    "S06": {"pattern": "AABBBA", "question": "Can an asymmetric return be found after a sustained segment?",
            "expect": "two transitions and a return candidate; duration is retained"},
    "S07": {"pattern": "AAAABC", "question": "Can a single-frame outlier be distinguished from a sustained change?",
            "expect": "B is isolated/outlier; C starts a separate, unconfirmed transition"},
    "S08": {"pattern": "AAABAAA", "question": "Does one-frame contamination avoid becoming a persistent event?",
            "expect": "isolated anomaly only; no persistent return claim"},
}
