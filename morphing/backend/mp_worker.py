"""MediaPipe Face Landmarker как ОТДЕЛЬНЫЙ процесс + общий с валидацией roll-канон.

Почему процесс, а не импорт в сервере. MediaPipe и torch/3DMM-стек морфинга не живут
в одном интерпретаторе: на этой машине и в этом окружении любой порядок заканчивается
SIGSEGV — проверено в обе стороны (реконструкция → MediaPipe: падает на инициализации
_landmarker_; MediaPipe → реконструкция: падает внутри torch). Ни один из падений не
ловится try/except, это нативный крах процесса. Поэтому сервер поднимает воркера
`python -m morphing.backend.mp_worker` и говорит с ним по строкам JSON через stdin/stdout.

Что делает воркер: принимает кадр, отдаёт 478 точек (x, y в пикселях, z в тех же
пикселях, как в валидации) и blendshape-коэффициенты. Клиент применяет
`roll_corrected` — единственный боевой канон (его же импортирует прогон валидации
`metric_shortlist.extract_mp`), поэтому замеры отбора и значения в интерфейсе
сходятся бит-в-бит.

14 из 30 утверждённых метрик без MediaPipe не считаются. Если воркер недоступен
(модель не найдена, процесс упал дважды), прод честно отдаёт эти метрики как null с
причиной, а не подменяет их нулями.
"""
from __future__ import annotations

import base64
import contextlib
import json
import math
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
# Где искать модель: переменная окружения, потом известные места в рабочем дереве.
ASSET_CANDIDATES = (
    os.environ.get("MP_LANDMARKER_TASK", ""),
    str(ROOT / "morphing/backend/assets/models/mediapipe/face_landmarker.task"),
    str(ROOT / "temp/atlas/.cache/models/mediapipe/face_landmarker.task"),
    str(ROOT / "atlas/.cache/models/mediapipe/face_landmarker.task"),
)
TIMEOUT_S = float(os.environ.get("MP_WORKER_TIMEOUT", "20"))


def resolve_asset() -> Path | None:
    for raw in ASSET_CANDIDATES:
        if raw and Path(raw).is_file():
            return Path(raw)
    return None


def roll_corrected(pts: np.ndarray) -> np.ndarray:
    """Снять roll: линия внешних уголков глаз становится горизонтальной.

    Начало координат — середина линии глаз. Без этого любые 2D-отношения («наклон»,
    «асимметрия») содержат наклон головы, а не лицо. Единственный экземпляр функции:
    прогон валидации импортирует её отсюда, поэтому боевые MP-метрики совпадают с
    утверждёнными числами (проверено: max|Δ| = 0 на кэше `.runtime/metric_shortlist`).
    """
    eye_l = (pts[33] + pts[133]) / 2
    eye_r = (pts[362] + pts[263]) / 2
    theta = math.atan2(float(eye_r[1] - eye_l[1]), float(eye_r[0] - eye_l[0]))
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    origin = (eye_l[:2] + eye_r[:2]) / 2
    v = pts[:, :2] - origin
    out = np.empty_like(pts)
    out[:, 0] = cos_t * v[:, 0] + sin_t * v[:, 1]
    out[:, 1] = -sin_t * v[:, 0] + cos_t * v[:, 1]
    out[:, 2] = pts[:, 2]
    return out


