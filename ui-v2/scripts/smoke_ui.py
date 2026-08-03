#!/usr/bin/env python3
"""🚪 ENTRY POINT → Post-build smoke test for the React/Vite UI.

`app6/scripts/project_readiness.py` требует этот файл для `ui_ready: true`.
Он не подменяет `npm run typecheck`/`check_contract.py`, а проверяет то, что
они не покрывают: что production-сборка (`ui/dist/`) физически раздаётся
статическим сервером и содержит контрактные маркеры (9 pose bins, 8 режимов,
API endpoint, Fix Capsule schema, обязательный дисклеймер «НЕ ВЕРДИКТ») уже
после минификации, а не только в исходниках.

Использование:
    cd ui && npm ci && npm run build
    python scripts/smoke_ui.py

🚨 WARNING: не запускает браузер и не рендерит DOM — это HTTP-уровневая
проверка раздачи собранных статических файлов, а не UI/e2e тест.
"""
from __future__ import annotations

import http.client
import json
import re
import socket
import threading
from contextlib import closing
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

#: Контрактные маркеры, обязанные пережить минификацию (см. ui/API_CONTRACT.md
#: и ui/scripts/check_contract.py — тот же список источников истины).
POSE_BINS = (
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)
VIEW_MODES = ("FULL", "MATRIX", "CLUSTER", "COMPARE", "INSPECTOR", "DRIFT", "METRICS", "STATS")
REQUIRED_STRINGS = (
    *POSE_BINS, *VIEW_MODES,
    "/api/v1/timeline", "deeputin.fix-capsule.v2", "НЕ ВЕРДИКТ",
)


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _asset_paths(index_html: str) -> list[str]:
    """🔍 QUERY → Извлечь пути к JS/CSS ассетам, на которые ссылается index.html."""
    return sorted(set(re.findall(r'(?:src|href)="(/assets/[^"]+)"', index_html)))


def check_dist_exists() -> list[str]:
    """🚧 GATE → Собран ли dist вообще."""
    errors = []
    if not DIST.is_dir():
        errors.append(f"каталог сборки не найден: {DIST}. Выполните: npm run build")
        return errors
    if not (DIST / "index.html").is_file():
        errors.append(f"нет dist/index.html")
    return errors


def check_served_content() -> tuple[list[str], dict[str, object]]:
    """🚧 GATE → Поднять статический сервер на dist/ и проверить реальную раздачу."""
    errors: list[str] = []
    detail: dict[str, object] = {}
    port = _free_port()

    class _QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(DIST), **kwargs)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
            pass

    server = HTTPServer(("127.0.0.1", port), _QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", "/")
        response = conn.getresponse()
        index_body = response.read().decode("utf-8", errors="replace")
        if response.status != 200:
            errors.append(f"GET / вернул {response.status}, ожидался 200")
        if '<div id="root">' not in index_body:
            errors.append('index.html не содержит <div id="root"> — точку монтирования React')
        conn.close()

        assets = _asset_paths(index_body)
        if not assets:
            errors.append("index.html не ссылается ни на один /assets/*")

        combined_asset_text = ""
        for asset_path in assets:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("GET", asset_path)
            asset_response = conn.getresponse()
            body = asset_response.read()
            if asset_response.status != 200:
                errors.append(f"GET {asset_path} вернул {asset_response.status}")
            else:
                combined_asset_text += body.decode("utf-8", errors="replace")
            conn.close()

        missing = [marker for marker in REQUIRED_STRINGS if marker not in combined_asset_text]
        if missing:
            errors.append(f"собранный бандл не содержит контрактные маркеры: {missing}")
        detail = {
            "port": port,
            "assets_served": assets,
            "required_markers_checked": len(REQUIRED_STRINGS),
            "missing_markers": missing,
        }
    finally:
        server.shutdown()
        thread.join(timeout=5)
    return errors, detail


def main() -> int:
    errors = check_dist_exists()
    detail: dict[str, object] = {}
    if not errors:
        serve_errors, detail = check_served_content()
        errors.extend(serve_errors)

    report = {
        "schema": "deeputin-ui-smoke-v1",
        "status": "pass" if not errors else "fail",
        "dist_dir": str(DIST),
        "errors": errors,
        "detail": detail,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
