import { useEffect, useState } from "react";
import {
  X,
  RotateCcw,
  Calendar,
  Compass,
  ExternalLink,
  Trash2,
} from "lucide-react";
import { useStore, poseLabels } from "../store";
import { api, post } from "../api";
import { Slider, Toggle } from "./ui";
export function PhotoEditor() {
  const id = useStore((s) => s.photoEditor),
    photo = useStore((s) => s.photos.find((p) => p.id === s.photoEditor)),
    set = useStore((s) => s.set),
    notify = useStore((s) => s.notify),
    refresh = useStore((s) => s.refresh);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [date, setDate] = useState(""),
    [angles, setAngles] = useState({ yaw: 0, pitch: 0, roll: 0 }),
    [manual, setManual] = useState(false),
    [crop, setCrop] = useState(false),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (photo) {
      setDeleteConfirm(false);
      setDate(photo.date || "");
      setAngles(photo.angles);
      setManual(!!photo.angle_override);
      setCrop(photo.precropped);
    }
  }, [id]);
  if (!photo) return null;
  const save = async () => {
    setBusy(true);
    try {
      await api("/photos/" + photo.id, {
        method: "PATCH",
        body: JSON.stringify({
          date,
          angle_override: manual ? angles : null,
          precropped: crop,
        }),
      });
      if (crop !== photo.precropped)
        await post("/process", { photo_ids: [photo.id] });
      await refresh();
      notify("Дата и углы сохранены");
      set({ photoEditor: null });
    } catch (e) {
      notify(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-scrim" onClick={() => set({ photoEditor: null })}>
      <section className="photo-editor" onClick={(e) => e.stopPropagation()}>
        <div className="editor-photo">
          <img src={photo.url} />
          <a href={photo.url} target="_blank" rel="noreferrer">
            <ExternalLink size={13} /> Оригинал
          </a>
        </div>
        <div className="editor-fields">
          <div className="flex between">
            <strong>Свойства кадра</strong>
            <button
              className="icon-btn"
              onClick={() => set({ photoEditor: null })}
            >
              <X size={17} />
            </button>
          </div>
          <p className="mini muted filename">{photo.name}</p>
          <label className="field-label">
            <span>
              <Calendar size={12} /> Дата съёмки
            </span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>
          <div className="flex between mini">
            <span>Углы вручную</span>
            <Toggle label="Ручные углы" checked={manual} onChange={setManual} />
          </div>
          {(["yaw", "pitch", "roll"] as const).map((k) => (
            <Slider
              key={k}
              label={k}
              value={angles[k]}
              min={-90}
              max={90}
              step={0.1}
              onChange={(v) => {
                setManual(true);
                setAngles({ ...angles, [k]: v });
              }}
              unit="°"
            />
          ))}
          <button
            className="text-button"
            onClick={() => {
              setManual(false);
              setAngles((photo.meta as any)?.angles || photo.angles);
            }}
          >
            <RotateCcw size={11} /> Вернуть автоматические углы
          </button>
          <p className="micro muted">
            Ракурс: {poseLabels[photo.pose]}. Ручные углы меняют выбор метрик, а
            не реконструированный меш.
          </p>
          <label className="check-row">
            <input
              type="checkbox"
              checked={crop}
              onChange={(e) => setCrop(e.target.checked)}
            />{" "}
            Готовый выровненный кроп 224×224
          </label>
          <p className="micro muted">
            Без детектора. Используйте только уже правильно выровненный портрет,
            особенно для сложного профиля.
          </p>
          <button
            className="danger-text"
            onClick={async () => {
              if (!deleteConfirm) {
                setDeleteConfirm(true);
                return;
              }
              await post("/library/trash", { photo_ids: [photo.id] });
              set({ photoEditor: null });
              await refresh();
              notify("Фото удалено из ATLAS безвозвратно");
            }}
          >
            <Trash2 size={13} />
            {deleteConfirm
              ? "Подтвердить: удалить навсегда"
              : "Удалить фотографию…"}
          </button>
          <button className="primary" disabled={busy} onClick={save}>
            {busy ? "Сохранение…" : "Сохранить"}
          </button>
        </div>
      </section>
    </div>
  );
}
