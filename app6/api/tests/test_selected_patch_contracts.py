import unittest
from unittest import mock
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO

from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app6.api.server import _require_removable_output, _uploads_root, app, clear_data
from app6.stage2.pair_planner import plan_pairs
from app6.api.settings import SettingsPayload,_deep_merge,DEFAULT_SETTINGS
class Contracts(unittest.TestCase):
 def test_settings_rejects_uncalibrated_release(self):
  with self.assertRaises(ValueError):SettingsPayload.model_validate({**DEFAULT_SETTINGS,"threshold_mode":"calibrated"})
 def test_deep_merge_preserves_thresholds(self):
  self.assertIn("quality_min",_deep_merge(DEFAULT_SETTINGS,{"thresholds":{"confidence_min":.6}})["thresholds"])
 def test_pair_planner_is_deterministic(self):
  class R:
   def __init__(self,i):self.record_id=str(i);self.date=f"2000-01-{i+1:02d}";self.sequence=i
  a=plan_pairs([R(i) for i in range(12)]);self.assertEqual([(k,x.record_id,y.record_id) for k,x,y in a],[(k,x.record_id,y.record_id) for k,x,y in plan_pairs([R(i) for i in range(12)])])
 def test_upload_rejects_content_that_does_not_match_extension(self):
  with TemporaryDirectory() as td:
   with mock.patch.dict("os.environ",{"DEEPUTIN_UPLOADS_ROOT":td}):
    response=TestClient(app).post(
     "/api/v1/photos/upload",
     files={"file":("2020_01_02.jpg",b"\x89PNG\r\n\x1a\nnot-a-jpeg","image/jpeg")},
    )
   self.assertEqual(response.status_code,400)
   self.assertIn("content",response.json()["detail"])
   self.assertEqual(list(Path(td).rglob("*.*")),[])
 def test_upload_accepts_matching_png_signature(self):
  payload=BytesIO();Image.new("RGB",(1,1)).save(payload,format="PNG")
  with TemporaryDirectory() as td:
   with mock.patch.dict("os.environ",{"DEEPUTIN_UPLOADS_ROOT":td}):
    response=TestClient(app).post(
     "/api/v1/photos/upload",
     files={"file":("2020_01_02.png",payload.getvalue(),"image/png")},
    )
   self.assertEqual(response.status_code,200)
   self.assertTrue(response.json()["stored"])
   self.assertEqual(len(list(Path(td).rglob("*.png"))),1)
 def test_upload_accepts_matching_jpeg_signature(self):
  payload=BytesIO();Image.new("RGB",(1,1)).save(payload,format="JPEG")
  with TemporaryDirectory() as td:
   with mock.patch.dict("os.environ",{"DEEPUTIN_UPLOADS_ROOT":td}):
    response=TestClient(app).post(
     "/api/v1/photos/upload",
     files={"file":("2020_01_02.jpeg",payload.getvalue(),"image/jpeg")},
    )
   self.assertEqual(response.status_code,200)
   self.assertTrue(response.json()["stored"])
   self.assertEqual(len(list(Path(td).rglob("*.jpeg"))),1)
 def test_upload_rejects_signature_only_payload(self):
  with TemporaryDirectory() as td:
   with mock.patch.dict("os.environ",{"DEEPUTIN_UPLOADS_ROOT":td}):
    response=TestClient(app).post(
     "/api/v1/photos/upload",
     files={"file":("2020_01_02.jpg",b"\xff\xd8\xfftruncated","image/jpeg")},
    )
   self.assertEqual(response.status_code,400)
   self.assertIn("decode",response.json()["detail"])
   self.assertEqual(list(Path(td).rglob("*.*")),[])
 def test_upload_rejects_jpeg_truncated_after_verify(self):
  payload=BytesIO();Image.new("RGB",(8,8)).save(payload,format="JPEG")
  truncated=payload.getvalue()[:-1]
  with TemporaryDirectory() as td:
   with mock.patch.dict("os.environ",{"DEEPUTIN_UPLOADS_ROOT":td}):
    response=TestClient(app).post(
     "/api/v1/photos/upload",
     files={"file":("2020_01_02.jpg",truncated,"image/jpeg")},
    )
   self.assertEqual(response.status_code,400)
   self.assertIn("decode",response.json()["detail"])
   self.assertEqual(list(Path(td).rglob("*.*")),[])
 def test_upload_rejects_decompression_bomb_warning(self):
  payload=BytesIO();Image.new("RGB",(2,2)).save(payload,format="PNG")
  with TemporaryDirectory() as td:
   with mock.patch.dict("os.environ",{"DEEPUTIN_UPLOADS_ROOT":td}),mock.patch.object(
    Image,"MAX_IMAGE_PIXELS",2
   ):
    response=TestClient(app).post(
     "/api/v1/photos/upload",
     files={"file":("2020_01_02.png",payload.getvalue(),"image/png")},
    )
   self.assertEqual(response.status_code,400)
   self.assertIn("decode",response.json()["detail"])
   self.assertEqual(list(Path(td).rglob("*.*")),[])
 def test_upload_rejects_when_storage_space_is_insufficient(self):
  payload=BytesIO();Image.new("RGB",(1,1)).save(payload,format="PNG")
  usage=mock.Mock(free=len(payload.getvalue())-1)
  with TemporaryDirectory() as td:
   with mock.patch.dict("os.environ",{"DEEPUTIN_UPLOADS_ROOT":td}),mock.patch(
    "app6.api.server.shutil.disk_usage",return_value=usage
   ):
    response=TestClient(app).post(
     "/api/v1/photos/upload",
     files={"file":("2020_01_02.png",payload.getvalue(),"image/png")},
    )
   self.assertEqual(response.status_code,507)
   self.assertEqual(list(Path(td).rglob("*.*")),[])
 def test_storage_root_override_controls_uploads_outputs_and_clear(self):
  with TemporaryDirectory() as td:
   storage=Path(td).resolve()
   (storage/"api_stage1").mkdir();(storage/"api_stage2").mkdir()
   with mock.patch.dict("os.environ",{"DEEPUTIN_STORAGE_ROOT":str(storage)},clear=False),mock.patch.dict(
    "os.environ",{"DEEPUTIN_UPLOADS_ROOT":""},clear=False
   ):
    self.assertEqual(_uploads_root(),storage/"api_uploads")
    self.assertEqual(_require_removable_output(storage/"custom"),storage/"custom")
    result=clear_data()
   self.assertEqual(sorted(result["removed"]),["api_stage1","api_stage2"])
   self.assertFalse((storage/"api_stage1").exists())
   self.assertFalse((storage/"api_stage2").exists())
 def test_output_guard_rejects_storage_root_itself(self):
  with TemporaryDirectory() as td:
   storage=Path(td).resolve()
   with mock.patch.dict("os.environ",{"DEEPUTIN_STORAGE_ROOT":str(storage)},clear=False):
    with self.assertRaises(HTTPException):
     _require_removable_output(storage)
 def test_storage_root_rejects_filesystem_root(self):
  with mock.patch.dict("os.environ",{"DEEPUTIN_STORAGE_ROOT":str(Path("/").resolve())},clear=False):
   with self.assertRaises(RuntimeError):
    _uploads_root()
 def test_clear_data_fails_closed_when_uploads_overlap_outputs(self):
  with TemporaryDirectory() as td:
   storage=Path(td).resolve();stage1=storage/"api_stage1";uploads=stage1/"uploads"
   uploads.mkdir(parents=True);source=uploads/"2020_01_01.jpg";source.write_bytes(b"source-photo")
   with mock.patch.dict("os.environ",{
    "DEEPUTIN_STORAGE_ROOT":str(storage),
    "DEEPUTIN_UPLOADS_ROOT":str(uploads),
   },clear=False):
    with self.assertRaises(HTTPException):
     clear_data()
   self.assertTrue(source.is_file())
 def test_clear_data_rejects_symlink_escape(self):
  with TemporaryDirectory() as td,TemporaryDirectory() as outside_td:
   storage=Path(td).resolve();outside=Path(outside_td).resolve();victim=outside/"victim.txt"
   victim.write_text("keep",encoding="utf-8");(storage/"api_stage1").symlink_to(outside,target_is_directory=True)
   with mock.patch.dict("os.environ",{
    "DEEPUTIN_STORAGE_ROOT":str(storage),
    "DEEPUTIN_UPLOADS_ROOT":str(storage/"api_uploads"),
   },clear=False):
    with self.assertRaises(HTTPException):
     clear_data()
   self.assertEqual(victim.read_text(encoding="utf-8"),"keep")
if __name__=="__main__":unittest.main()
