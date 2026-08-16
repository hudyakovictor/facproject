import { useState } from "react";
import { Download } from "lucide-react";
import type { ResearchPhoto } from "../../shared/researchApi";
import { buildCsv, buildViewState, downloadText, NOT_A_VERDICT } from "./exportView";
import type { Viewport } from "./viewport";
import styles from "./timeline.module.css";

/**
 * Экспорт видимого среза таймлайна (§8.10 ТЗ).
 *
 * Выгружаются те кадры и те метрики, что сейчас на экране, — вместе с
 * границами окна, схемой ответа и пометкой «не вердикт». Обещать здесь
 * «figure request с claim ID» нельзя: публикации и claim ID появятся вместе с
 * соответствующим контуром backend, а кнопка, которая ничего не отправляет,
 * хуже отсутствующей.
 */

export interface ExportMenuProps {
  photos: readonly ResearchPhoto[];
  metrics: readonly string[];
  viewport: Viewport;
  pose: string;
  multiPose: boolean;
  schema: string | null;
  sourceMode: string | null;
}

export function ExportMenu(props: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const context = () => ({
    photos: props.photos,
    metrics: props.metrics,
    viewport: props.viewport,
    pose: props.pose,
    multiPose: props.multiPose,
    schema: props.schema,
    sourceMode: props.sourceMode,
    permalink: typeof window === "undefined" ? "" : window.location.href,
  });

  const stamp = new Date().toISOString().slice(0, 10);

  return (
    <div className={styles.menuRoot}>
      <button
        type="button"
        className={styles.menuTrigger}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Download className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
        Экспорт
      </button>

      {open ? (
        <div className={styles.menuPanel} role="group" aria-label="Экспорт вида">
          <p className={styles.menuNote}>
            Выгружается видимый срез: {props.photos.length} кадров,{" "}
            {props.metrics.length} метрик. В файл записывается пометка «не вердикт»,
            схема ответа и границы окна.
          </p>

          <button
            type="button"
            className={styles.menuAction}
            disabled={props.photos.length === 0}
            onClick={() => {
              downloadText(
                `timeline-${stamp}.csv`,
                buildCsv(context()),
                "text/csv",
              );
              setOpen(false);
            }}
          >
            CSV видимых данных
          </button>

          <button
            type="button"
            className={styles.menuAction}
            onClick={() => {
              downloadText(
                `timeline-view-${stamp}.json`,
                buildViewState(context()),
                "application/json",
              );
              setOpen(false);
            }}
          >
            JSON состояния вида
          </button>

          <button
            type="button"
            className={styles.menuAction}
            onClick={() => {
              void navigator.clipboard
                ?.writeText(window.location.href)
                .then(() => setCopied(true))
                .catch(() => setCopied(false));
            }}
          >
            {copied ? "Ссылка скопирована" : "Копировать permalink"}
          </button>

          <p className={styles.menuFootnote}>{NOT_A_VERDICT}</p>
          <p className={styles.menuFootnote}>
            Экспорт изображения (PNG/SVG) и запрос иллюстрации для публикации
            появятся вместе с контуром публикаций: сейчас claim ID присвоить нечему.
          </p>
        </div>
      ) : null}
    </div>
  );
}
