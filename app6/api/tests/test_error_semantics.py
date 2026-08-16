"""🚪 CONTRACT → Семантика ошибок API (ER-166).

Фиксирует единое правило для всех /api/v1/* эндпоинтов:
  400 = неверный/неподдерживаемый запрос клиента (неизвестный дискриминатор/имя);
  404 = валидный идентификатор, но данных нет среди сохранённых;
  409 = конфликт с состоянием (зависимость не настроена / операция невозможна);
  422 = содержимое корректного ресурса повреждено/необрабатываемо;
  503 = временная недоступность необходимой зависимости.

Полная таблица — в docs/final/04_DATA_CONTRACTS.md (раздел «Ошибки API»).
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from fastapi.testclient import TestClient

from app6.api.server import app


class ErrorSemanticsContracts(unittest.TestCase):
    """Проверяет соответствие кода задокументированной таблице статусов."""

    def test_unsupported_artifact_name_returns_400(self):
        # Дискриминатор артефакта отсутствует в allowlist => 400 (не 404).
        with mock.patch.dict("os.environ", {}, clear=False):
            response = TestClient(app).get("/api/v1/photos/whatever/artifacts/evil.txt")
        self.assertEqual(response.status_code, 400)

    def test_unsupported_landmark_count_returns_400(self):
        # count/space вне известного перечня => 400.
        with mock.patch.dict("os.environ", {}, clear=False):
            response = TestClient(app).get("/api/v1/photos/x/landmarks/99/raw")
        self.assertEqual(response.status_code, 400)

    def test_unsupported_landmark_space_returns_400(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            response = TestClient(app).get("/api/v1/photos/x/landmarks/106/bogus")
        self.assertEqual(response.status_code, 400)

    def test_unsupported_image_kind_returns_400(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            response = TestClient(app).get("/api/v1/photos/x/image", params={"kind": "malware"})
        self.assertEqual(response.status_code, 400)

    def test_unknown_job_returns_404(self):
        # Валидный идентификатор, которого нет => 404.
        with mock.patch.dict("os.environ", {}, clear=False):
            response = TestClient(app).get("/api/v1/jobs/nope-not-a-job")
        self.assertEqual(response.status_code, 404)

    def test_photo_image_without_stage1_returns_409(self):
        # Зависимость Stage 1 не настроена => 409 (конфликт с состоянием).
        with mock.patch.dict("os.environ", {"DEEPUTIN_STAGE1_ROOT": ""}, clear=False):
            response = TestClient(app).get("/api/v1/photos/x/image", params={"kind": "original"})
        self.assertEqual(response.status_code, 409)

    def test_photo_image_photo_missing_returns_404(self):
        # Stage 1 настроен, но фото отсутствует => 404.
        with TemporaryDirectory() as td:
            root = Path(td)
            # _stage1_root() требует main_timeline.csv, чтобы считать вывод готовым.
            (root / "main_timeline.csv").write_text(
                "photo_id,date,same_date_sequence,pose_bin\n", encoding="utf-8"
            )
            with mock.patch.dict(
                "os.environ", {"DEEPUTIN_STAGE1_ROOT": str(root)}, clear=False
            ):
                response = TestClient(app).get(
                    "/api/v1/photos/absent_photo/image", params={"kind": "original"}
                )
            self.assertEqual(response.status_code, 404)

    def test_unknown_job_cancel_returns_409(self):
        # Нельзя отменить несуществующий/терминальный job => 409.
        with mock.patch.dict("os.environ", {}, clear=False):
            response = TestClient(app).post("/api/v1/jobs/ghost/cancel")
        self.assertEqual(response.status_code, 409)

    def test_mesh_bfm_unavailable_returns_503(self):
        # BFM-геометрия (внешняя зависимость) недоступна => 503.
        import app6.api.server as server

        fake_record = mock.Mock(record_id="p1")
        with mock.patch.dict("os.environ", {}, clear=False), mock.patch.object(
            server, "_main_record", return_value=fake_record
        ), mock.patch("app6.api.server.is_bfm_available", return_value=False):
            response = TestClient(app).get("/api/v1/photos/p1/mesh")
        self.assertEqual(response.status_code, 503)

    def test_compare_upload_is_501_not_supported_in_env(self):
        # Метод требует недоступную Stage 1-модель => 501.
        with mock.patch.dict("os.environ", {}, clear=False):
            response = TestClient(app).post(
                "/api/v1/compare/upload",
                params={"photo_id": "x"},
                files={"file": ("2020_01_01.jpg", b"\xff\xd8\xff", "image/jpeg")},
            )
        self.assertEqual(response.status_code, 501)


if __name__ == "__main__":
    unittest.main()