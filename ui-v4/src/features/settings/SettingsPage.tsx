import { useEffect, useState } from "react";
import {
  detail, fetchSettings, image, info, photoArtifactJson, photoArtifactUrl, photoMesh,
  resetSettings, saveSettings, skin, timeline, uploadPhoto,
  type AppSettings, type UploadResult,
} from "../../shared/api";

type CheckStatus = "pass" | "fail" | "pending" | "unavailable";
interface PhotoCheck { key: string; label: string; status: CheckStatus; actual: string; requirement: string }
interface UploadedPhoto { localId: string; fileName: string; state: "uploading" | "checking" | "complete" | "error"; result?: UploadResult; checks: PhotoCheck[]; error?: string }
const number = (value: string) => Number.isFinite(Number(value)) ? Number(value) : 0;
const display = (value: unknown, digits = 3) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : value == null ? "нет данных" : String(value);

function deepFind(value: unknown, names: string[]): unknown {
  const wanted = new Set(names.map(name => name.toLowerCase()));
  const stack: unknown[] = [value];
  const seen = new Set<object>();
  while (stack.length) {
    const current = stack.pop();
    if (!current || typeof current !== "object" || seen.has(current)) continue;
    seen.add(current);
    for (const [key, child] of Object.entries(current as Record<string, unknown>)) {
      if (wanted.has(key.toLowerCase())) return child;
      if (child && typeof child === "object") stack.push(child);
    }
  }
  return undefined;
}
async function exists(url: string): Promise<boolean> {
  try { const response = await fetch(url, { cache: "no-store" }); return response.ok; }
  catch { return false; }
}
async function settled<T>(promise: Promise<T>): Promise<T | null> {
  try { return await promise; } catch { return null; }
}
function gate(label: string, actual: number | null, threshold: number, direction: "min" | "max", key: string): PhotoCheck {
  if (actual === null) return { key, label, status: "pending", actual: "нет данных", requirement: `${direction === "min" ? "≥" : "≤"} ${threshold}` };
  const pass = direction === "min" ? actual >= threshold : actual <= threshold;
  return { key, label, status: pass ? "pass" : "fail", actual: display(actual), requirement: `${direction === "min" ? "≥" : "≤"} ${threshold}` };
}

async function evaluatePhoto(photoId: string, settings: AppSettings, stored: boolean): Promise<PhotoCheck[]> {
  const [timelineData, photoData, infoData, skinData, meshData, textureData, rawInfo, maskOk, uvOk] = await Promise.all([
    timeline(), settled(detail(photoId)), settled(info(photoId)), settled(skin(photoId)), settled(photoMesh(photoId, 2)),
    settled(photoArtifactJson(photoId, "texture.json")), settled(photoArtifactJson(photoId, "info.json")),
    exists(photoArtifactUrl(photoId, "face_mask.png")), exists(image(photoId, "uv_texture")),
  ]);
  const photo = timelineData.photos.find(item => item.id === photoId) || null;
  const source = rawInfo || infoData || photoData || {};
  const smileDetected = deepFind(source, ["smile_detected"]);
  const smileValue = deepFind(source, ["smile_score", "expression_smile", "corner_lift_ioc"]);
  const jawDetected = deepFind(source, ["jaw_open_detected"]);
  const jawValue = deepFind(source, ["jaw_open_ratio", "expression_jaw_open"]);
  const landmarks106 = deepFind(photoData, ["landmarks_106", "ldm106"]);
  const landmarks134 = deepFind(photoData, ["landmarks_134", "ldm134"]);
  const activeZones = deepFind(skinData, ["active_zone_count"]);
  const expressionCheck = (label: string, detected: unknown, value: unknown, threshold: number, key: string): PhotoCheck => {
    if (detected === true) return { key, label, status: "fail", actual: "обнаружено", requirement: "не обнаружено" };
    if (detected === false) return { key, label, status: "pass", actual: "не обнаружено", requirement: "не обнаружено" };
    return gate(label, typeof value === "number" && Number.isFinite(value) ? value : null, threshold, "max", key);
  };
  const artifact = (key: string, label: string, ok: boolean, requirement: string): PhotoCheck => ({ key, label, status: ok ? "pass" : photo ? "unavailable" : "pending", actual: ok ? "доступен" : "не найден", requirement });
  return [
    { key: "stored", label: "Файл принят backend", status: stored ? "pass" : "unavailable", actual: stored ? "сохранён" : "дубликат или не сохранён", requirement: "сохранён" },
    { key: "record", label: "Stage 1 запись создана", status: photo ? "pass" : "pending", actual: photo ? photo.id : "ожидает extraction", requirement: "запись в timeline" },
    { key: "pose", label: "Ракурс классифицирован", status: photo?.bucket ? "pass" : "pending", actual: photo?.bucket || "нет данных", requirement: "1 из 9 pose bins" },
    gate("Минимальное качество", photo && Number.isFinite(photo.quality) ? photo.quality : null, settings.thresholds.quality_min, "min", "quality"),
    gate("Минимальная confidence", photo && Number.isFinite(photo.confidence) ? photo.confidence : null, settings.thresholds.confidence_min, "min", "confidence"),
    expressionCheck("Улыбка", smileDetected, smileValue, settings.thresholds.expression_smile, "smile"),
    expressionCheck("Открытая челюсть", jawDetected, jawValue, settings.thresholds.expression_jaw_open, "jaw"),
    { key: "ldm106", label: "Landmarks 106", status: Array.isArray(landmarks106) && landmarks106.length >= 106 ? "pass" : photoData ? "fail" : "pending", actual: Array.isArray(landmarks106) ? `${landmarks106.length} точек` : "нет данных", requirement: "≥ 106 точек" },
    { key: "ldm134", label: "Landmarks 134", status: Array.isArray(landmarks134) && landmarks134.length >= 134 ? "pass" : photoData ? "fail" : "pending", actual: Array.isArray(landmarks134) ? `${landmarks134.length} точек` : "нет данных", requirement: "≥ 134 точек" },
    artifact("mask", "face_mask.png", maskOk, "обязательный mask artifact"),
    artifact("uv", "UV texture", uvOk, "доступная UV texture"),
    artifact("texture", "texture.json", Boolean(textureData), "валидный texture JSON"),
    artifact("mesh", "3D BFM mesh", Boolean(meshData?.vertices?.length), "vertices + triangles"),
    { key: "skin", label: "Активные skin zones", status: typeof activeZones === "number" ? activeZones > 0 ? "pass" : "fail" : skinData ? "unavailable" : "pending", actual: display(activeZones, 0), requirement: "> 0 зон" },
  ];
}

