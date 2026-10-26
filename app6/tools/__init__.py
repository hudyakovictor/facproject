"""🧰 Версионные калибровочные утилиты app6.

Раньше эти скрипты жили в `.runtime/`, который лежит в `.gitignore`. Из-за этого
`test_module/test_a11_artifacts.py` не собирался в чистой среде (CI): тест импортировал
`tools.rebuild_landmark_utility` и получал `ModuleNotFoundError: No module named 'tools'`.
Каталог намеренно внутри `app6`, чтобы импорт шёл через обычный путь пакета, а не через
`sys.path`-заглушку.
"""
