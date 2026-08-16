import { useCallback, useMemo, useRef, useState } from "react";
import { Crosshair, Minus, Plus, RotateCcw } from "lucide-react";
import { useLandmarks } from "../../shared/api/queries";
import { Button, IconButton } from "../../shared/ui/primitives";
import { LAYERS, type LayerDef, type LayerId } from "./layers";
import styles from "./inspector.module.css";

/**
 * Левая область инспектора (§10.2): слои поверх кадра, зум/панорама,
 * непрозрачность, координаты пикселя.
 *
 * Слои — это разные файлы Stage 1, а не фильтры на одной картинке:
 * `original.jpg`, `face_crop.jpg`, `face_mask.png`, `uv_texture.png`. Поэтому
 * переключатель слоя меняет источник, а ползунок непрозрачности накладывает
 * выбранный слой на исходный кадр. Наложить `face_crop` на `original` в верных
 * координатах нельзя без bbox, поэтому режим наложения включается только для
 * слоёв, снятых в системе исходного кадра.
 *
 * 🚨 WARNING: слой, файла которого нет в перечне артефактов кадра, не
 * показывается пустым — кнопка отключается с подписью причины. Пустой холст
 * читался бы как «маска пустая», то есть как измерение.
 */

function artifactUrl(photoId: string, name: string): string {
  return `/api/v1/photos/${encodeURIComponent(photoId)}/artifacts/${encodeURIComponent(name)}`;
}

