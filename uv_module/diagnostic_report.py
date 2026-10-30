"""Offline linked source/UV viewer, annotation export and batch diagnostic frames."""
from __future__ import annotations

import base64
import gzip
import html
import json
from pathlib import Path

import cv2
import numpy as np


def json_value(value):
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path: Path, value):
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(json_value(value), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def packed_array(array):
    array = np.asarray(array)
    if array.dtype == bool:
        array = array.astype(np.uint8)
    array = np.ascontiguousarray(array.astype(array.dtype.newbyteorder("<"), copy=False))
    return {"shape": list(array.shape), "dtype": array.dtype.str,
            "gzip_base64": base64.b64encode(gzip.compress(array.tobytes(), compresslevel=6)).decode()}


def image_url(image):
    image = np.clip(image, 0, 255).astype(np.uint8)
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("cannot encode diagnostic image")
    return "data:image/png;base64," + base64.b64encode(buffer).decode()


def color_map(values, mask, logarithmic=False):
    data = np.asarray(values, dtype=float)
    valid = mask & np.isfinite(data)
    if logarithmic:
        data = np.log10(np.maximum(data, 1e-8))
    if valid.any():
        low, high = np.quantile(data[valid], [0.02, 0.98])
        scaled = np.clip((np.nan_to_num(data, nan=low) - low) / max(high - low, 1e-8), 0, 1)
    else:
        scaled = np.zeros(data.shape)
    colored = cv2.applyColorMap((scaled * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    colored[~valid] = [35, 35, 35]
    return colored


def save_diagnostic_png(path: Path, original, raw, beauty, provenance, anisotropy, recon, independent=None):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    figure = Figure(figsize=(14, 9), dpi=110)
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 3)
    source = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
    axes[0, 0].imshow(source)
    projection, triangles = recon["vertices_2d"], recon["triangles"]
    for face in triangles[::max(1, len(triangles) // 500)]:
        polygon = projection[np.r_[face, face[0]]]
        axes[0, 0].plot(polygon[:, 0], polygon[:, 1], color="#ff7c4a", linewidth=0.35, alpha=0.5)
    if independent is not None:
        axes[0, 0].scatter(independent["points"][:, 0], independent["points"][:, 1], s=1, color="#32ff96")
    axes[0, 0].set_title("Original: model mesh / independent landmarks")
    mask = provenance["triangle_id"] >= 0
    panels = [(raw, "Raw observed UV"), (beauty, "Visual UV (may be modified)"),
              (np.repeat((provenance["observed_fraction"] * 255)[..., None], 3, axis=2), "Observed support"),
              (color_map(provenance["source_density"], mask, True), "Source pixels / UV texel (log)"),
              (color_map(anisotropy, mask, True), "UV-to-photo anisotropy (not a defect label)")]
    for axis, (image, title) in zip(list(axes.flat)[1:], panels, strict=True):
        axis.imshow(cv2.cvtColor(np.clip(image, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB))
        axis.set_title(title)
    for axis in axes.flat:
        axis.set_axis_off()
    figure.tight_layout()
    figure.savefig(path)


def save_viewer(path: Path, original, raw, beauty, recon, provenance, metrics, metadata, buffers, independent=None):
    side = raw.shape[0]
    ids = provenance["triangle_id"]
    mask = ids >= 0
    anisotropy = np.full(ids.shape, np.nan, dtype=np.float32)
    anisotropy[mask] = metrics["anisotropy_uv_photo"][ids[mask]]
    ratio = min(1, 1280 / max(original.shape[:2]))
    preview = cv2.resize(original, (int(original.shape[1] * ratio), int(original.shape[0] * ratio))) if ratio < 1 else original
    arrays = {key: packed_array(provenance[key]) for key in (
        "triangle_id", "source_xy", "primary_source_xy", "barycentric", "weight", "raw_method", "beauty_method",
        "observed_fraction", "primary_fraction", "source_detail_px", "source_density", "source_xy_variance",
        "geometry_visible", "in_image", "external_occlusion", "sample_count", "source_bounds")}
    arrays.update({"triangles": packed_array(np.asarray(recon["triangles"], dtype=np.int32)),
                   "projection": packed_array(np.asarray(recon["vertices_2d"], dtype=np.float32)),
                   "uv": packed_array(np.asarray(recon["uv_coords"], dtype=np.float32)),
                   "original_triangle_id": packed_array(buffers["triangle_id"])})
    payload = {"metadata": json_value(metadata), "uv_size": side, "source_size": [original.shape[1], original.shape[0]],
               "preview_size": [preview.shape[1], preview.shape[0]], "depth_scale": buffers["scale"].tolist(),
               "depth_size": [buffers["depth"].shape[1], buffers["depth"].shape[0]], "arrays": arrays,
               "landmarks": independent["points"].tolist() if independent is not None else [],
               "images": {"original": image_url(preview), "raw": image_url(raw), "beauty": image_url(beauty),
                          "visibility": image_url(np.repeat((provenance["observed_fraction"] * 255)[..., None], 3, axis=2)),
                          "density": image_url(color_map(provenance["source_density"], mask, True)),
                          "stretch": image_url(color_map(anisotropy, mask, True))}}
    if "contour_error_px" in provenance:
        payload["images"]["contour_error"] = image_url(color_map(provenance["contour_error_px"], mask, False))
    document = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Linked UV Quality Inspector</title><style>
body{font:14px/1.45 system-ui,sans-serif;margin:16px;color:#152b35;background:#f2f6f8}header{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.views{display:flex;gap:12px;flex-wrap:wrap}.pane{flex:1;min-width:300px;max-width:900px;background:white;padding:10px;overflow:auto}
canvas{width:100%;height:auto;cursor:crosshair;display:block}.zoom{transform-origin:top left}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#e0ebf1;padding:12px}
button,input,select{padding:6px}fieldset{margin-top:12px}.notice{background:#fff1d9;padding:10px;border-left:4px solid #ac6128}
</style><header><h2>Linked Source / UV Inspector</h2><label>UV layer <select id="layer"><option>raw</option><option>beauty</option><option>visibility</option><option>density</option><option>stretch</option></select></label>
<label>Zoom <input id="zoom" type="range" min="1" max="4" step="0.25" value="1"></label><label><input id="mesh" type="checkbox">Mesh</label>
<label><input id="numbers" type="checkbox">Face IDs</label><label><input id="contours" type="checkbox" checked>Independent landmarks</label>
<label><input id="blind" type="checkbox">Blind annotation (hide predictions/layers)</label></header>
<p class="notice">Only UV quality is assessed. Gray/unknown visibility or occlusion does not establish a material-related cause.
Click a UV texel or source triangle to inspect both windows. Raw UV is separate from detail/fill/seam-modified visual UV.</p>
<div class="views"><section class="pane"><h3>Oriented original</h3><div class="zoom"><canvas id="original"></canvas></div></section>
<section class="pane"><h3>UV</h3><div class="zoom"><canvas id="uv"></canvas></div></section></div><pre id="info">Loading compressed numerical provenance...</pre>
<fieldset><legend>Manual annotation (never auto-ground-truth)</legend><label>Observer <input id="observer" placeholder="observer ID"></label>
<label>Round <select id="round"><option>round1</option><option>round2_blind</option></select></label>
<label>Draw <select id="tool"><option>inspect</option><option>source_polygon</option><option>uv_polygon</option></select></label>
<label>Region <select id="region"><option>eyes</option><option>brows</option><option>nasal_bridge</option><option>nose</option><option>lips</option><option>cheeks</option><option>lower_contour</option><option>chin</option></select></label>
<label>Severity <select id="severity"><option>unassessable</option><option>none</option><option>mild</option><option>moderate</option><option>severe</option></select></label>
<label>External occlusion <select id="occlusion"><option value="-1">unknown</option><option value="0">manually clear</option><option value="1">occluded</option></select></label>
<label>Causes <select id="cause" multiple size="3"><option selected>unknown</option><option>stretch</option><option>contour_shift</option><option>background_capture</option><option>tear</option><option>blur</option><option>fill</option></select></label>
<button id="add">Add linked region</button><button id="clear">Clear current polygons</button>
<label>Anatomical source curve <select id="curve"><option>eye_0_upper</option><option>eye_0_lower</option><option>eye_1_upper</option><option>eye_1_lower</option><option>upper_lip</option><option>lower_lip</option><option>lower_face</option></select></label><button id="addcurve">Add manual source contour</button>
<label>Current quality <select id="quality"><option>unassessable</option><option>normal</option><option>distorted</option></select></label><button id="export">Export annotation JSON</button></fieldset>
<script id="payload" type="application/json">__PAYLOAD__</script><script>
const P=JSON.parse(document.getElementById('payload').textContent),A={},I={};let selected=-1,point=null,uvPoint=null,footprint=null;const polygons={source:[],uv:[]},annotations=[];
const manualContours={};const O=document.getElementById('original'),U=document.getElementById('uv');O.width=P.preview_size[0];O.height=P.preview_size[1];U.width=U.height=P.uv_size;
async function unpack(item){const bytes=Uint8Array.from(atob(item.gzip_base64),c=>c.charCodeAt(0));const data=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();const type=item.dtype.slice(-2);return type==='f4'?new Float32Array(data):type==='f8'?new Float64Array(data):type==='i4'?new Int32Array(data):type==='i1'?new Int8Array(data):type==='u2'?new Uint16Array(data):new Uint8Array(data)}
function image(url){return new Promise(resolve=>{const x=new Image();x.onload=()=>resolve(x);x.src=url})}
function getXY(k,index){return [A[k][index*2],A[k][index*2+1]]}
function uvVertex(index){const v=getXY('uv',index);return [v[0]*(P.uv_size-1),(1-v[1])*(P.uv_size-1)]}
function originalVertex(index){const v=getXY('projection',index);return [v[0]*O.width/P.source_size[0],v[1]*O.height/P.source_size[1]]}
function outline(ctx,face,vertex,color){ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();for(let j=0;j<4;j++){const v=vertex(A.triangles[face*3+(j%3)]);j?ctx.lineTo(...v):ctx.moveTo(...v)}ctx.stroke()}
function drawPolygon(ctx,values,scale){if(!values.length)return;ctx.strokeStyle='#e83462';ctx.lineWidth=2;ctx.beginPath();values.forEach((p,i)=>{const x=[p[0]*scale[0],p[1]*scale[1]];i?ctx.lineTo(...x):ctx.moveTo(...x)});ctx.stroke()}
function redraw(){const co=O.getContext('2d'),cu=U.getContext('2d'),blind=document.getElementById('blind').checked;co.clearRect(0,0,O.width,O.height);cu.clearRect(0,0,U.width,U.height);co.drawImage(I.original,0,0,O.width,O.height);cu.drawImage(I[blind?'raw':document.getElementById('layer').value],0,0,U.width,U.height);
if(!blind&&document.getElementById('mesh').checked){const n=A.triangles.length/3;co.lineWidth=cu.lineWidth=.4;for(let f=0;f<n;f+=Math.max(1,Math.floor(n/1600))){outline(co,f,originalVertex,'#dd764c55');outline(cu,f,uvVertex,'#dd764c55')}}
if(!blind&&document.getElementById('contours').checked){co.fillStyle='#17bf74';P.landmarks.forEach(p=>co.fillRect(p[0]*O.width/P.source_size[0],p[1]*O.height/P.source_size[1],2,2))}
if(selected>=0&&!blind){outline(co,selected,originalVertex,'#0098d1');outline(cu,selected,uvVertex,'#0098d1');if(document.getElementById('numbers').checked){co.fillStyle=cu.fillStyle='#0098d1';const ov=originalVertex(A.triangles[selected*3]),uv=uvVertex(A.triangles[selected*3]);co.fillText(selected,...ov);cu.fillText(selected,...uv)}}
if(point&&point.every(Number.isFinite)&&!blind){co.fillStyle='#e93646';co.beginPath();co.arc(point[0]*O.width/P.source_size[0],point[1]*O.height/P.source_size[1],4,0,2*Math.PI);co.fill()}if(uvPoint&&!blind){cu.fillStyle='#e93646';cu.fillRect(uvPoint[0]-3,uvPoint[1]-3,6,6)}
if(footprint&&footprint.every(Number.isFinite)&&!blind){co.strokeStyle='#ffe100';co.lineWidth=2;co.strokeRect(footprint[0]*O.width/P.source_size[0],footprint[1]*O.height/P.source_size[1],(footprint[2]-footprint[0])*O.width/P.source_size[0],(footprint[3]-footprint[1])*O.height/P.source_size[1])}
drawPolygon(co,polygons.source,[O.width/P.source_size[0],O.height/P.source_size[1]]);drawPolygon(cu,polygons.uv,[1,1])}
function eventPoint(e,c){const r=c.getBoundingClientRect();return [(e.clientX-r.left)*c.width/r.width,(e.clientY-r.top)*c.height/r.height]}
function inspectUV(x,y){x=Math.max(0,Math.min(U.width-1,Math.floor(x)));y=Math.max(0,Math.min(U.height-1,Math.floor(y)));const index=y*U.width+x;selected=A.triangle_id[index];uvPoint=[x,y];point=getXY('source_xy',index);footprint=Array.from(A.source_bounds.slice(index*4,index*4+4));const methods=['unavailable','direct','interpolated_observed','mirror_fill','inpaint','synthetic_or_seam_modified'];document.getElementById('info').textContent=JSON.stringify({triangle:selected,uv_texel:[x,y],source_pixel:point,primary_source:getXY('primary_source_xy',index),barycentric:Array.from(A.barycentric.slice(index*3,index*3+3)),weight:A.weight[index],raw_origin:methods[A.raw_method[index]],visual_origin:methods[A.beauty_method[index]],observed_fraction:A.observed_fraction[index],primary_fraction:A.primary_fraction[index],sample_count:A.sample_count[index],source_detail_px:A.source_detail_px[index],source_density:A.source_density[index],source_sample_variance:getXY('source_xy_variance',index),source_kernel_bounds:footprint,mesh_visibility:A.geometry_visible[index],in_source_image:A.in_image[index],external_occlusion:A.external_occlusion[index],note:'Unknown occlusion=-1; yellow box is the conservative sampling footprint.'},null,2);redraw()}
U.onclick=e=>{const p=eventPoint(e,U);if(document.getElementById('tool').value==='uv_polygon'){polygons.uv.push(p);redraw()}else if(!document.getElementById('blind').checked)inspectUV(...p)};
O.onclick=e=>{const p=eventPoint(e,O),source=[p[0]*P.source_size[0]/O.width,p[1]*P.source_size[1]/O.height];if(document.getElementById('tool').value==='source_polygon'){polygons.source.push(source);redraw();return}if(document.getElementById('blind').checked)return;const x=Math.round(source[0]*P.depth_scale[0]),y=Math.round(source[1]*P.depth_scale[1]);if(x<0||y<0||x>=P.depth_size[0]||y>=P.depth_size[1])return;selected=A.original_triangle_id[y*P.depth_size[0]+x];point=source;uvPoint=null;footprint=null;document.getElementById('info').textContent=JSON.stringify({source_pixel:source,triangle:selected,metadata:P.metadata},null,2);redraw()};
for(const id of ['layer','mesh','numbers','contours','blind'])document.getElementById(id).onchange=()=>{if(document.getElementById('blind').checked)document.getElementById('info').textContent='Blind mode: previous annotations and diagnostic scores are hidden.';redraw()};
document.getElementById('zoom').oninput=e=>document.querySelectorAll('.zoom').forEach(x=>x.style.transform=`scale(${e.target.value})`);
document.getElementById('round').onchange=e=>{if(e.target.value==='round2_blind'){document.getElementById('blind').checked=true;document.getElementById('info').textContent='Round2: no round1 labels or diagnostic layers shown.';redraw()}};
document.getElementById('clear').onclick=()=>{polygons.source=[];polygons.uv=[];redraw()};
document.getElementById('add').onclick=()=>{if(polygons.source.length<3||polygons.uv.length<3){alert('Draw both source and UV polygons; otherwise use unassessable.');return}annotations.push({region:document.getElementById('region').value,severity:document.getElementById('severity').value,causes:Array.from(document.getElementById('cause').selectedOptions,o=>o.value),external_occlusion:Number(document.getElementById('occlusion').value),source_polygon:polygons.source.slice(),uv_polygon:polygons.uv.slice()});polygons.source=[];polygons.uv=[];redraw()};
document.getElementById('addcurve').onclick=()=>{if(polygons.source.length<3){alert('Trace at least3 original anatomical contour points.');return}manualContours[document.getElementById('curve').value]=polygons.source.slice();polygons.source=[];redraw()};
document.getElementById('export').onclick=()=>{const observer=document.getElementById('observer').value;if(!observer){alert('Observer ID required');return}const quality=document.getElementById('quality').value,result={schema_version:'uv-quality-manual-v1',sample_id:P.metadata.sample_id,source_sha256:P.metadata.source_sha256,generation_id:P.metadata.generation_id,observer_id:observer,round:document.getElementById('round').value,blind_to_prior:document.getElementById('blind').checked,manual:true,timestamp:new Date().toISOString(),quality_label_current:quality==='unassessable'?null:quality,regions:annotations,manual_contours:manualContours,material_presence:null};const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`${result.sample_id}_${result.round}.json`;link.click();URL.revokeObjectURL(url)};
Promise.all(Object.entries(P.arrays).map(async([key,value])=>A[key]=await unpack(value))).then(()=>Promise.all(Object.entries(P.images).map(async([key,value])=>I[key]=await image(value)))).then(()=>{document.getElementById('info').textContent='Ready. Click a UV texel or original triangle.';redraw()}).catch(e=>document.getElementById('info').textContent='Viewer load failed: '+e.message);
</script></html>"""
    escaped = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    if "contour_error" in payload["images"]:
        document = document.replace("<option>stretch</option>", "<option>stretch</option><option>contour_error</option>", 1)
    document = document.replace("__PAYLOAD__", escaped)
    path.write_text(document, encoding="utf-8")


def save_batch_index(path: Path, results: list[dict], dataset_summary: dict):
    rows = []
    for row in results:
        relative = row.get("viewer_relative")
        view = f"<a href='{html.escape(relative)}'>linked viewer</a>" if relative else "unavailable"
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(key, '')))}</td>" for key in ("sample_id", "partition", "status", "reason"))
                    + f"<td>{view}</td></tr>")
    text = "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
    text += "<title>UV Quality Diagnostics</title><style>body{font:15px system-ui;margin:24px;max-width:1500px}td,th{border:1px solid #ccd8df;padding:8px}table{border-collapse:collapse}pre{white-space:pre-wrap}</style>"
    text += "<h1>UV Quality Diagnostics</h1><p>Quality/correspondence only. No face-material or identity inference. Closed test is not used for tuning.</p><pre>"
    text += html.escape(json.dumps(json_value(dataset_summary), indent=2)) + "</pre><table><tr><th>Sample</th><th>Partition</th><th>Status</th><th>Reason</th><th>Diagnostics</th></tr>"
    text += "".join(rows) + "</table></html>"
    path.write_text(text, encoding="utf-8")