function CheckTable({ photo, refresh }: { photo: UploadedPhoto; refresh: () => void }) {
  const counts = photo.checks.reduce((acc, check) => ({ ...acc, [check.status]: (acc[check.status] || 0) + 1 }), {} as Record<CheckStatus, number>);
  return <article className="photo-validation-card">
    <header><div><b>{photo.fileName}</b><span>{photo.result?.photo_id || photo.state}</span></div><div className="check-summary"><em className="pass">✓ {counts.pass || 0}</em><em className="fail">× {counts.fail || 0}</em><em className="pending">… {counts.pending || 0}</em><button disabled={!photo.result || photo.state === "checking"} onClick={refresh}>↻ Проверить</button></div></header>
    {photo.error && <div className="error">{photo.error}</div>}
    {(photo.state === "uploading" || photo.state === "checking") && <div className="validation-progress"><i/><span>{photo.state === "uploading" ? "Загрузка файла…" : "Проверка Stage 1 артефактов…"}</span></div>}
    {photo.checks.length > 0 && <div className="check-table"><div className="check-table-head"><span>Проверка</span><span>Статус</span><span>Фактически</span><span>Требование</span></div>{photo.checks.map(check => <div key={check.key} className={`check-row ${check.status}`}><span>{check.label}</span><b>{check.status === "pass" ? "✓ Проходит" : check.status === "fail" ? "× Не проходит" : check.status === "pending" ? "… Ожидает" : "— Нет данных"}</b><span>{check.actual}</span><span>{check.requirement}</span></div>)}</div>}
  </article>;
}

