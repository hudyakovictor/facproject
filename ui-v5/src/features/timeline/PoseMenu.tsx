import { useMemo, useState } from "react";
import { POSE_BINS, poseFullLabel } from "../../shared/poseBins";
import type { ResearchPhoto } from "../../shared/researchApi";
import styles from "./timeline.module.css";

/**
 * Меню «Ракурс» (§8.1 ТЗ).
 *
 * Для каждого из девяти бинов показываются число кадров, медианное качество и
 * поддержка калибровки. Бин, в котором мало кадров или нет калиброванных
 * величин, помечается как ограниченный: сравнение внутри него формально
 * возможно, но опирается на слишком узкую выборку, и об этом нужно сказать до
 * того, как пользователь построит на нём вывод.
 *
 * Мультиракурс включается отдельным переключателем и не является режимом по
 * умолчанию — инвариант 1 требует, чтобы обычная работа шла внутри одного бина.
 */

const LIMITED_THRESHOLD = 5;

export interface PoseMenuProps {
  photos: readonly ResearchPhoto[];
  activePose: string;
  onSelect: (pose: string) => void;
  multiPose: boolean;
  onMultiPose: (value: boolean) => void;
}

interface BinStat {
  id: string;
  label: string;
  count: number;
  medianQuality: number | null;
  calibrated: number;
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

export function PoseMenu({
  photos,
  activePose,
  onSelect,
  multiPose,
  onMultiPose,
}: PoseMenuProps) {
  const [open, setOpen] = useState(false);

  const stats = useMemo<BinStat[]>(() => {
    return POSE_BINS.map((bin) => {
      const inBin = photos.filter((photo) => photo.bucket === bin.id);
      // Ноль — законная оценка качества, поэтому фильтруется только отсутствие.
      const qualities = inBin
        .map((photo) => photo.quality)
        .filter((value): value is number => typeof value === "number");
      const calibrated = inBin.filter(
        (photo) => typeof photo.zOrbitDepth === "number" || typeof photo.zJawWidth === "number",
      ).length;
      return {
        id: bin.id,
        label: poseFullLabel(bin.id),
        count: inBin.length,
        medianQuality: median(qualities),
        calibrated,
      };
    });
  }, [photos]);

  const active = stats.find((stat) => stat.id === activePose);

  return (
    <div className={styles.menuRoot}>
      <button
        type="button"
        className={styles.menuTrigger}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        Ракурс · {active ? active.label : activePose}
      </button>

      {open ? (
        <div className={styles.menuPanel} role="group" aria-label="Выбор ракурса">
          <label className={styles.menuMultiRow}>
            <input
              type="checkbox"
              checked={multiPose}
              onChange={(event) => onMultiPose(event.target.checked)}
            />
            <span>
              Мультиракурс
              <span className={styles.menuUnit}> · сравнение бинов рядом, не одной линией</span>
            </span>
          </label>

          <table className={styles.poseTable}>
            <thead>
              <tr>
                <th scope="col">Бин</th>
                <th scope="col">Кадров</th>
                <th scope="col">Медиана качества</th>
                <th scope="col">Калибровка</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((stat) => {
                const limited = stat.count > 0 && stat.count < LIMITED_THRESHOLD;
                return (
                  <tr
                    key={stat.id}
                    className={stat.id === activePose ? styles.poseRowActive : undefined}
                  >
                    <th scope="row">
                      <button
                        type="button"
                        className={styles.poseSelect}
                        disabled={stat.count === 0}
                        aria-current={stat.id === activePose}
                        onClick={() => {
                          onSelect(stat.id);
                          setOpen(false);
                        }}
                      >
                        {stat.label}
                      </button>
                      {limited ? (
                        <span
                          className={styles.menuBadgeLimited}
                          title={`В бине ${stat.count} кадров — выборка слишком мала для устойчивого сравнения`}
                        >
                          ограничен
                        </span>
                      ) : null}
                    </th>
                    <td>{stat.count}</td>
                    <td>
                      {stat.medianQuality === null
                        ? "н/д"
                        : stat.medianQuality.toFixed(2)}
                    </td>
                    <td>
                      {stat.calibrated === 0 ? (
                        <span className={styles.menuCountEmpty}>нет</span>
                      ) : (
                        `${stat.calibrated} из ${stat.count}`
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
