import { useMemo, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import type { ResearchPhoto } from "../../shared/researchApi";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { histogramOf, isSmallSample, SMALL_N } from "./filters";
import styles from "./timeline.module.css";

/**
 * Меню «Фильтры» (§9.1, §9.4).
 *
 * Всё, что здесь есть, — фильтр вида: он меняет отображение и ничего не
 * пересчитывает. Об этом сказано в самом меню, потому что иначе подкрученный
 * порог легко принять за результат анализа, а снимок экрана с ним — за вывод.
 *
 * Под каждым порогом — распределение величины и последствия среза: сколько
 * кадров останется и сколько уйдёт. Порог без этой картины показывает только
 * то, что осталось, и скрывает цену.
 */

export interface FiltersMenuProps {
  /** Кадры до применения порогов — на них строится распределение. */
  photos: readonly ResearchPhoto[];
}

function Histogram({
  photos,
  threshold,
}: {
  photos: readonly ResearchPhoto[];
  threshold: number;
}) {
  const data = useMemo(
    () =>
      histogramOf(photos, (photo) => photo.quality ?? null, {
        min: 0,
        max: 1,
        bins: 20,
        threshold,
      }),
    [photos, threshold],
  );

  const peak = Math.max(...data.bins.map((bin) => bin.total), 1);

  return (
    <div>
      <div className={styles.histogram} aria-hidden="true">
        {data.bins.map((bin) => (
          <span
            key={bin.from}
            className={bin.from + 1e-9 >= threshold ? styles.histBarKept : styles.histBarCut}
            style={{ height: `${(bin.total / peak) * 100}%` }}
            title={`${bin.from.toFixed(2)}–${bin.to.toFixed(2)}: ${bin.total}`}
          />
        ))}
      </div>
      <p className={styles.menuNote}>
        Останется {data.kept}, уйдёт {data.dropped}
        {data.withoutValue > 0
          ? ` · без оценки качества ${data.withoutValue} (порогом не отбрасываются: отсутствие оценки — не ноль)`
          : ""}
        .
      </p>
      {isSmallSample(data.kept) ? (
        <p className={styles.menuWarn} role="alert">
          После среза остаётся меньше {SMALL_N} кадров — на такой выборке разброс не
          оценивается.
        </p>
      ) : null}
    </div>
  );
}

export function FiltersMenu({ photos }: FiltersMenuProps) {
  const [open, setOpen] = useState(false);
  const {
    qualityThreshold,
    setQualityThreshold,
    poseAngleThreshold,
    setPoseAngleThreshold,
    mouthThreshold,
    setMouthThreshold,
  } = useAnalysisStore();

  const dirty =
    qualityThreshold !== 0 || poseAngleThreshold !== 6 || mouthThreshold !== 0.35;

  return (
    <div className={styles.menuRoot}>
      <button
        type="button"
        className={styles.menuTrigger}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <SlidersHorizontal className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
        Фильтры{dirty ? " · изменены" : ""}
      </button>

      {open ? (
        <div className={styles.menuPanel} role="group" aria-label="Фильтры вида">
          <p className={styles.menuViewOnly}>
            только вид · не пересчитывает анализ и не меняет выборку прогона
          </p>

          <label className={styles.filterRow}>
            <span className={styles.filterName}>
              Порог качества
              <span className={styles.menuUnit}> · {qualityThreshold.toFixed(2)}</span>
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={qualityThreshold}
              onChange={(event) => setQualityThreshold(Number(event.target.value))}
            />
          </label>
          <Histogram photos={photos} threshold={qualityThreshold} />

          <label className={styles.filterRow}>
            <span className={styles.filterName}>
              Допуск угла позы
              <span className={styles.menuUnit}> · ±{poseAngleThreshold}°</span>
            </span>
            <input
              type="range"
              min={0}
              max={30}
              step={1}
              value={poseAngleThreshold}
              onChange={(event) => setPoseAngleThreshold(Number(event.target.value))}
            />
          </label>

          <label className={styles.filterRow}>
            <span className={styles.filterName}>
              Порог активности рта
              <span className={styles.menuUnit}> · {mouthThreshold.toFixed(2)}</span>
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={mouthThreshold}
              onChange={(event) => setMouthThreshold(Number(event.target.value))}
            />
          </label>

          <button
            type="button"
            className={styles.menuAction}
            disabled={!dirty}
            onClick={() => {
              setQualityThreshold(0);
              setPoseAngleThreshold(6);
              setMouthThreshold(0.35);
            }}
          >
            Сбросить пороги
          </button>

          <p className={styles.menuFootnote}>
            Профили анализа с версионированием и манифестом выборки — отдельная
            сущность (§9.6): фильтр вида их не заменяет и прогон не запускает.
          </p>
        </div>
      ) : null}
    </div>
  );
}
