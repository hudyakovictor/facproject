"""🚪 ENTRY POINT → Skin-блок отчёта Stage 3.
🚪 API: run()
🔗 DEPENDS ON: report.render_report() + morphing_contract
"""
import json
from pathlib import Path
from .report import render_report
from app6.stage1.skin.serialization import atomic_json
class SkinStage3Engine:
 def __init__(self,stage2_root,output):self.root=Path(stage2_root);self.out=Path(output)
 # 🚪 ENTRY POINT skin-блока отчёта
 def run(self):
  self.out.mkdir(parents=True,exist_ok=True);pairs=json.loads((self.root/'skin_pairs.json').read_text());chron=json.loads((self.root/'skin_chronology.json').read_text());symmetry=json.loads((self.root/'skin_symmetry.json').read_text()) if (self.root/'skin_symmetry.json').is_file() else None;manifest=json.loads((self.root/'manifest.json').read_text());data={'schema':'skin-stage3-v1','methodology':'original photo pixels under face_mask; UV render is visualization only','pairs':pairs,'chronology':chron,'symmetry':symmetry,'stage2_manifest':manifest,'limitations':['not identity verdict','not material verdict','surface units are not mm']};atomic_json(self.out/'report_data.json',data);render_report(pairs['pairs'],self.out/'index.html',{'stage2_manifest':manifest,'chronology_schema':chron.get('schema')},chronology=chron);atomic_json(self.out/'validation.json',{'schema':'skin-stage3-validation-v1','status':'complete','files':['index.html','report_data.json']});return data
