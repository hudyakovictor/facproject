import { useEffect, useRef } from "react";
import { Link } from "@tanstack/react-router";
import { X } from "lucide-react";
import type { ResearchPhoto } from "../../shared/researchApi";
import { PhotoImage } from "../../shared/ui/PhotoImage";
import { poseFullLabel } from "../../shared/poseBins";
import { substantiveFlags } from "../../shared/findings";
import { missingFields } from "../../shared/api/contract";
import { SidecarEditor } from "./SidecarEditor";
import styles from "./dataManager.module.css";

/**
 * Временный ящик с деталями кадра (§7.5 ТЗ).
 *
 * ТЗ требует именно drawer, а не постоянную боковую панель: детали одного
 * кадра не должны отнимать место у таблицы, когда с ними закончили работать.
 *
 * Панель показывает и то, чего нет: список обязательных полей контракта,
 * отсутствующих у записи. Пустое место в карточке читается как «поле пустое»,
 * а явный перечень — как «backend их не прислал», и это разные утверждения.
 */

export interface DetailDrawerProps {
  photo: ResearchPhoto;
  onClose: () => void;
}

export function DetailDrawer({ photo, onClose }: DetailDrawerProps) {
  const ref = useRef<HTMLDivElement>(null);

  // Esc закрывает ящик: он временный, и выход должен быть без прицеливания мышью.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    ref.current?.focus();
  }, [photo.id]);

  const flags = substantiveFlags(photo);
  const missing = missingFields(photo);

  const rows: Array<[string, string]> = [
    ["Дата", photo.date ?? "н/д"],
    ["Происхождение даты", photo.dateProvenanceStatus ?? "н/д"],
    ["Ракурс", poseFullLabel(photo.bucket)],
    ["Эпоха", photo.era],
    ["Стадия", photo.analysisStage],
    ["Режим источника", photo.sourceMode],
    [
      "Качество",
      typeof photo.quality === "number" ? `${Math.round(photo.quality * 100)}%` : "н/д",
    ],
    ["Yaw", typeof photo.yaw === "number" ? `${photo.yaw.toFixed(1)}°` : "н/д"],
    ["Pitch", typeof photo.pitch === "number" ? `${photo.pitch.toFixed(1)}°` : "н/д"],
    ["Roll", typeof photo.roll === "number" ? `${photo.roll.toFixed(1)}°` : "н/д"],
    ["Состояние доказательств", photo.evidenceState ?? "н/д"],
    ["Пар в Stage 2", photo.stage2PairCount != null ? String(photo.stage2PairCount) : "н/д"],
    ["Аномалия EXIF", photo.exifAnomaly ? "да" : "нет"],
  ];

  return (
    <aside
      className={styles.drawer}
      role="dialog"
      aria-label={`Детали кадра ${photo.id}`}
      aria-modal="false"
      tabIndex={-1}
      ref={ref}
    >
      <header className={styles.drawerHead}>
        <h3 className={styles.drawerTitle}>{photo.id}</h3>
        <button type="button" onClick={onClose} aria-label="Закрыть детали">
          <X className="h-4 w-4" />
        </button>
      </header>

      <div className={styles.drawerBody}>
        <PhotoImage photoId={photo.id} alt="" className={styles.drawerImage} />

        <dl className={styles.drawerList}>
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd className={value === "н/д" ? styles.cellMissing : undefined}>{value}</dd>
            </div>
          ))}
        </dl>

        <section>
          <h4 className={styles.drawerSection}>Отметки</h4>
          {flags.length > 0 ? (
            <ul className={styles.drawerFlags}>
              {flags.map((flag) => (
                <li key={flag}>{flag}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.drawerNote}>Содержательных отметок нет.</p>
          )}
        </section>

        <section>
          <h4 className={styles.drawerSection}>Целостность и происхождение</h4>
          {/*
            Здесь нельзя показать хеши и цепочку источников: API их не отдаёт.
            Прежняя версия писала «недоступен в API» и рядом рисовала галочку
            совпадения хеша — то есть показывала результат несуществующей
            сверки.
          */}
          <p className={styles.drawerNote}>
            Хеши файла, цепочка источников и статус прав хранятся в sidecar,
            которого API пока не отдаёт (задача B-02). Сверка целостности в
            интерфейсе до этого невозможна, и её результат не показывается.
          </p>
        </section>

        {missing.length > 0 && (
          <section>
            <h4 className={styles.drawerSection}>Отсутствующие поля контракта</h4>
            <p className={styles.drawerNote}>
              Backend не прислал: {missing.join(", ")}. Значения не подставлены.
            </p>
          </section>
        )}

        <SidecarEditor photo={photo} />

        <div className={styles.drawerActions}>
          <Link
            to="/inspector"
            search={(prev) => ({ ...prev, photo: photo.id })}
            className={styles.drawerLink}
          >
            Открыть в инспекторе
          </Link>
          <Link
            to="/timeline"
            search={(prev) => ({ ...prev, photo: photo.id })}
            className={styles.drawerLink}
          >
            Показать на таймлайне
          </Link>
        </div>
      </div>
    </aside>
  );
}
