import { Link } from "@tanstack/react-router";
import type { ResearchPhoto } from "../../shared/researchApi";
import { substantiveFlags } from "../../shared/findings";
import { poseFullLabel } from "../../shared/poseBins";
import { PhotoImage } from "../../shared/ui/PhotoImage";
import styles from "./timeline.module.css";

/**
 * Развёрнутая подсказка кадра (§8.5 ТЗ).
 *
 * Раньше единственной подсказкой был нативный `title=`, который показывает
 * только строку текста, появляется через секунду и не поддерживает действий.
 *
 * Здесь показываются те поля, которые backend действительно вернул.
 * Отсутствующие значения пишутся как «н/д»: подставлять ноль в метрику,
 * которой нет, значит сообщать измерение, которого не делали.
 */

const pct = (v: number | null | undefined) => (v == null ? "н/д" : `${Math.round(v * 100)}%`);
const deg = (v: number | null | undefined) => (v == null ? "н/д" : `${v.toFixed(1)}°`);

export function PhotoTooltip({
  photo,
  x,
  y,
  blind,
  label,
}: {
  photo: ResearchPhoto;
  x: number;
  y: number;
  blind: boolean;
  label: string;
}) {
  const findings = substantiveFlags(photo).slice(0, 3);

  return (
    <div
      className={styles.tooltip}
      style={{ left: x, top: y }}
      role="tooltip"
      // Подсказка не должна перехватывать курсор: иначе она мигает под ним.
      aria-hidden="true"
    >
      <div className={styles.tooltipHead}>
        <PhotoImage
          photoId={photo.id}
          alt=""
          className={styles.tooltipThumb}
          variant="cover"
        />
        <div className={styles.tooltipTitle}>
          <strong>{blind ? label : photo.id}</strong>
          <span>{blind ? "дата скрыта слепым режимом" : (photo.date ?? "дата отсутствует")}</span>
          <span>{poseFullLabel(photo.bucket)}</span>
        </div>
      </div>

      <dl className={styles.tooltipGrid}>
        <div>
          <dt>quality</dt>
          <dd>{pct(photo.quality)}</dd>
        </div>
        <div>
          <dt>yaw</dt>
          <dd>{deg(photo.yaw)}</dd>
        </div>
        <div>
          <dt>pitch</dt>
          <dd>{deg(photo.pitch)}</dd>
        </div>
        <div>
          <dt>roll</dt>
          <dd>{deg(photo.roll)}</dd>
        </div>
        <div>
          <dt>boneScore</dt>
          <dd>{photo.boneScore == null ? "н/д" : photo.boneScore.toFixed(2)}</dd>
        </div>
        <div>
          <dt>provenance</dt>
          <dd>{photo.dateProvenanceStatus ?? "н/д"}</dd>
        </div>
      </dl>

      {findings.length > 0 && (
        <ul className={styles.tooltipFindings}>
          {findings.map((flag) => (
            <li key={flag}>{flag}</li>
          ))}
        </ul>
      )}

      <div className={styles.tooltipHint}>
        Клик — назначить A/B ·{" "}
        {/*
          Ссылка несёт идентификатор кадра: без него инспектор открывался
          пустым, и кадр приходилось искать заново.
        */}
        <Link to="/inspector" search={(prev) => ({ ...prev, photo: photo.id })}>
          инспектор
        </Link>
        {" · "}
        <Link to="/pair-analysis" search={(prev) => ({ ...prev, photo: photo.id })}>
          сравнение
        </Link>
      </div>
    </div>
  );
}
