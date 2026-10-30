import { memo, useState, useRef, useEffect } from "react";
import { useReactFlow, type NodeProps } from "@xyflow/react";
import {
  Images,
  Upload,
  FolderOpen,
  RefreshCw,
  Box,
  SlidersHorizontal,
  Activity,
  ArrowUpRight,
  Cpu,
  Check,
  AlertCircle,
  Lock,
  FileArchive,
  Trash2,
  RotateCcw,
} from "lucide-react";
import { useStore, type WorkNode, poseLabels } from "../store";
import { api, post } from "../api";
import { NodeHead, Port, Toggle, Slider, JobProgress, StatusDot } from "./ui";
export const SourceNode = memo(function SourceNode({
  id,
  data,
}: NodeProps<WorkNode>) {
  const photos = useStore((s) => s.photos),
    groups = useStore((s) => s.groups),
    group = useStore((s) => s.group),
    jobs = useStore((s) => s.jobs),
    seconds = useStore((s) => s.secondsPerPhoto),
    setGroup = useStore((s) => s.setGroup),
    refresh = useStore((s) => s.refresh),
    notify = useStore((s) => s.notify),
    select = useStore((s) => s.selectPhoto);
  const [trashOpen, setTrashOpen] = useState(false),
    [trashItems, setTrashItems] = useState<any[]>([]),
    [confirmDelete, setConfirmDelete] = useState<string[] | null>(null);
  const [inputGroup, setInputGroup] = useState("Моя группа");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null),
    folderRef = useRef<HTMLInputElement>(null);
  const ps = photos.filter((p) => group === "__all" || p.group === group),
    done = ps.filter((p) => p.status === "ready").length,
    unknown = ps.filter((p) => !p.date);
  const job = jobs.find(
    (j) =>
      j.kind === "process" &&
      ["running", "queued", "failed"].includes(j.status),
  );
  const upload = async (files: FileList | File[]) => {
    if (!files.length) return;
    setBusy(true);
    try {
      const f = new FormData();
      Array.from(files).forEach((file) =>
        f.append("files", file, (file as any).webkitRelativePath || file.name),
      );
      f.append("group", inputGroup);
      const result = await api("/upload", { method: "POST", body: f });
      await refresh();
      const s = useStore.getState(),
        target = s.groups.includes(inputGroup)
          ? inputGroup
          : s.groups.find((g) => !g.includes("Демо")) || s.group;
      s.setGroup(target);
      notify(
        result.added
          ? result.job
            ? `Загружено ${result.added} фото. Обработка запущена; прогресс отображается на холсте.`
            : `Загружено ${result.added} фото, но обработка НЕ запущена: ${result.reason || "модель недоступна"}. Исходники сохранены.`
          : "Новых фото нет: файлы уже в библиотеке.",
      );
    } catch (e) {
      notify(String(e));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
      if (folderRef.current) folderRef.current.value = "";
    }
  };
  return (
    <div className="node-card source-node">
      <NodeHead
        id={id}
        title="Фото и серии"
        icon={<Images size={16} />}
        subtitle="Источник · локальное хранилище"
        collapsed={data.collapsed}
        badge={<span className="node-number">01</span>}
      />
      {!data.collapsed && (
        <div className="node-content nodrag nowheel">
          <div className="library-actions">
            {photos.some((p) => p.demo) && (
              <button
                className="danger-text"
                onClick={() =>
                  setConfirmDelete(
                    photos.filter((p) => p.demo).map((p) => p.id),
                  )
                }
              >
                <Trash2 size={12} />
                Убрать все демо
              </button>
            )}
            {photos.some((p) => p.demo) && (
              <button
                className="danger-text"
                title="Безвозвратно удалить только сгенерированные демо и их кэш"
                onClick={async () => {
                  if (
                    !window.confirm(
                      "Безвозвратно удалить все искусственные ATLAS-демо и их кэш? Исходные пользовательские фотографии не затрагиваются.",
                    )
                  )
                    return;
                  await post("/library/delete-demo", {});
                  await refresh();
                  setGroup(
                    useStore
                      .getState()
                      .groups.find((g) => !g.includes("Демо")) || "",
                  );
                  notify(
                    "Демо удалены безвозвратно. Пользовательские фото сохранены.",
                  );
                }}
              >
                <Trash2 size={12} />
                Удалить навсегда
              </button>
            )}
            <button
              title="Корзина — восстановить удалённые фото"
              onClick={async () => {
                const r = await api("/library/trash");
                setTrashItems(r.photos);
                setTrashOpen(!trashOpen);
              }}
            >
              <RotateCcw size={12} />
              Корзина
            </button>
            {ps.length > 0 && (
              <button
                title="Удалить текущую группу"
                onClick={() => setConfirmDelete(ps.map((p) => p.id))}
              >
                <Trash2 size={12} />
              </button>
            )}
          </div>
          {confirmDelete && (
            <div className="inline-confirm">
              <b>Убрать {confirmDelete.length} фото в корзину?</b>
              <p>Исходники и кэш останутся. Можно восстановить.</p>
              <button
                className="danger-button"
                onClick={async () => {
                  await post("/library/trash", { photo_ids: confirmDelete });
                  setConfirmDelete(null);
                  await refresh();
                  notify("Фотографии перемещены в корзину");
                }}
              >
                Убрать
              </button>
              <button onClick={() => setConfirmDelete(null)}>Отмена</button>
            </div>
          )}
          {trashOpen && (
            <div className="trash-list">
              <strong>Корзина · {trashItems.length}</strong>
              {trashItems.length > 0 ? (
                <button
                  onClick={async () => {
                    await post("/library/restore", {
                      photo_ids: trashItems.map((p) => p.id),
                    });
                    setTrashOpen(false);
                    await refresh();
                  }}
                >
                  Восстановить все
                </button>
              ) : (
                <small>Пусто</small>
              )}
              {trashItems.slice(0, 40).map((p) => (
                <div key={p.id}>
                  <span>{p.name}</span>
                  <button
                    title="Восстановить"
                    onClick={async () => {
                      await post("/library/restore", { photo_ids: [p.id] });
                      setTrashItems((xs) => xs.filter((x) => x.id !== p.id));
                      await refresh();
                    }}
                  >
                    <RotateCcw size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <label className="field-label">
            Набор фотографий
            <select
              aria-label="Выбрать группу"
              value={group}
              onChange={(e) => setGroup(e.target.value)}
            >
              {groups.map((g) => (
                <option key={g} value={g}>
                  {g.startsWith("Демо") ? "Демо · один портрет" : g} ·{" "}
                  {photos.filter((p) => p.group === g).length}
                </option>
              ))}
              <option value="__all">Все группы · {photos.length}</option>
            </select>
          </label>
          <div className="source-thumbs">
            {ps.slice(0, 5).map((p) => (
              <button
                key={p.id}
                title={p.date || p.name}
                onClick={() => select(p.id)}
                onDoubleClick={() => useStore.setState({ photoEditor: p.id })}
              >
                <img src={p.thumbnail} />
              </button>
            ))}
            {ps.length > 5 && <span>+{ps.length - 5}</span>}
          </div>
          <div className="flex between mini">
            <span>
              <StatusDot /> {done} / {ps.length} обработано
            </span>
            <span className="muted">{seconds ?? "—"} с/фото</span>
          </div>
          <div
            className={"upload-drop " + (drag ? "drag" : "")}
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setDrag(false);
              upload(e.dataTransfer.files);
            }}
            onClick={() => !busy && fileRef.current?.click()}
          >
            <Upload size={15} />
            <span>
              {busy ? "Загрузка…" : "Фото или ZIP с группами"}
              <small>перетащите сюда или нажмите</small>
            </span>
          </div>
          <input
            aria-label="Название новой группы"
            className="group-input"
            value={inputGroup}
            onChange={(e) => setInputGroup(e.target.value)}
            placeholder="Название новой группы"
          />
          <input
            ref={fileRef}
            hidden
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,image/bmp,.zip"
            onChange={(e) => e.target.files && upload(e.target.files)}
          />
          <input
            ref={folderRef}
            hidden
            type="file"
            multiple
            {...({ webkitdirectory: "" } as any)}
            onChange={(e) => e.target.files && upload(e.target.files)}
          />
          <div className="flex gap">
            <button
              className="secondary small grow"
              onClick={() => folderRef.current?.click()}
            >
              <FolderOpen size={12} /> Папка
            </button>
            <button
              className="secondary small grow"
              onClick={async () => {
                try {
                  await post("/scan");
                  notify("Сканирование и обработка в очереди");
                } catch (e) {
                  notify(String(e));
                }
              }}
            >
              <RefreshCw size={12} /> Сканировать
            </button>
          </div>
          {unknown.length > 0 && (
            <button
              className="warning-link"
              onClick={() => useStore.setState({ photoEditor: unknown[0].id })}
            >
              <AlertCircle size={12} /> Без даты: {unknown.length} · указать
              вручную
            </button>
          )}
          {ps.some((p) => p.error) && (
            <button
              className="inline-warning"
              onClick={() =>
                useStore.setState({
                  photoEditor: ps.find((p) => p.error)?.id || null,
                })
              }
            >
              {ps.find((p) => p.error)?.error} · настроить кадр
            </button>
          )}
          {job && <JobProgress job={job} />}
        </div>
      )}
      <Port
        id="photos"
        type="source"
        color="#72bec9"
        top={data.collapsed ? "50%" : "64%"}
        label={data.collapsed ? undefined : "photos[]"}
      />
    </div>
  );
});
export const ProcessorNode = memo(function ProcessorNode({
  id,
  data,
}: NodeProps<WorkNode>) {
  const model = useStore((s) => s.models.find((m) => m.id === "3ddfa_v3")),
    photos = useStore((s) => s.photos),
    notify = useStore((s) => s.notify),
    refresh = useStore((s) => s.refresh),
    edges = useStore((s) => s.edges);
  const [runtime, setRuntime] = useState<any>({
    torch_threads: 2,
    detector_confidence: 0.7,
  });
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const rf = useReactFlow();
  useEffect(() => {
    api("/runtime")
      .then((r) => setRuntime((v: any) => ({ ...v, ...r })))
      .catch(() => {});
  }, []);
  const run = async () => {
    if (!edges.some((e) => e.target === id && e.targetHandle === "photos")) {
      notify("Сначала подключите источник фотографий");
      return;
    }
    setBusy(true);
    try {
      if (dirty) {
        await api("/runtime", { method: "PUT", body: JSON.stringify(runtime) });
        setDirty(false);
      }
      await post("/process");
      await refresh();
      notify("Обработка запущена. Совпадающий кэш будет использован повторно.");
    } catch (e) {
      notify(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="node-card processor-node">
      <NodeHead
        id={id}
        title="3DDFA_V3"
        icon={<Box size={16} />}
        subtitle="Реконструкция геометрии"
        collapsed={data.collapsed}
      >
        <Toggle
          label="Включить 3DDFA_V3"
          checked={!!model?.enabled}
          disabled={!model?.available}
          onChange={async (enabled) => {
            await api("/models/3ddfa_v3", {
              method: "PUT",
              body: JSON.stringify({ enabled }),
            });
            await refresh();
          }}
        />
      </NodeHead>
      {!data.collapsed && (
        <div className="node-content nodrag nowheel">
          <div className="model-identity">
            <div className="mesh-emblem">
              <svg viewBox="0 0 52 58">
                <ellipse cx="26" cy="24" rx="17" ry="23" />
                <path d="M9 24H43M11 13H41M11 35H41M16 3L15 45M26 1V48M36 3L37 45M11 13L26 24L41 13M11 35L26 24L41 35M15 45L26 38L37 45" />
              </svg>
            </div>
            <div>
              <span className="chip">MobileNet-V3</span>
              <span className="model-sub">
                <Cpu size={11} /> CPU · {runtime.torch_threads} потока
              </span>
              <span className="mini muted">35 709 вершин · 80D ID</span>
            </div>
          </div>
          <Slider
            label="Порог детектора"
            value={runtime.detector_confidence}
            min={0.4}
            max={0.95}
            step={0.01}
            onChange={(v) => {
              setRuntime({ ...runtime, detector_confidence: v });
              setDirty(true);
            }}
          />
          <Slider
            label="Потоки CPU"
            value={runtime.torch_threads}
            min={1}
            max={2}
            step={1}
            onChange={(v) => {
              setRuntime({ ...runtime, torch_threads: v });
              setDirty(true);
            }}
          />
          <button
            className={"secondary small " + (dirty ? "has-changes" : "")}
            disabled={busy || !model?.enabled}
            onClick={run}
          >
            <RefreshCw size={12} />
            {dirty ? "Применить и пересчитать" : "Рассчитать новые фото"}
          </button>
          {!model?.available && (
            <p className="inline-warning">{model?.reason}</p>
          )}
          <div className="model-cache-line">
            <StatusDot on={model?.available} />
            {photos.filter((p) => p.status === "ready").length} результатов в
            кэше
          </div>
        </div>
      )}
      <Port id="photos" type="target" color="#72bec9" top="32%" />
      <Port id="mesh" type="source" color="#b19ae8" top="40%" />
      <Port id="landmarks" type="source" color="#e8b870" top="61%" />
      <Port id="alpha_id" type="source" color="#a89ae9" top="82%" />
      {!data.collapsed && (
        <div className="output-captions">
          <span>mesh</span>
          <span>ldm</span>
          <span>α_id</span>
        </div>
      )}
    </div>
  );
});
export const MetricProcessorNode = memo(function MetricProcessorNode({
  id,
  data,
}: NodeProps<WorkNode>) {
  const table = useStore((s) => s.metrics),
    reveal = useStore((s) => s.revealNode);
  return (
    <div className="node-card metric-processor">
      <NodeHead
        id={id}
        title="Реестр метрик"
        subtitle={
          data.collapsed
            ? `${table.catalog.filter((m) => m.model === "3ddfa_v3").length} активных · 5 ракурсов`
            : undefined
        }
        icon={<Activity size={16} />}
        collapsed={data.collapsed}
      />
      {!data.collapsed && (
        <div className="node-content nodrag">
          <p className="mini muted">
            Функции Python + YAML. Новые метрики автоматически становятся
            дорожками таймлайна.
          </p>
          <div className="flex gap">
            <button
              className="secondary small"
              onClick={() => reveal("registry", { x: 700, y: 100 })}
            >
              <SlidersHorizontal size={12} /> Метрики
            </button>
            <button
              className="secondary small"
              onClick={() => reveal("poses", { x: 500, y: 100 })}
            >
              Ракурсы
            </button>
          </div>
        </div>
      )}
      <Port id="landmarks" type="target" top="50%" color="#e5b971" />
      <Port id="series" type="source" top="50%" color="#60cdb0" />
    </div>
  );
});
export const PendingNode = memo(function PendingNode({
  id,
  data,
}: NodeProps<WorkNode>) {
  return (
    <div className="node-card pending-node">
      <NodeHead
        id={id}
        title={data.title}
        subtitle="Расширение · следующий этап"
        collapsed={data.collapsed}
        icon={<Lock size={14} />}
      />
      {!data.collapsed && (
        <div className="node-content mini muted">
          Модель не установлена. Файлы трёх стартовых метрик для всех пяти
          ракурсов уже подготовлены. Результаты не подменяются.
        </div>
      )}
    </div>
  );
});