export default function SettingsPage({ openPhoto }: { openPhoto: (id: string) => void }) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploads, setUploads] = useState<UploadedPhoto[]>([]);
  const load = async () => { try { setSettings(await fetchSettings()); } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); } };
  useEffect(() => { void load(); }, []);
  const threshold = (key: keyof AppSettings["thresholds"], value: number) => setSettings(current => current ? { ...current, thresholds: { ...current.thresholds, [key]: value } } : current);
  const heat = (key: keyof AppSettings["heatmap"], value: number) => setSettings(current => current ? { ...current, heatmap: { ...current.heatmap, [key]: value } } : current);
  const shift = (key: "tolerance" | "suspect", value: number) => setSettings(current => current ? { ...current, landmark_shift: { tolerance: current.landmark_shift?.tolerance ?? .02, suspect: current.landmark_shift?.suspect ?? .05, calibrated: current.landmark_shift?.calibrated ?? false, [key]: value } } : current);
  const shiftValid = !settings?.landmark_shift || settings.landmark_shift.suspect > settings.landmark_shift.tolerance;
  const save = async () => { if (!settings || !shiftValid) return; setBusy(true); try { setSettings(await saveSettings(settings)); setMessage("Настройки сохранены в app6"); } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); } finally { setBusy(false); } };
  const updateUpload = (localId: string, patch: Partial<UploadedPhoto>) => setUploads(current => current.map(item => item.localId === localId ? { ...item, ...patch } : item));
  const evaluate = async (localId: string, result: UploadResult) => {
    if (!settings) return;
    updateUpload(localId, { state: "checking", error: undefined });
    try { updateUpload(localId, { state: "complete", checks: await evaluatePhoto(result.photo_id, settings, result.stored) }); }
    catch (error) { updateUpload(localId, { state: "error", error: error instanceof Error ? error.message : String(error) }); }
  };
  const uploadFiles = async (files: FileList | null) => {
    if (!files || !settings) return;
    for (const file of Array.from(files)) {
      const localId = `${Date.now()}-${crypto.randomUUID()}`;
      setUploads(current => [...current, { localId, fileName: file.name, state: "uploading", checks: [] }]);
      try { const result = await uploadPhoto(file); updateUpload(localId, { result }); await evaluate(localId, result); }
      catch (error) { updateUpload(localId, { state: "error", error: error instanceof Error ? error.message : String(error) }); }
    }
  };
  if (!settings) return <div className="state loading"><span>◌</span><b>Чтение настроек app6</b><p>{message}</p></div>;
  const rows: [keyof AppSettings["thresholds"], string, number, number, number][] = [
    ["quality_min", "Минимальное качество", 0, 1, .01], ["confidence_min", "Минимальная confidence", 0, 1, .01],
    ["expression_smile", "Порог улыбки", 0, 2, .01], ["expression_jaw_open", "Порог открытой челюсти", 0, 1, .01],
    ["geometry_zone_delta_limit", "Лимит геометрии зоны", 0, .2, .001], ["texture_zone_delta_limit", "Лимит текстуры зоны", 0, .3, .001],
  ];
  return <div className="page-shell settings-page"><div className="page-heading"><div><small>CALIBRATED CONTROLS</small><h1>Настройки анализа</h1><p>Пороговые значения сохраняются backend и используются при проверке каждого загруженного фото.</p></div><div><button className="ghost" onClick={() => void resetSettings().then(setSettings)}>Сбросить</button><button className="primary" disabled={busy || !shiftValid} onClick={() => void save()}>Сохранить</button></div></div>{message && <div className="notice wide">{message}</div>}
    <div className="settings-grid"><section className="card"><header><span>01</span><div><b>Quality & expression gates</b><small>Проверки реальных Stage outputs</small></div></header><div className="slider-list">{rows.map(([key, label, min, max, step]) => <label key={key}><div><span>{label}</span><input type="number" min={min} max={max} step={step} value={settings.thresholds[key]} onChange={event => threshold(key, number(event.target.value))}/></div><input type="range" min={min} max={max} step={step} value={settings.thresholds[key]} onChange={event => threshold(key, number(event.target.value))}/></label>)}</div></section>
      <section className="card"><header><span>02</span><div><b>Heatmap & landmark shift</b><small>Визуальные пороги остатка</small></div></header><div className="slider-list"><label><div><span>LDM допустимое смещение (green)</span><input type="number" min="0" max="1" step=".001" value={settings.landmark_shift?.tolerance ?? .02} onChange={event => shift("tolerance", number(event.target.value))}/></div><input type="range" min="0" max=".2" step=".001" value={settings.landmark_shift?.tolerance ?? .02} onChange={event => shift("tolerance", number(event.target.value))}/></label><label><div><span>LDM подозрительное смещение (orange/red)</span><input type="number" min="0" max="1" step=".001" value={settings.landmark_shift?.suspect ?? .05} onChange={event => shift("suspect", number(event.target.value))}/></div><input type="range" min="0" max=".4" step=".001" value={settings.landmark_shift?.suspect ?? .05} onChange={event => shift("suspect", number(event.target.value))}/></label>{!shiftValid && <div className="error wide">Порог suspect должен быть строго больше tolerance.</div>}<div className={`calibration-state ${settings.landmark_shift?.calibrated ? "calibrated" : "diagnostic"}`}>{settings.landmark_shift?.calibrated ? "✓ Пороги откалиброваны" : "Диагностические пороги — требуется calibration bundle"}</div>{(["stop_blue_cyan", "stop_cyan_green", "stop_green_red", "stop_saturated_red", "max_residual_reference"] as (keyof AppSettings["heatmap"])[]).map(key => <label key={key}><div><span>{key.replaceAll("_", " ")}</span><input type="number" step=".01" value={settings.heatmap[key]} onChange={event => heat(key, number(event.target.value))}/></div><input type="range" min="0" max="1" step=".01" value={settings.heatmap[key]} onChange={event => heat(key, number(event.target.value))}/></label>)}</div></section>
      <section className="card upload-card"><header><span>03</span><div><b>Проверка тестовых фотографий</b><small>Каждый файл получает отдельный checklist по реальным данным app6</small></div></header><label className="drop-zone"><input type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={event => void uploadFiles(event.target.files)}/><b>Выбрать или перетащить фотографии</b><small>Можно выбрать несколько JPG, PNG или WEBP</small></label><div className="uploaded-validation-list">{uploads.map(photo => <div key={photo.localId}><CheckTable photo={photo} refresh={() => photo.result && void evaluate(photo.localId, photo.result)}/>{photo.result && <button className="open-result" onClick={() => openPhoto(photo.result!.photo_id)}>Открыть Photo Lab →</button>}</div>)}</div></section>
    </div>
  </div>;
}
