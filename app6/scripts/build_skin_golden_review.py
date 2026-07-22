#!/usr/bin/env python3
"""🏭 FACTORY → Генерирует golden-набор для ручной ревизии skin-каналов.
🔗 DEPENDS ON: stage2.skin.* + previews
📊 METRIC: выход — ревизионный набор для подтверждения статусов ⚠️→✅.
"""
import argparse,csv,html,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--stage1',required=True);p.add_argument('--output',required=True);p.add_argument('--limit',type=int,default=30);a=p.parse_args();root=Path(a.stage1);out=Path(a.output);out.mkdir(parents=True,exist_ok=True);rows=[]
for d in sorted(root.iterdir()):
 if len(rows)>=a.limit:break
 img=d/'skin/previews/atlas_A20_overlay.png';q=d/'skin/previews/quality_weight.png';info=d/'info.json'
 if not img.is_file() or not info.is_file():continue
 meta=json.loads(info.read_text());dst=out/f'{d.name}_atlas.png';shutil.copy2(img,dst);qd=out/f'{d.name}_quality.png';shutil.copy2(q,qd) if q.is_file() else None;rows.append({'photo_id':d.name,'pose_bin':meta.get('pose',{}).get('pose_bin'),'atlas_overlay':dst.name,'quality_overlay':qd.name if qd.is_file() else '','left_right_ok':'','eyes_brows_lips_excluded':'','visibility_ok':'','boundary_ok':'','reviewer':'','notes':''})
with open(out/'manual_review.csv','w',newline='',encoding='utf8') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys() if rows else ['photo_id']);w.writeheader();w.writerows(rows)
body=''.join(f"<section><h3>{html.escape(r['photo_id'])} · {r['pose_bin']}</h3><img src='{r['atlas_overlay']}' width=480><img src='{r['quality_overlay']}' width=480></section>" for r in rows);(out/'index.html').write_text('<meta charset=utf-8><h1>Skin golden review</h1>'+body);print(len(rows))
