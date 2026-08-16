import { useMemo, useRef } from "react";
import {
  createColumnHelper,
  createSortedRowModel,
  rowSortingFeature,
  tableFeatures,
  useTable,
  type SortingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { ResearchPhoto } from "../../shared/researchApi";
import { columnById, type DataColumn } from "./columns";
import styles from "./dataManager.module.css";

/**
 * Таблица данных на TanStack Table v9 + виртуализация строк (§7.4, дефект D11).
 *
 * Прежняя таблица держала в DOM все строки сразу и рисовала пагинацию,
 * которая ничего не листала: подпись «1–10 из 137» была литералом, а кнопки
 * страниц не имели обработчиков. При 1400 кадрах это и медленно, и неправда.
 *
 * Здесь в DOM попадают только видимые строки, сортировка выполняется моделью
 * таблицы, а прокрутка отражает весь набор целиком — числа под таблицей
 * считаются, а не пишутся.
 *
 * Замечание о версии: `@tanstack/react-table@9` — актуальная линейка с явной
 * регистрацией возможностей (`tableFeatures`), а не legacy, как ошибочно
 * утверждал ранний аудит (D28). Регистрируется ровно одна возможность —
 * сортировка строк; остальное таблице здесь не нужно.
 */

const features = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
});

const helper = createColumnHelper<typeof features, ResearchPhoto>();

const ROW_HEIGHT = 30;

export interface DataTableProps {
  photos: readonly ResearchPhoto[];
  visibleColumns: readonly string[];
  sorting: SortingState;
  onSortingChange: (next: SortingState) => void;
  selectedIds: ReadonlySet<string>;
  onToggleSelect: (id: string, shiftKey: boolean) => void;
  activeId: string | null;
  onOpenDetail: (id: string) => void;
  /** Высота области прокрутки в пикселях. */
  height: number;
}

export function DataTable({
  photos,
  visibleColumns,
  sorting,
  onSortingChange,
  selectedIds,
  onToggleSelect,
  activeId,
  onOpenDetail,
  height,
}: DataTableProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const columns = useMemo(() => {
    const chosen = visibleColumns
      .map((id) => columnById(id))
      .filter((column): column is DataColumn => Boolean(column));

    return helper.columns(
      chosen.map((column) =>
        helper.accessor((photo: ResearchPhoto) => column.value(photo), {
          id: column.id,
          header: column.header,
          // Ячейку рисует описание колонки: одно место отвечает и за
          // сортируемое значение, и за то, что видит человек.
          cell: (context) => column.render(context.row.original),
          sortUndefined: "last",
        }),
      ),
    );
  }, [visibleColumns]);

  const data = useMemo(() => [...photos], [photos]);

  const table = useTable({
    features,
    columns,
    data,
    state: { sorting },
    onSortingChange: (updater) =>
      onSortingChange(typeof updater === "function" ? updater(sorting) : updater),
    getRowId: (row) => row.id,
  });

  const rows = table.getRowModel().rows;

  /*
   * React Compiler сообщает, что `useVirtualizer` возвращает функции, которые
   * нельзя мемоизировать, и пропускает оптимизацию этого компонента. Это
   * ожидаемо: виртуализатор обязан пересчитываться при каждой прокрутке, иначе
   * он будет отдавать устаревшие позиции строк. Предупреждение относится к
   * оптимизации, а не к корректности.
   */
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    getItemKey: (index) => rows[index].id,
    overscan: 12,
  });

  const totalWidth = visibleColumns.reduce(
    (sum, id) => sum + (columnById(id)?.width ?? 120),
    36,
  );

  return (
    <div className={styles.tableShell}>
      <div
        ref={scrollRef}
        className={styles.tableScroll}
        style={{ height }}
        role="region"
        aria-label="Таблица кадров архива"
        tabIndex={0}
      >
        <div style={{ width: totalWidth, minWidth: "100%" }}>
          <div className={styles.headRow} role="row">
            <span className={styles.cellSelect} aria-hidden="true" />
            {table.getHeaderGroups()[0]?.headers.map((header) => {
              const column = columnById(header.column.id);
              const sorted = header.column.getIsSorted();
              return (
                <button
                  key={header.id}
                  type="button"
                  role="columnheader"
                  aria-sort={
                    sorted === "asc"
                      ? "ascending"
                      : sorted === "desc"
                        ? "descending"
                        : "none"
                  }
                  className={`${styles.headCell} ${column?.align === "right" ? styles.alignRight : ""}`}
                  style={{ width: column?.width ?? 120 }}
                  onClick={header.column.getToggleSortingHandler()}
                  title={
                    column?.origin === "absent"
                      ? column.note
                      : "Нажмите для сортировки"
                  }
                >
                  {column?.header ?? header.column.id}
                  {column?.origin === "absent" ? (
                    <span className={styles.headAbsent}> · нет источника</span>
                  ) : null}
                  <span className={styles.sortMark} aria-hidden="true">
                    {sorted === "asc" ? "▲" : sorted === "desc" ? "▼" : ""}
                  </span>
                </button>
              );
            })}
          </div>

          <div
            style={{ height: virtualizer.getTotalSize(), position: "relative" }}
            role="rowgroup"
          >
            {virtualizer.getVirtualItems().map((item) => {
              const row = rows[item.index];
              const photo = row.original;
              const selected = selectedIds.has(photo.id);
              return (
                <div
                  key={row.id}
                  data-index={item.index}
                  role="row"
                  aria-selected={selected}
                  className={`${styles.bodyRow} ${photo.id === activeId ? styles.bodyRowActive : ""} ${selected ? styles.bodyRowSelected : ""}`}
                  style={{ transform: `translateY(${item.start}px)`, height: ROW_HEIGHT }}
                  onClick={() => onOpenDetail(photo.id)}
                >
                  <span className={styles.cellSelect}>
                    <input
                      type="checkbox"
                      checked={selected}
                      aria-label={`Выбрать ${photo.id}`}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) =>
                        onToggleSelect(
                          photo.id,
                          (event.nativeEvent as MouseEvent).shiftKey ?? false,
                        )
                      }
                    />
                  </span>
                  {row.getAllCells().map((cell) => {
                    const column = columnById(cell.column.id);
                    const text = column ? column.render(photo) : "";
                    return (
                      <span
                        key={cell.id}
                        role="cell"
                        className={`${styles.bodyCell} ${column?.align === "right" ? styles.alignRight : ""} ${text === "н/д" ? styles.cellMissing : ""}`}
                        style={{ width: column?.width ?? 120 }}
                        title={text}
                      >
                        {text}
                      </span>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <p className={styles.tableFooter}>
        {/* Числа считаются, а не пишутся литералом, как было раньше. */}
        Строк: {rows.length.toLocaleString("ru-RU")} · в DOM:{" "}
        {virtualizer.getVirtualItems().length} · выбрано: {selectedIds.size}
      </p>
    </div>
  );
}