# ── воркер (отдельный процесс) ────────────────────────────────────────────────
def _serve() -> int:
    """Читает строки JSON из stdin, пишет ответы в stdout. Никакого torch здесь импортировать нельзя."""
    import cv2
    import mediapipe as mp

    asset = resolve_asset()
    if asset is None:
        print(json.dumps({"fatal": "модель face_landmarker.task не найдена"}), flush=True)
        return 2
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(asset),
                                          delegate=mp.tasks.BaseOptions.Delegate.CPU),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=False,
    )
    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
    print(json.dumps({"ready": True}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            raw = base64.b64decode(req["image_b64"])
            img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("кадр не декодировался")
            h, w = img.shape[:2]
            res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                             data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            if not res.face_landmarks or len(res.face_landmarks[0]) != 478:
                resp = {"id": req.get("id"), "ok": False, "error": "лицо не найдено (478 точек)"}
            else:
                lm = res.face_landmarks[0]
                pts = [[q.x * w, q.y * h, q.z * w] for q in lm]
                blend = ({s.category_name: float(s.score) for s in res.face_blendshapes[0]}
                         if res.face_blendshapes else {})
                resp = {"id": req.get("id"), "ok": True, "points": pts,
                        "blendshapes": blend, "width": w, "height": h}
        except Exception as exc:  # noqa: BLE001 — воркер не должен умирать от одного кадра
            resp = {"id": None, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(resp), flush=True)
    return 0


# ── клиент (в процессе сервера) ───────────────────────────────────────────────
class MediaPipeUnavailable(RuntimeError):
    """Воркер не поднялся или упал: MP-ветка метрик недоступна, прод это показывает."""


class FaceNotFound(MediaPipeUnavailable):
    """Воркер живой, но лица в кадре нет: для сервера это 400, а не 503."""


class LandmarkerClient:
    """Один тёплый дочерний процесс MediaPipe, запрос-ответ по строкам JSON.

    Пул потоков нужен только ради таймаута на `readline`: зависший воркер не должен
    вешать HTTP-запрос. При таймауте или мёртвом процессе — одна попытка перезапуска.
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mp-read")
        self._seq = 0

    # -- жизненный цикл --
    def _start(self) -> None:
        if not resolve_asset():
            raise MediaPipeUnavailable("модель face_landmarker.task не найдена в известных путях")
        if shutil.which(sys.executable) is None and not Path(sys.executable).exists():
            raise MediaPipeUnavailable(f"интерпретатор {sys.executable} недоступен")
        # PYTHONPATH нужен, чтобы `-m morphing.backend.mp_worker` нашёл пакет из любого cwd.
        env = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""),
               "NO_ALBUMENTATIONS_UPDATE": "1", "GLOG_minloglevel": "2",
               "TF_CPP_MIN_LOG_LEVEL": "2"}
        self._proc = subprocess.Popen(  # noqa: S603 — свой интерпретатор, без shell
            [sys.executable, "-m", "morphing.backend.mp_worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, cwd=str(ROOT), env=env, bufsize=1,
        )
        try:
            hello = self._read_line(timeout=TIMEOUT_S)
        except MediaPipeUnavailable:
            self._kill()
            raise
        if not hello or not hello.get("ready"):
            self._kill()
            raise MediaPipeUnavailable(f"воркер не готов: {hello}")

    def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        # Убить воркера — не то, что может сломать запрос: процесс всё равно больше
        # не используется, а врать о нём незачем.
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            proc.kill()
            proc.wait(timeout=5)

    def _read_line(self, timeout: float) -> dict[str, Any] | None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            raise MediaPipeUnavailable("воркер не запущен")
        future = self._pool.submit(proc.stdout.readline)
        try:
            line = future.result(timeout=timeout)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise MediaPipeUnavailable(f"воркер молчит больше {timeout}s") from exc
        if not line:
            raise MediaPipeUnavailable("воркер закрыл поток (скорее всего, упал)")
        return json.loads(line)

    def _request(self, image_b64: str) -> dict[str, Any]:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise MediaPipeUnavailable("воркер не запущен")
        self._seq += 1
        proc.stdin.write(json.dumps({"id": self._seq, "image_b64": image_b64}) + "\n")
        proc.stdin.flush()
        resp = self._read_line(timeout=TIMEOUT_S)
        if resp is None:
            raise MediaPipeUnavailable("пустой ответ воркера")
        if resp.get("id") != self._seq:
            raise MediaPipeUnavailable(f"ответ не по запросу: {resp.get('id')} != {self._seq}")
        return resp

    # -- публичное API --
    def detect(self, image_bytes: bytes) -> dict[str, Any]:
        """{points: (478,3) float32 после roll-канона, blendshapes: dict, points_raw, image_size}.

        `MediaPipeUnavailable` — ветка недоступна (воркер/модель); `FaceNotFound` —
        воркер живой, лица в кадре нет.
        """
        payload = base64.b64encode(image_bytes).decode("ascii")
        with self._lock:
            for attempt in (1, 2):
                if self._proc is None or self._proc.poll() is not None:
                    if attempt > 1:
                        code = self._proc.returncode if self._proc is not None else None
                        raise MediaPipeUnavailable(f"воркер умер (exit {code})")
                    self._kill()
                    self._start()
                try:
                    resp = self._request(payload)
                except MediaPipeUnavailable:
                    if attempt > 1:
                        raise
                    self._kill()
                    continue
                if resp.get("ok"):
                    pts = np.asarray(resp["points"], dtype=np.float32)
                    return {"points": roll_corrected(pts),
                            "points_raw": pts,
                            "blendshapes": resp.get("blendshapes", {}),
                            "image_size": (resp.get("width"), resp.get("height"))}
                # «лица нет» — не поломка воркера: процесс живой, спрашиваем дальше
                raise FaceNotFound(str(resp.get("error") or "лицо не найдено"))
        raise MediaPipeUnavailable("исчерпаны попытки")

    def close(self) -> None:
        with self._lock:
            self._kill()
        self._pool.shutdown(wait=False)


_CLIENT: LandmarkerClient | None = None
_CLIENT_LOCK = threading.Lock()


def client() -> LandmarkerClient:
    """Один воркер на процесс сервера, лениво."""
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = LandmarkerClient()
        return _CLIENT


def main() -> int:
    return _serve()


if __name__ == "__main__":
    raise SystemExit(main())
