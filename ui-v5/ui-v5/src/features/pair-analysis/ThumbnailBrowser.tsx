import { useCallback, useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { ResearchPhoto } from "../../shared/researchApi";
import { PhotoImage } from "../../shared/ui/PhotoImage";
import { TINT_LABELS, type TintLevel } from "./metricGroups";
import styles from "./pair.module.css";

/**
 * Четырёхрядный браузер миниатюр (§11.3).
 *
 * Ряды идут «змейкой» по времени: виртуализируется столбец, а не строка, потому
 * что кадров тысячи и хронологический порядок должен читаться слева направо
 * внутри столбца из N рядов. Виртуализация горизонтальная — при 1400 кадрах в
 * DOM остаётся около полусотни плиток.
 *
 * 🚨 WARNING: A-relative подсветка не является вероятностью совпадения
 * личности (прямой запрет §11.3). Уровень дублируется значком и текстом в
 * подписи, а не передаётся одним цветом: цвет — не единственный канал.
 */

export interface ThumbnailItem {
  photo: ResearchPhoto;
  tint: TintLevel;
  /** Значение метрики относительно A, если измерено. */
  relative: number | null;
}

const TINT_MARK: Record<TintLevel, string> = {
  near: "=",
  moderate: "~",
  far: "≠",
  unknown: "?",
  inapplicable: "×",
};

export function ThumbnailBrowser({
  items,
  rows,
  size,
  pairA,
  pairB,
  onPick,
  metricLabel,
}: {
  items: ThumbnailItem[];
  rows: number;
  size: number;
  pairA: string | null;
  pairB: string | null;
  onPick: (photoId: string) => void;
  metricLabel: string | null;
}) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [focus, setFocus] = useState(0);

  /** Столбцы «змейкой»: индекс i попадает в столбец i / rows. */
  const columnCount = Math.ceil(items.length / rows);
  const gap = 4;
  const columnWidth = size + gap;

  const virtualizer = useVirtualizer({
    horizontal: true,
    count: columnCount,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => columnWidth,
    overscan: 6,
  });

  /** Клавиатура (§11.3): стрелки двигают фокус, Enter назначает кадр. */
  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      const deltas: Record<string, number> = {
        ArrowRight: rows,
        ArrowLeft: -rows,
        ArrowDown: 1,
        ArrowUp: -1,
      };
      const delta = deltas[event.key];
      if (delta !== undefined) {
        event.preventDefault();
        setFocus((current) => Math.min(items.length - 1, Math.max(0, current + delta)));
        return;
      }
      if (event.key === "Enter" && items[focus]) {
        event.preventDefault();
        onPick(items[focus].photo.id);
      }
    },
    [focus, items, onPick, rows],
  );

  useEffect(() => {
    if (items.length === 0) return;
    virtualizer.scrollToIndex(Math.floor(focus / rows), { align: "auto" });
  }, [focus, rows, virtualizer, items.length]);

  const focused = items[focus];

  return (
    <div className={styles.browser}>
      <div
        ref={scrollRef}
        className={styles.browserScroll}
        style={{ height: rows * columnWidth + gap }}
        tabIndex={0}
        role="listbox"
        aria-label="Кадры в диапазоне, хронологический порядок"
        aria-activedescendant={focused ? `thumb-${focused.photo.id}` : undefined}
        onKeyDown={onKeyDown}
      >
        <div
          className={styles.browserInner}
          style={{ width: virtualizer.getTotalSize(), height: rows * columnWidth }}
        >
          {virtualizer.getVirtualItems().map((column) => {
            const start = column.index * rows;
            const slice = items.slice(start, start + rows);
            return (
              <div
                key={column.key}
                className={styles.browserColumn}
                style={{ transform: `translateX(${column.start}px)`, width: columnWidth }}
              >
                {slice.map((item, offset) => {
                  const index = start + offset;
                  const isA = item.photo.id === pairA;
                  const isB = item.photo.id === pairB;
                  return (
                    <button
                      key={item.photo.id}
                      id={`thumb-${item.photo.id}`}
                      type="button"
                      role="option"
                      aria-selected={isA || isB}
                      tabIndex={-1}
                      onClick={() => {
                        setFocus(index);
                        onPick(item.photo.id);
                      }}
                      className={styles.thumb}
                      data-tint={item.tint}
                      data-focused={index === focus}
                      data-pin={isA ? "a" : isB ? "b" : undefined}
                      style={{ width: size, height: size }}
                      title={`${item.photo.date ?? "дата н/д"} · ${item.photo.id}\n${TINT_LABELS[item.tint]}${
                        item.relative === null ? "" : ` · ${item.relative.toFixed(4)}`
                      }${metricLabel ? ` (${metricLabel})` : ""}`}
                    >
                      <PhotoImage
                        photoId={item.photo.id}
                        alt={`${item.photo.date ?? "дата н/д"}, ${TINT_LABELS[item.tint]}`}
                        variant="cover"
                        className={styles.thumbImage}
                      />
                      <span className={styles.thumbMark} aria-hidden="true">
                        {isA ? "A" : isB ? "B" : TINT_MARK[item.tint]}
                      </span>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      <p className={styles.browserFooter}>
        {focused ? (
          <>
            {focused.photo.date ?? "дата н/д"} · {focused.photo.id} ·{" "}
            {TINT_LABELS[focused.tint]}
            {focused.relative === null ? "" : ` · ${focused.relative.toFixed(4)}`}
          </>
        ) : (
          "В диапазоне нет кадров"
        )}
        <span className={styles.hint}>
          {" "}
          · стрелки перемещают фокус, Enter назначает кадр · в DOM{" "}
          {virtualizer.getVirtualItems().length * rows} из {items.length}
        </span>
      </p>
    </div>
  );
}
