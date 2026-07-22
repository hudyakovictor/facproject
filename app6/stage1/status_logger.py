#!/usr/bin/env python3
"""
================================================================================
DEEPUTIN app6 — Unified Status Logger v2
================================================================================
Status flow:
    need_testing → ✅ complete → 🚪 closed

- "need_testing": Function works without errors but needs verification
- "✅ complete": Function verified to work correctly (always shown in console)
- "🚪 closed": Function fully tested and approved (hidden from console)

Manual closing only! User must explicitly change status to "closed".
When closed, STATUS_AUDIT.py is automatically updated.

Future: Isolated test module will auto-validate functions.
"""
import logging
import sys
import os
from typing import Optional

# Configure logging - show all statuses
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout
)

logger = logging.getLogger('facproject')
# Status flow: need_testing → complete → closed
# 🚨 WARNING: любой статус, используемый в log_status(), ОБЯЗАН присутствовать
# в STATUS_FLOW — иначе print_status_summary() и STATUS_AUDIT его не увидят.
STATUS_FLOW = {
    "need_testing": {"next": "complete", "log_level": "warning", "emoji": "🔴"},  # Bright red circle - very visible!
    "complete": {"next": "closed", "log_level": "info", "emoji": "✅"},
    "closed": {"next": None, "log_level": None, "emoji": "🚪"},  # Hidden from console
    "in_progress": {"next": "need_testing", "log_level": "warning", "emoji": "⚠️"},
    "blocked": {"next": None, "log_level": "warning", "emoji": "🚫"},
    "error": {"next": None, "log_level": "error", "emoji": "❌"},
    "experimental": {"next": "need_testing", "log_level": "info", "emoji": "🔬"},
    "deprecated": {"next": None, "log_level": "warning", "emoji": "🗑️"},
}

# Statuses that always show in console
ALWAYS_SHOW = {"need_testing", "complete", "in_progress", "blocked", "error",
               "experimental", "deprecated"}


# 🎯 CRITICAL → единая точка логирования статуса функции
def log_status(func_name: str, status: str, detail: str = ""):
    """Log function status.

    Status values:
        - "need_testing": Works without errors, needs verification
        - "complete": Verified to work correctly (always shown)
        - "closed": Fully tested and approved (hidden from console)
        - "in_progress": Partially implemented
        - "blocked": Blocked by another unimplemented function
        - "error": Has a known bug
        - "deprecated": Outdated
        - "experimental": Experimental
    """
    msg = f"{func_name}: {status}"
    if detail:
        msg += f" — {detail}"

    if status == "need_testing":
        logger.warning(f"🔴 NEED_TESTING: {msg}")
    elif status == "complete":
        logger.info(f"✅ {msg}")
    elif status == "closed":
        # Closed functions are hidden from console
        pass
    elif status == "in_progress":
        logger.warning(f"⚠️ {msg}")
    elif status == "blocked":
        logger.warning(f"🚫 {msg}")
    elif status == "error":
        logger.error(f"❌ {msg}")
    elif status == "deprecated":
        logger.warning(f"🗑️ {msg}")
    elif status == "experimental":
        logger.info(f"🔬 {msg}")
def log_need_testing(func_name: str, detail: str = ""):
    """Mark function as needing testing (works but not verified)."""
    log_status(func_name, "need_testing", detail)


def log_complete(func_name: str, detail: str = "complete"):
    """Mark function as complete (verified to work)."""
    log_status(func_name, "complete", detail)


# 🔒 Ручное закрытие функции + авто-апдейт STATUS_AUDIT.py
def close_function(func_name: str, audit_path: str = "app6/STATUS_AUDIT.py"):
    """Close a function (mark as fully tested and approved).

    This is MANUAL ONLY - user must explicitly close each function.
    Updates STATUS_AUDIT.py automatically.
    """
    logger.info(f"🚪 CLOSED: {func_name}")

    # Update STATUS_AUDIT.py
    _update_audit_status(func_name, "closed", audit_path)


def _update_audit_status(func_name: str, new_status: str, audit_path: str):
    """Update function status in STATUS_AUDIT.py."""
    if not os.path.exists(audit_path):
        return

    with open(audit_path, 'r') as f:
        content = f.read()

    # Find and update the function status
    # Pattern: "func_name": {"status": "...", ...}
    pattern = rf'("{func_name}":\s*\{{"status":\s*")([^"]*)("[^}}]*\}})'
    replacement = rf'\g<1>{new_status}\3'
    new_content = re.sub(pattern, replacement, content)

    if new_content != content:
        with open(audit_path, 'w') as f:
            f.write(new_content)
        logger.info(f"  Updated {audit_path}: {func_name} → {new_status}")


# 🚫 Функция заблокирована другой нереализованной
def log_blocker(func_name: str, blocker: str, detail: str = ""):
    """Log that a function is blocked by another function."""
    msg = f"{func_name}: BLOCKED by {blocker}"
    if detail:
        msg += f" — {detail}"
    logger.warning(f"🚫 {msg}")


# ⚠️ Предупреждение о неполной реализации
def log_warning(func_name: str, message: str):
    """Log a warning about incomplete implementation."""
    logger.warning(f"⚠️ {func_name}: {message}")


def status_warning(func_name: str, message: str):
    """Log a warning status for a subsystem/feature (used by stage1 engine,
    reconstruction and stage2 modules). Alias of log_warning."""
    log_warning(func_name, message)


# ❌ Известный баг в функции
def log_error(func_name: str, message: str):
    """Log an error/bug."""
    logger.error(f"❌ {func_name}: {message}")


# 🔬 Экспериментальная функция
def log_experimental(func_name: str, message: str = ""):
    """Log experimental function."""
    logger.info(f"🔬 {func_name}: {message}")


# Track which functions have been verified
_verified_functions: set = set()
_closed_functions: set = set()


# ✅ Пометить функцию проверенной (complete)
def mark_verified(func_name: str):
    """Mark a function as verified (complete)."""
    _verified_functions.add(func_name)
# 🚪 Пометить функцию закрытой
def mark_closed(func_name: str):
    """Mark a function as closed (fully tested)."""
    _closed_functions.add(func_name)


# 🔍 Проверка: функция verified?
def is_verified(func_name: str) -> bool:
    """Check if function has been verified."""
    return func_name in _verified_functions
# 🔍 Проверка: функция closed?
def is_closed(func_name: str) -> bool:
    """Check if function has been closed."""
    return func_name in _closed_functions


# 📤 Сводка статусов в консоль
def print_status_summary():
    """Print summary of function statuses."""
    print("\n" + "=" * 60)
    print("📊 FUNCTION STATUS SUMMARY")
    print("=" * 60)
    print(f"Verified (complete): {len(_verified_functions)}")
    print(f"Closed (tested): {len(_closed_functions)}")
    print("=" * 60 + "\n")


# Import re for _update_audit_status
import re
