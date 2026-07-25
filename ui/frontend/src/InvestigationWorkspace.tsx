import { useEffect, useMemo, useState } from "react";
import { loadPhotos } from "./api";
import type { PhotoIndexResponse, PhotoRecord, ProjectHealth } from "./types";
import { uiLog } from "./logStore";

const POSES: [string, string, string][] = [
  ["left_profile", "LP", "Левый профиль"], ["left_deep", "LD", "Левый глубокий"], ["left_mid", "LM", "Левый средний"],
  ["left_light", "LL", "Левый лёгкий"], ["frontal", "F", "Фронтальный"], ["right_light", "RL", "Правый лёгкий"],
  ["right_mid", "RM", "Правый средний"], ["right_deep", "RD", "Правый глубокий"], ["right_profile", "RP", "Правый профиль"],
];
const YEAR_MIN = 1999, YEAR_MAX = 2026;

function bytes(value: number) {
  if (value < 1024) return `${value} Б`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} КБ`;
  return `${(value / 1024 / 1024).toFixed(1)} МБ`;
}

export function InvestigationWorkspace({ health }: { health: ProjectHealth | null }) {
  const [data, setData] = useState<PhotoIndexResponse | null>(null);
  const [selected, setSelected] = useState<PhotoRecord | null>(null);
  const [error, setError] = useState("");
  const [poseFilter, setPoseFilter] = useState("all");
  const [showUndated, setShowUndated] = useState(false);

  useEffect(() => {
    let stopped = false;
    uiLog("info", "photos", "Загрузка read-only индекса фотографий");
    loadPhotos().then((result) => {
      if (stopped) return;
      setData(result);
      uiLog("info", "photos", `Индекс загружен: ${result.summary.all_photos} фото; датировано ${result.summary.dated}; без даты ${result.summary.undated}`);
      if (result.summary.undated > 0) uiLog("warning", "photos", `${result.summary.undated} фото не соответствуют формату даты YYYY_MM_DD`);
    }).catch((reason) => { if (!stopped) { setError(String(reason)); uiLog("error", "photos", `Индекс недоступен: ${String(reason)}`); } });
    return () => { stopped = true; };
  }, []);

  const items = useMemo(() => (data?.items ?? []).filter((x) => (poseFilter === "all" || x.pose_bin_hint === poseFilter) && (showUndated || x.date !== null)), [data, poseFilter, showUndated]);
  const byPose = useMemo(() => {
    const map = new Map<string, PhotoRecord[]>();
    for (const pose of [...POSES.map((x) => x[0]), "unknown"]) map.set(pose, []);
    for (const item of items) (map.get(item.pose_bin_hint) ?? map.get("unknown")!).push(item);
    return map;
  }, [items]);

  function selectPhoto(item: PhotoRecord) {
    setSelected(item); uiLog("info", "photos", `Выбрано фото ${item.id}: ${item.date ?? "без даты"}, pose hint ${item.pose_bin_hint}`);
  }

  return <div className="investigation-workbench">
    <header className="view-header"><div><p className="eyebrow">FORENSIC FACE / SKIN CONSISTENCY · READ ONLY INDEX</p><h1>Хронология расследования</h1><p>Реальные файлы архива; pose пока показан только как организационная подсказка до свежего Stage 1.</p></div><div className="view-actions"><span className="mode-chip">1999–2026</span><span className="mode-chip">{data?.summary.all_photos ?? health?.datasets.main?.file_count ?? 0} фотографий</span></div></header>
    <div className="investigation-layout"><section className="chronology-panel">
      <div className="analysis-toolbar"><div className="segmented"><button className="active">Хронология</button><button disabled>Матрица</button><button disabled>Кластеры</button></div><div className="analysis-filters"><select value={poseFilter} onChange={(e) => setPoseFilter(e.target.value)} aria-label="Фильтр ракурса"><option value="all">Все 9 ракурсов</option>{POSES.map(([id,,name]) => <option value={id} key={id}>{name}</option>)}<option value="unknown">Pose неизвестен</option></select><label><input type="checkbox" checked={showUndated} onChange={(e) => setShowUndated(e.target.checked)} /> без даты</label></div></div>
      <div className="metric-legend"><span className="geometry">Файл найден</span><span className="quality">Дата распознана</span><span className="anomaly">Требует Stage 1</span>{data && <b>{data.summary.dated} датировано · {data.summary.undated} без даты</b>}</div>
      {error && <div className="photo-index-error">Не удалось загрузить индекс: {error}</div>}
      {!data && !error && <div className="photo-index-loading">Сканируем имена, даты и структуру ракурсов…</div>}
      {data && <div className="photo-timeline-real"><div className="year-axis"><span>1999</span><span>2005</span><span>2010</span><span>2015</span><span>2020</span><span>2026</span></div><div className="pose-lanes">
        {POSES.map(([id,code,name]) => <div className="pose-lane real" key={id}><b>{code}</b><span>{name}<small>{data.summary.pose_counts[id] ?? 0}</small></span><div className="marker-track">{(byPose.get(id) ?? []).map((item, index) => { const left = item.year == null ? 0 : Math.max(0, Math.min(100, (item.year - YEAR_MIN) / (YEAR_MAX - YEAR_MIN) * 100)); return <button key={item.id} className={`photo-marker ${selected?.id === item.id ? "selected" : ""} ${item.issues.length ? "warning" : ""}`} style={{ left: `calc(${left}% - 3px)`, top: `${8 + index % 3 * 7}px` }} onClick={() => selectPhoto(item)} title={`${item.date ?? "без даты"} · ${item.relative_path}`} aria-label={`Фото ${item.date ?? "без даты"}, ${name}`} />; })}</div></div>)}
        {(showUndated || poseFilter === "unknown") && <div className="pose-lane real unknown"><b>?</b><span>Не классифицировано<small>{data.summary.pose_counts.unknown ?? 0}</small></span><div className="marker-track">{(byPose.get("unknown") ?? []).slice(0,200).map((item,index) => <button key={item.id} className={`photo-marker warning ${selected?.id === item.id ? "selected" : ""}`} style={{ left: `${index % 100}%`, top: `${8 + index % 3 * 7}px` }} onClick={() => selectPhoto(item)} title={item.relative_path} aria-label={`Фото без измеренного pose: ${item.filename}`} />)}</div></div>}
      </div>{data.summary.all_photos > data.items.length && <div className="timeline-limit">Показаны первые {data.items.length} из {data.summary.all_photos}. Следующая итерация добавит виртуальную подгрузку.</div>}</div>}
    </section><aside className="analysis-inspector"><div className="inspector-tabs"><button className="active">Фото</button><button disabled>Пара A/B</button><button disabled>3D</button></div>{selected ? <div className="photo-detail"><p className="eyebrow">READ-ONLY PHOTO RECORD</p><h2>{selected.date ?? "Дата не распознана"}</h2><code>{selected.relative_path}</code><dl><div><dt>Pose hint</dt><dd>{selected.pose_bin_hint}</dd></div><div><dt>Источник pose</dt><dd>{selected.pose_hint_source}</dd></div><div><dt>Размер</dt><dd>{bytes(selected.size_bytes)}</dd></div><div><dt>Stage 1</dt><dd>{selected.processing_status}</dd></div></dl>{selected.issues.length > 0 && <div className="photo-issues"><b>Требует внимания</b>{selected.issues.map((x) => <span key={x}>{x}</span>)}</div>}<p className="pose-warning">Pose из папки или имени — только подсказка организации архива. Научный pose должен быть заново измерен Stage 1.</p></div> : <div className="inspector-empty"><span>＋</span><b>Выберите точку на хронологии</b><p>Появятся путь, дата, организационный pose hint и проблемы индекса.</p></div>}<div className="evidence-boundary"><b>Граница доказательств</b><p>Файловый индекс ничего не утверждает о личности, коже или подлинности. Он только организует исходные данные.</p></div></aside></div>
  </div>;
}
