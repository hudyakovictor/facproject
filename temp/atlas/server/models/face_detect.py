"""RetinaFace (ResNet-50) — детектор лица для выравнивания 3DDFA-V3.

YuNet (OpenCV) не находил лица, занимающие больше ~70% кадра: на плотном
портрете скор падал до 0.61 при пороге 0.7. RetinaFace из чекаута 3DDFA-V3
тот же кадр детектирует с скором 0.999, поэтому выбран основным. Цена —
порядка 3 с на CPU вместо ~0.01 с у YuNet.

Обёртка сознательно повторяет сигнатуру `cv2.FaceDetectorYN.detect`:
`detect()` возвращает `(retval, faces)`, где `faces` — массив (N, 15)
[x, y, w, h, 5x(x, y), score] в пикселях исходного изображения, y вниз.
Благодаря `align()` в tddfa.py почти не меняется, а выбор крупнейшего лица
и POS-выравнивание по пяти точкам остаются общими для обоих детекторов.
"""

import sys
from pathlib import Path

import numpy as np

WEIGHTS = "retinaface_resnet50_2020-07-20_old_torch.pth"
# Длинная сторона входного tensor'а. 512 — как в upstream LargeModelInfer;
# дальше predict_jsons сам приводит координаты к пикселям оригинала.
MAX_SIZE = 512


class RetinaFaceDetector:
    """Ленивая загрузка весов и YuNet-совместимый интерфейс."""

    def __init__(self, assets: Path, tddfa_root: Path):
        weights = Path(assets) / WEIGHTS
        if not weights.exists():
            raise FileNotFoundError(f"Нет весов детектора: {weights}")
        face_box = str(Path(tddfa_root) / "face_box")
        # face_box/__init__.py на уровне модуля импортирует mtcnn (TensorFlow),
        # что роняет процесс на этом окружении; ретина-подпакет от него не зависит.
        if face_box not in sys.path:
            sys.path.insert(0, face_box)
        import torch
        from retinaface.predict_single import Model

        self.torch = torch
        self.threshold = 0.7
        self.model = Model(max_size=MAX_SIZE, device="cpu")
        # Только тензоры: weights_only не даёт файлу выполнить код при загрузке.
        state = torch.load(weights, map_location="cpu", weights_only=True)
        self.model.load_state_dict(state)
        self.model.eval()

    def setScoreThreshold(self, value):
        """Имя и сигнатура как у cv2.FaceDetectorYN."""
        self.threshold = float(value)

    def detect(self, rgb: np.ndarray):
        """(retval, (N, 15) float32) — пустой массив, если лица нет."""
        rows = []
        for ann in self.model.predict_jsons(
            np.ascontiguousarray(rgb), self.threshold, 0.4
        ):
            score = float(ann.get("score", -1))
            if score < 0:  # служебный ответ "лиц не найдено"
                continue
            box = np.asarray(ann["bbox"], np.float32)
            points = np.asarray(ann["landmarks"], np.float32).reshape(-1)
            if box.size < 4 or points.size < 10:
                continue
            x1, y1, x2, y2 = box[:4]
            rows.append([x1, y1, x2 - x1, y2 - y1, *points[:10], score])
        if not rows:
            return 0, np.zeros((0, 15), np.float32)
        return 1, np.asarray(rows, np.float32)
