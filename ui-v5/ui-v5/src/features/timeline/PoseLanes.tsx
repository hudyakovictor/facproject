import { useMemo } from "react";
import type { ResearchPhoto } from "../../shared/researchApi";
import { poseFullLabel } from "../../shared/poseBins";
import { isFinding } from "../../shared/findings";
import { TrackCanvas, type TrackSpec } from "./TrackCanvas";
import { timeToRatio, type Viewport } from "./viewport";
import { pickRepresentatives } from "./representative";
import styles from "./timeline.module.css";

/**
 * Мультиракурсный режим (§8.9 ТЗ).
 *
 * Каждый бин ракурса получает собственную компактную полосу: свои дорожки
 * метрик и свою photo row. Полосы делят один временной вьюпорт, поэтому
 * события в них сопоставимы по горизонтали.
 *
 * Ключевое ограничение, ради которого режим и сделан отдельным компонентом:
 * **нельзя проводить одну линию через разные бины**. Фронтальный кадр и кадр в
 * профиль измерены в разных условиях проекции; соединив их, интерфейс нарисует
 * скачок метрики там, где сменился только ракурс съёмки. Раньше именно это и
 * происходило: включение мультиракурса просто снимало фильтр по бину, и все
 * девять бинов попадали в одну полилинию. Здесь каждый бин рисуется
 * независимо, а сопоставление между бинами остаётся задачей глаза и отметок
 * событий, а не общей кривой.
 *
 * Вертикальная шкала у полос общая (домен считается по всем видимым кадрам) —
 * иначе одинаковая высота точки в разных полосах означала бы разные величины.
 */

const LANE_HEIGHT = 34;
const LANE_THUMB_SLOT = 44;

export interface PoseLanesProps {
  photos: readonly ResearchPhoto[];
  times: Map<string, number>;
  viewport: Viewport;
  tracks: readonly TrackSpec[];
  width: number;
  activePose: string;
  pairA: string | null;
  pairB: string | null;
  selected: string | null;
  dimmed: (photo: ResearchPhoto) => boolean;
  hoverTime: number | null;
  onSelect: (photo: ResearchPhoto) => void;
  labelOf: (photo: ResearchPhoto) => string;
  onFocusPose: (pose: string) => void;
}

export function PoseLanes(props: PoseLanesProps) {
  const lanes = useMemo(() => {
    const byBin = new Map<string, ResearchPhoto[]>();
    for (const photo of props.photos) {
      const key = photo.bucket;
      const list = byBin.get(key);
      if (list) list.push(photo);
      else byBin.set(key, [photo]);
    }
    return [...byBin.entries()]
      .map(([id, items]) => ({
        id,
        label: poseFullLabel(id),
        photos: items,
        findings: items.filter(isFinding).length,
      }))
      .sort((a, b) => b.photos.length - a.photos.length);
  }, [props.photos]);

  if (lanes.length === 0) return null;

  return (
    <div className={styles.lanes}>
      <p className={styles.lanesNote}>
        {lanes.length} ракурсов, общий временной интервал. Линии не соединяются между
        полосами: кадры разных ракурсов сняты в разной проекции, и общая кривая
        показывала бы смену ракурса как изменение метрики.
      </p>

      {lanes.map((lane) => {
        const representatives = pickRepresentatives(lane.photos, props.times, {
          viewport: props.viewport,
          width: props.width,
          slotWidth: LANE_THUMB_SLOT,
          pinned: [props.pairA, props.pairB, props.selected],
        });

        return (
          <section
            key={lane.id}
            className={`${styles.lane} ${lane.id === props.activePose ? styles.laneActive : ""}`}
          >
            <header className={styles.laneHeader}>
              <button
                type="button"
                className={styles.laneTitle}
                onClick={() => props.onFocusPose(lane.id)}
                title="Сделать этот ракурс активным и выйти из мультиракурса"
              >
                {lane.label}
              </button>
              <span className={styles.laneCount}>
                {lane.photos.length} кадр.
                {lane.findings > 0 ? ` · находок ${lane.findings}` : ""}
              </span>
            </header>

            <div className={styles.laneBody}>
              {props.tracks.map((track) => (
                <div key={track.key} className={styles.laneTrack}>
                  <span className={styles.laneTrackLabel} title={track.range}>
                    {track.label}
                  </span>
                  <div className={styles.laneCanvas}>
                    <TrackCanvas
                      track={track}
                      photos={lane.photos}
                      times={props.times}
                      viewport={props.viewport}
                      height={LANE_HEIGHT}
                      dimmed={props.dimmed}
                      hoverTime={props.hoverTime}
                    />
                  </div>
                </div>
              ))}

              <div className={styles.lanePhotoRow}>
                {representatives.map((photo) => {
                  const ratio = timeToRatio(props.viewport, props.times.get(photo.id) ?? 0);
                  return (
                    <button
                      key={photo.id}
                      type="button"
                      className={`${styles.laneThumb} ${
                        photo.id === props.pairA
                          ? styles.laneThumbA
                          : photo.id === props.pairB
                            ? styles.laneThumbB
                            : isFinding(photo)
                              ? styles.laneThumbFinding
                              : ""
                      } ${props.dimmed(photo) ? styles.thumbDimmed : ""}`}
                      style={{ left: `${ratio * 100}%` }}
                      title={props.labelOf(photo)}
                      onClick={() => props.onSelect(photo)}
                    >
                      <span className={styles.laneThumbCaption}>{props.labelOf(photo)}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>
        );
      })}
    </div>
  );
}
