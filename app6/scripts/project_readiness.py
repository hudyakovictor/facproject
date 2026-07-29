#!/usr/bin/env python3
"""Deterministic readiness report: code/UI vs external research inputs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--strict-research',action='store_true');a=p.parse_args();r=a.project_root.resolve()
 code=['app6/run_stage1.py','app6/run_stage2.py','app6/run_stage2b.py','app6/run_stage3.py','app6/run_preflight.py']
 ui=['ui/dist/index.html','ui/START_UI.sh','ui/scripts/smoke_ui.py']
 weights=['assets/face_model.npy','assets/net_recon.pth','assets/large_base_net.pth','assets/retinaface_resnet50_2020-07-20_old_torch.pth','assets/similarity_Lm3D_all.mat']
 datasets=['dataset/main','calibration_dataset/photos']
 missing_code=[x for x in code if not (r/x).is_file()];missing_ui=[x for x in ui if not (r/x).is_file()];missing_weights=[x for x in weights if not (r/x).is_file()];missing_data=[x for x in datasets if not (r/x).exists()]
 report={'schema':'deeputin-project-readiness-v1','code_ready':not missing_code,'ui_ready':not missing_ui,'research_run_ready':not(missing_code or missing_weights or missing_data),'missing_code':missing_code,'missing_ui':missing_ui,'external_inputs':{'missing_model_assets':missing_weights,'missing_dataset_paths':missing_data},'launch':{'ui':'./RUN_PROJECT.sh ui','check':'./RUN_PROJECT.sh check','research':'./RUN_PROJECT.sh preflight --calibration-root calibration_dataset'}}
 print(json.dumps(report,ensure_ascii=False,indent=2))
 return 1 if missing_code or missing_ui or (a.strict_research and not report['research_run_ready']) else 0
if __name__=='__main__':raise SystemExit(main())
