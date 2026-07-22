"""📤 Рендер skin-отчёта + строгая валидация языка формулировок.
🚪 API: validate_language(), render_report()
🚨 WARNING: forbidden-формулировки ('диагноз', возраст-оценка) отклоняются.
"""
from __future__ import annotations
import html,json
from pathlib import Path
FORBIDDEN=('доказано, что это силикон','доказано, что это другой человек','биологический возраст равен')
# 🚨 Ревизия формулировок (запрещённые = отказ)
def validate_language(text):
 for q in FORBIDDEN:
  if q in text.lower():raise ValueError(f'unsupported verdict language: {q}')
# 📤 Рендер финального skin-отчёта
def render_report(pair_results,output,provenance,chronology=None):
 rows=[]
 for p in pair_results:
  for z in p.get('zones',[]):rows.append(f"<tr><td>{html.escape(str(p.get('photo_a')))}</td><td>{html.escape(str(p.get('photo_b')))}</td><td>{z['zone']}</td><td>{z['status']}</td><td>{z.get('coverage_sym',0):.3f}</td></tr>")
 changes=''.join(f"<tr><td>{html.escape(str(x.get('interval')))}</td><td>{x.get('zone')}</td><td>{x.get('family')}</td><td>{x.get('type')}</td><td>{x.get('robust_z','')}</td></tr>" for x in (chronology or {}).get('change_candidates',[]))
 body=f'''<style>body{{font:15px system-ui;max-width:1200px;margin:auto;padding:32px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:7px}}.warn{{background:#fff4d6;padding:12px}}</style><h1>Skin evidence report</h1><p class=warn>Измерительные свидетельства с quality/applicability control. Не автоматический вывод об идентичности, материале, операции или причине изменения.</p><h2>Common observed surface</h2><table><tr><th>A</th><th>B</th><th>Zone</th><th>Status</th><th>Coverage</th></tr>{''.join(rows)}</table><h2>Chronology candidates</h2><table><tr><th>Interval</th><th>Zone</th><th>Family</th><th>Type</th><th>Robust z</th></tr>{changes}</table><h2>Provenance</h2><pre>{html.escape(json.dumps(provenance,ensure_ascii=False,indent=2))}</pre>''';validate_language(body);Path(output).write_text('<!doctype html><meta charset=utf-8>'+body,encoding='utf8')
