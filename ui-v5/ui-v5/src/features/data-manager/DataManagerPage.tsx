import { useCallback, useMemo, useState } from "react";
import type { SortingState } from "@tanstack/react-table";
import { Search, Columns3, RefreshCw } from "lucide-react";
import { useTimeline } from "../../shared/api/queries";
import type { ResearchPhoto } from "../../shared/researchApi";
import { poseLabel, sortPoseBins } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { DataContractBanner } from "../../shared/ui/DataContractBanner";
import { EmptyState, ErrorState, LoadingState } from "../../shared/ui/states";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { DATA_COLUMNS, DEFAULT_COLUMN_IDS } from "./columns";
import { DataTable } from "./DataTable";
import { DetailDrawer } from "./DetailDrawer";
import { IngestPanel } from "./IngestPanel";
import { JobQueue } from "./JobQueue";
import { BatchBar } from "./BatchBar";
import styles from "./dataManager.module.css";

/**
 * Экран «Данные и provenance» (§7 ТЗ).
 *
 * Что здесь исправлено по сравнению с прежней версией (BUG-3, D11):
 *  - таблица виртуализирована и сортируется по-настоящему; пагинация с
 *    литеральной подписью «1–10 из 137» и кнопками без обработчиков убрана;
 *  - колонки, для которых у API нет источника (хеши, дубликаты, права),
 *    больше не изображают результат: они помечены «нет источника» и
 *    показывают «н/д» вместо галочки о совпадении, которого никто не проверял;
 *  - появились приём файлов, очередь заданий и пакетные операции — разделы
 *    §7.1, §7.6, §7.7, которых не было вовсе.
 */

const TABLE_HEIGHT = 420;

export function DataManagerPage() {
  const {
    search,
    setSearch,
    activePose,
    setActivePose,
    multiPose,
    setMultiPose,
    selectedPhoto,
    setSelectedPhoto,
  } = useAnalysisStore();

  const [visibleColumns, setVisibleColumns] = useState<string[]>(DEFAULT_COLUMN_IDS);
  const [showColumnChooser, setShowColumnChooser] = useState(false);
  const [sorting, setSorting] = useState<SortingState>([{ id: "date", desc: false }]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const query = useTimeline();
  const stage = resolveStage(query.data);
  const photos = useMemo(() => query.data?.photos ?? [], [query.data]);

  const poseOptions = useMemo(
    () => sortPoseBins(Array.from(new Set(photos.map((photo) => photo.bucket)))),
    [photos],
  );

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return photos.filter((photo) => {
      if (!multiPose && photo.bucket !== activePose) return false;
      if (!needle) return true;
      // Поиск идёт по тем же полям, что показаны в таблице.
      return [photo.id, photo.date, photo.bucket, photo.era, ...photo.flags]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [photos, multiPose, activePose, search]);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectedPhotos = useMemo(
    () => photos.filter((photo) => selectedIds.has(photo.id)),
    [photos, selectedIds],
  );

  const detail: ResearchPhoto | undefined = useMemo(
    () => photos.find((photo) => photo.id === selectedPhoto),
    [photos, selectedPhoto],
  );

  if (query.isLoading) return <LoadingState text="Загрузка каталога данных…" />;
  if (query.error)
    return (
      <ErrorState
        title="Каталог данных недоступен"
        error={query.error}
        onRetry={() => void query.refetch()}
      />
    );

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h2 className={styles.title}>
          ДАННЫЕ И PROVENANCE · {stageLabel(stage)}
        </h2>

        <select
          aria-label="Фильтр по ракурсу"
          value={multiPose ? "ALL" : activePose}
          onChange={(event) => {
            const next = event.target.value;
            if (next === "ALL") setMultiPose(true);
            else {
              setMultiPose(false);
              setActivePose(next);
            }
          }}
          className={styles.select}
        >
          <option value="ALL">Ракурс: все</option>
          {poseOptions.map((pose) => (
            <option key={pose} value={pose}>
              {poseLabel(pose)}
            </option>
          ))}
        </select>

        <label className={styles.searchBox}>
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="sr-only">Поиск по кадрам</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="ID, дата, отметка…"
          />
        </label>

        <div className={styles.menuRoot}>
          <button
            type="button"
            className={styles.linkButton}
            aria-expanded={showColumnChooser}
            onClick={() => setShowColumnChooser((value) => !value)}
          >
            <Columns3 className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
            Колонки · {visibleColumns.length}
          </button>
          {showColumnChooser && (
            <div className={styles.columnMenu} role="group" aria-label="Выбор колонок">
              {DATA_COLUMNS.map((column) => (
                <label key={column.id} className={styles.columnRow}>
                  <input
                    type="checkbox"
                    checked={visibleColumns.includes(column.id)}
                    onChange={() =>
                      setVisibleColumns((prev) =>
                        prev.includes(column.id)
                          ? prev.filter((id) => id !== column.id)
                          : [...prev, column.id],
                      )
                    }
                  />
                  <span>{column.header}</span>
                  {column.origin === "absent" && (
                    <span className={styles.columnAbsent} title={column.note}>
                      нет источника
                    </span>
                  )}
                </label>
              ))}
              <p className={styles.columnNote}>
                Колонки с пометкой «нет источника» остаются в списке намеренно:
                отсутствие хешей и sidecar в API — факт о системе, а не пустая
                ячейка.
              </p>
            </div>
          )}
        </div>

        <button
          type="button"
          className={styles.linkButton}
          onClick={() => void query.refetch()}
          aria-label="Обновить каталог"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </header>

      <div className={styles.banners}>
        <StageBanner stage={stage} note={query.data?.note} />
        <DataContractBanner
          photos={photos}
          totalPhotos={photos.length}
          completeCount={query.data?.ui_fields_complete_photo_count}
          violationsByField={query.data?.ui_fields_violations_by_field}
          schema={query.data?.ui_fields_schema}
        />
      </div>

      <div className={styles.body}>
        <div className={styles.main}>
          {photos.length === 0 ? (
            <EmptyState
              title="Записей нет"
              description="API вернул пустой список фотографий. Проверьте, что Stage 1 выполнен и каталог данных смонтирован."
            />
          ) : (
            <>
              <p className={styles.counts}>
                Всего в архиве: {photos.length.toLocaleString("ru-RU")} · после фильтров:{" "}
                {filtered.length.toLocaleString("ru-RU")}
              </p>

              <BatchBar
                selected={selectedPhotos}
                visibleColumns={visibleColumns}
                onClearSelection={() => setSelectedIds(new Set())}
              />

              <DataTable
                photos={filtered}
                visibleColumns={visibleColumns}
                sorting={sorting}
                onSortingChange={setSorting}
                selectedIds={selectedIds}
                onToggleSelect={toggleSelect}
                activeId={selectedPhoto}
                onOpenDetail={setSelectedPhoto}
                height={TABLE_HEIGHT}
              />
            </>
          )}

          <IngestPanel />
          <JobQueue />
        </div>

        {detail && (
          <DetailDrawer photo={detail} onClose={() => setSelectedPhoto(null)} />
        )}
      </div>
    </div>
  );
}