export function SplitView({
  photoId,
  artifacts,
}: {
  photoId: string;
  artifacts: string[];
}) {
  const available = useMemo(() => new Set(artifacts), [artifacts]);
  const [layer, setLayer] = useState<LayerId>("original");
  const [opacity, setOpacity] = useState(100);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const [ldmCount, setLdmCount] = useState<106 | 134>(106);
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const frameRef = useRef<HTMLDivElement | null>(null);

  const definition = LAYERS.find((item) => item.id === layer) ?? LAYERS[0];
  const needsLandmarks = layer === "landmarks";
  const landmarks = useLandmarks(photoId, ldmCount, "original", { enabled: needsLandmarks });

  /**
   * Слой недоступен, если его файла нет среди артефактов. Для «видимости»
   * артефакта не существует вовсе — это честно отдельная причина.
   */
  const unavailable = useCallback(
    (item: LayerDef): string | null => {
      if (item.id === "visibility") {
        return "Отдельного артефакта карты видимости в Stage 1 нет";
      }
      if (item.artifact && !available.has(item.artifact)) {
        return `Файл ${item.artifact} не создан для этого кадра`;
      }
      return null;
    },
    [available],
  );

  const reset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    dragRef.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = frameRef.current?.getBoundingClientRect();
    if (rect && rect.width > 0 && rect.height > 0) {
      // Координата в системе неувеличенного кадра: пользователю нужен пиксель
      // изображения, а не пиксель экрана.
      const cx = (event.clientX - rect.left - rect.width / 2 - pan.x) / zoom + rect.width / 2;
      const cy = (event.clientY - rect.top - rect.height / 2 - pan.y) / zoom + rect.height / 2;
      setCursor({ x: Math.round(cx), y: Math.round(cy) });
    }
    const drag = dragRef.current;
    if (!drag) return;
    setPan({ x: drag.panX + (event.clientX - drag.x), y: drag.panY + (event.clientY - drag.y) });
  };

  const endDrag = () => {
    dragRef.current = null;
  };

  const blocked = unavailable(definition);
  const overlayMode = definition.inOriginalSpace && layer !== "original" && opacity < 100;

  return (
    <section className={styles.panel} aria-label="Просмотр слоёв кадра">
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>СЛОИ КАДРА</span>
        <span className={styles.panelMeta}>
          {cursor ? `x ${cursor.x} · y ${cursor.y}` : "координаты: наведите курсор"}
        </span>
      </div>

      <div className={styles.layerBar} role="group" aria-label="Выбор слоя">
        {LAYERS.map((item) => {
          const reason = unavailable(item);
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setLayer(item.id)}
              disabled={reason !== null}
              aria-pressed={layer === item.id}
              title={reason ?? item.note}
              className={styles.layerButton}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      <div className={styles.controlRow}>
        <IconButton label="Уменьшить" onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))}>
          <Minus className="h-3.5 w-3.5" />
        </IconButton>
        <span className={styles.zoomValue}>{Math.round(zoom * 100)}%</span>
        <IconButton label="Увеличить" onClick={() => setZoom((z) => Math.min(8, z + 0.25))}>
          <Plus className="h-3.5 w-3.5" />
        </IconButton>
        <IconButton label="Сбросить вид" onClick={reset}>
          <RotateCcw className="h-3.5 w-3.5" />
        </IconButton>
        <label className={styles.opacityLabel}>
          Непрозрачность
          <input
            type="range"
            min={0}
            max={100}
            value={opacity}
            onChange={(event) => setOpacity(Number(event.target.value))}
            aria-label="Непрозрачность слоя"
          />
          <span className={styles.zoomValue}>{opacity}%</span>
        </label>
        {needsLandmarks && (
          <div className={styles.ldmSwitch} role="group" aria-label="Число точек">
            <button
              type="button"
              aria-pressed={ldmCount === 106}
              onClick={() => setLdmCount(106)}
              className={styles.layerButton}
            >
              106
            </button>
            <button
              type="button"
              aria-pressed={ldmCount === 134}
              onClick={() => setLdmCount(134)}
              className={styles.layerButton}
            >
              134
            </button>
          </div>
        )}
      </div>

      <div
        ref={frameRef}
        className={styles.canvasFrame}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerLeave={() => {
          endDrag();
          setCursor(null);
        }}
      >
        {blocked ? (
          <p className={styles.layerBlocked}>{blocked}</p>
        ) : (
          <div
            className={styles.canvasInner}
            style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
          >
            {overlayMode && (
              <img
                src={artifactUrl(photoId, "original.jpg")}
                alt=""
                aria-hidden="true"
                className={styles.canvasImage}
              />
            )}
            {definition.artifact && (
              <img
                src={artifactUrl(photoId, definition.artifact)}
                alt={`Слой «${definition.label}» кадра ${photoId}`}
                className={overlayMode ? styles.canvasOverlay : styles.canvasImage}
                style={{ opacity: opacity / 100 }}
              />
            )}
            {needsLandmarks && (
              <>
                <img
                  src={artifactUrl(photoId, "original.jpg")}
                  alt={`Кадр ${photoId} с точками`}
                  className={styles.canvasImage}
                />
                <LandmarkOverlay
                  points={landmarks.data?.points ?? []}
                  loading={landmarks.isPending}
                  failed={landmarks.isError}
                  opacity={opacity / 100}
                />
              </>
            )}
          </div>
        )}
      </div>

      <p className={styles.layerNote}>{definition.note}</p>
      {overlayMode && (
        <p className={styles.layerNote}>
          Режим наложения: слой поверх исходного кадра. Совмещение верно только для
          слоёв в системе координат исходника.
        </p>
      )}
      <div className={styles.controlRow}>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            if (definition.artifact) {
              window.open(artifactUrl(photoId, definition.artifact), "_blank", "noopener");
            }
          }}
          disabled={!definition.artifact}
        >
          <Crosshair className="h-3.5 w-3.5" /> Открыть файл слоя
        </Button>
      </div>
    </section>
  );
}

/**
 * Точки поверх кадра. Координаты приходят в пикселях исходного изображения, а
 * рисуются в процентах от размера контейнера — иначе при зуме и панораме точки
 * уехали бы относительно картинки.
 */
function LandmarkOverlay({
  points,
  loading,
  failed,
  opacity,
}: {
  points: number[][];
  loading: boolean;
  failed: boolean;
  opacity: number;
}) {
  if (loading) return <p className={styles.overlayNote}>Загрузка точек…</p>;
  if (failed) return <p className={styles.overlayNote}>Точки для этого кадра недоступны</p>;
  if (points.length === 0) return <p className={styles.overlayNote}>Файл точек пуст</p>;

  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;

  return (
    <svg
      className={styles.landmarkSvg}
      viewBox={`${minX} ${minY} ${spanX} ${spanY}`}
      preserveAspectRatio="none"
      style={{ opacity }}
      role="img"
      aria-label={`Наложено точек: ${points.length}`}
    >
      {points.map((point, index) => (
        <circle
          key={index}
          cx={point[0]}
          cy={point[1]}
          r={Math.max(spanX, spanY) / 160}
          className={styles.landmarkDot}
        />
      ))}
    </svg>
  );
}
