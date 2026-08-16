import { Suspense, lazy, useCallback, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, Link2 } from "lucide-react";
import { usePhotoInfoKeys, useTimeline } from "../../shared/api/queries";
import { poseLabel } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { QueryState } from "../../shared/ui/QueryState";
import { Badge, Button, IconButton } from "../../shared/ui/primitives";
import { LoadingState } from "../../shared/ui/states";
import { describeError } from "../../shared/ui/errorDetail";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { consoleLogger } from "../../shared/logger";
import { compactFacts } from "./compactFacts";
import { InspectorTabs } from "./InspectorTabs";
import { ManualQA } from "./ManualQA";
import { SplitView } from "./SplitView";
import styles from "./inspector.module.css";

/**
 * Инспектор фотографии (§10).
 *
 * Раньше страница показывала восемь полей из `/timeline` и два одинаковых
 * превью одного и того же кадра — левое было подписано «исходный кадр Stage 2»,
 * правое «превью реального кадра». Теперь кадр читается из
 * `/api/v1/photos/{id}/info_keys`: около 156 ключей Stage 1, артефакты,
 * валидация и зоны кожи.
 *
 * 🚨 WARNING: страница не выносит суждений о личности. Качество, аутентичность
 * кожи и репроекция — входные данные сравнения пар, а не его результат.
 */

/**
 * Three.js весит около 900 КБ и нужен только для правой панели. Статический
 * импорт заставлял бы ждать его загрузки, чтобы увидеть факты о кадре, поэтому
 * панель подгружается отдельным чанком по требованию.
 */
const FaceMesh3D = lazy(() =>
  import("../../shared/ui/FaceMesh3D").then((module) => ({ default: module.FaceMesh3D })),
);

function poseBinOf(photo: { bucket?: string | null }): string {
  return photo.bucket ?? "unknown";
}

export function PhotoInspectorPage() {
  const timeline = useTimeline();
  const photos = useMemo(() => timeline.data?.photos ?? [], [timeline.data]);
  const {
    selectedPhoto: selectedId,
    setSelectedPhoto: setSelectedId,
    activePose,
    assignToPair,
  } = useAnalysisStore();

  // Инспектор также используется как автономная панель (например, в
  // resilience-тестах и при встраивании в рабочую станцию), поэтому он не
  // должен падать без RouterProvider. В штатном маршруте id читается из
  // адреса, а состояние стора остаётся fallback для открытий из таймлайна.
  const routePhotoId =
    typeof window === "undefined"
      ? undefined
      : decodeURIComponent(window.location.pathname.match(/\/photos\/([^/]+)/)?.[1] ?? "") || undefined;
  /**
   * Подтверждение копирования — счётчик, а не флаг: он растёт при каждом
   * нажатии и перезапускает CSS-анимацию, которая сама убирает надпись.
   * Таймер на это не нужен, а надпись на кнопке не прыгает.
   */
  const [copyCount, setCopyCount] = useState(0);
  const [pairRejection, setPairRejection] = useState<string | null>(null);

  /**
   * Соседние кадры считаются в пределах активного ракурса (§10.1): «следующий»
   * при включённом фильтре по бину должен вести к следующему кадру того же
   * бина, иначе кнопка выбрасывает пользователя из его выборки.
   */
  const scope = useMemo(() => {
    if (!activePose || activePose === "all") return photos;
    const filtered = photos.filter((photo) => poseBinOf(photo) === activePose);
    return filtered.length > 0 ? filtered : photos;
  }, [photos, activePose]);

  const current = useMemo(() => {
    const wanted = routePhotoId || selectedId;
    const byId = wanted ? photos.find((photo) => photo.id === wanted) : undefined;
    return byId ?? scope[0] ?? photos[0] ?? null;
  }, [photos, scope, selectedId, routePhotoId]);

  const index = current ? scope.findIndex((photo) => photo.id === current.id) : -1;

  const step = useCallback(
    (delta: number) => {
      if (index < 0) return;
      const next = scope[index + delta];
      if (next) setSelectedId(next.id);
    },
    [index, scope, setSelectedId],
  );

  const copyPermalink = useCallback(() => {
    if (!current) return;
    const url = new URL(window.location.href);
    url.searchParams.set("photo", current.id);
    void navigator.clipboard
      ?.writeText(url.toString())
      .then(() => setCopyCount((count) => count + 1))
      .catch((error: unknown) => {
        consoleLogger.addLog(
          "WARN",
          "inspector",
          "Ссылку скопировать не удалось",
          describeError(error).message,
        );
      });
  }, [current]);

  return (
    <QueryState
      query={timeline}
      loadingText="Загрузка записей фотографий…"
      errorTitle="Инспектор недоступен"
      isEmpty={(data) => data.photos.length === 0}
      emptyTitle="Записей нет"
      emptyDescription="API вернул пустой список фотографий, показывать в инспекторе нечего."
    >
      {() =>
        current ? (
          <div className="flex h-workspace w-full flex-col gap-4 overflow-y-auto bg-surface-canvas p-6 text-ink-primary">
            <StageBanner stage={resolveStage(timeline.data)} note={timeline.data?.note} />

            <header className={styles.header}>
              <div className={styles.headerMain}>
                <span className={styles.headerId}>{current.id}</span>
                <span className={styles.headerMeta}>
                  {stageLabel(resolveStage(timeline.data))} · {current.date ?? "дата н/д"} ·
                  ракурс: {poseLabel(poseBinOf(current))} · кадр {index + 1} из {scope.length}
                  {activePose && activePose !== "all" ? " в активном ракурсе" : ""}
                </span>
              </div>

              <div className={styles.headerActions}>
                <IconButton
                  label="Предыдущий кадр"
                  onClick={() => step(-1)}
                  disabled={index <= 0}
                >
                  <ChevronLeft className="h-4 w-4" />
                </IconButton>
                <IconButton
                  label="Следующий кадр"
                  onClick={() => step(1)}
                  disabled={index < 0 || index >= scope.length - 1}
                >
                  <ChevronRight className="h-4 w-4" />
                </IconButton>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    setPairRejection(
                      assignToPair(current.id, poseBinOf(current), (id) =>
                        photos.find((photo) => photo.id === id)?.bucket,
                      ),
                    )
                  }
                >
                  В пару
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    window.open(
                      `/api/v1/photos/${encodeURIComponent(current.id)}/image`,
                      "_blank",
                      "noopener",
                    )
                  }
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Исходник
                </Button>
                <Button size="sm" variant="ghost" onClick={copyPermalink}>
                  <Link2 className="h-3.5 w-3.5" /> Ссылка
                </Button>
                {copyCount > 0 && (
                  <span key={copyCount} className={styles.copyToast} role="status">
                    Скопировано
                  </span>
                )}
              </div>
            </header>

            {pairRejection && (
              <p className="text-2xs text-amber-300" role="status">
                {pairRejection}
              </p>
            )}

            <label className="flex items-center gap-2 text-2xs text-ink-muted">
              Кадр
              <select
                aria-label="Выбор фотографии"
                value={current.id}
                onChange={(event) => setSelectedId(event.target.value)}
                className="max-w-md rounded border border-line-default bg-surface-raised px-2 py-1 font-mono text-xs text-ink-primary"
              >
                {scope.slice(0, 500).map((photo) => (
                  <option key={photo.id} value={photo.id}>
                    {photo.date ?? "н/д"} · {photo.id}
                  </option>
                ))}
              </select>
            </label>

            <InspectorBody photoId={current.id} />
          </div>
        ) : null
      }
    </QueryState>
  );
}

/**
 * Тело инспектора зависит от второго запроса — полного `info.json`. Он вынесен
 * в отдельный компонент, чтобы смена кадра не перерисовывала шапку и список.
 */
function InspectorBody({ photoId }: { photoId: string }) {
  const details = usePhotoInfoKeys(photoId);

  return (
    <QueryState
      query={details}
      loadingText="Загрузка параметров кадра…"
      errorTitle="Параметры кадра недоступны"
    >
      {(data) => {
        const facts = compactFacts(data);
        return (
          <>
            <section className={styles.panel} aria-label="Компактные факты">
              <div className={styles.panelHeader}>
                <span className={styles.panelTitle}>КОМПАКТНЫЕ ФАКТЫ</span>
                <Badge tone="neutral">{data.artifacts?.length ?? 0} артефактов</Badge>
              </div>
              <div className={styles.factGrid}>
                {facts.map((fact) => (
                  <div key={fact.key} className={styles.factCard} data-warn={fact.warn ?? false}>
                    <div className={styles.factLabel}>{fact.label}</div>
                    <div className={styles.factValue} data-null={fact.value === null}>
                      {fact.value ?? "н/д"}
                    </div>
                    {fact.hint && <div className={styles.factHint}>{fact.hint}</div>}
                  </div>
                ))}
              </div>
            </section>

            <div className={styles.splitGrid}>
              <SplitView photoId={photoId} artifacts={data.artifacts ?? []} />
              {/* Правая область §10.2: реконструкция кадра, если mesh.obj создан. */}
              <section className={styles.panel} aria-label="Трёхмерная модель кадра">
                <div className={styles.panelHeader}>
                  <span className={styles.panelTitle}>МОДЕЛЬ КАДРА</span>
                </div>
                <Suspense fallback={<LoadingState text="Загрузка трёхмерного просмотра…" />}>
                  <FaceMesh3D photoId={photoId} />
                </Suspense>
              </section>
            </div>

            <InspectorTabs data={data} />

            <ManualQA photoId={photoId} />
          </>
        );
      }}
    </QueryState>
  );
}
