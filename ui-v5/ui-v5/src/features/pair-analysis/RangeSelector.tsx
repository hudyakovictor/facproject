import { useMemo } from "react";
import styles from "./pair.module.css";

/**
 * Выбор диапазона дат (§11.2).
 *
 * Два ползунка по индексу года, пресеты эпох и счётчик кадров в диапазоне.
 * Ползунки работают по индексу, а не по timestamp: шаг «один год» понятен, а
 * перетаскивание по миллисекундам эпохи — нет.
 *
 * 🚨 WARNING: счётчик показывает, сколько кадров осталось после сужения. Это
 * важнее самих границ: диапазон, в котором остался один кадр, делает любое
 * сравнение бессмысленным, и пользователь должен видеть это до того, как
 * начнёт читать метрики.
 */

export interface RangeValue {
  from: number;
  to: number;
}

const ERA_PRESETS: ReadonlyArray<{ id: string; label: string; from: number; to: number }> = [
  { id: "all", label: "Весь архив", from: 0, to: 9999 },
  { id: "early", label: "1999–2007", from: 1999, to: 2007 },
  { id: "middle", label: "2008–2015", from: 2008, to: 2015 },
  { id: "late", label: "2016–2026", from: 2016, to: 2026 },
];

export function RangeSelector({
  years,
  value,
  onChange,
  countInRange,
  totalCount,
  onlyCurrentPose,
  onToggleOnlyCurrentPose,
  poseLabelText,
}: {
  years: number[];
  value: RangeValue;
  onChange: (next: RangeValue) => void;
  countInRange: number;
  totalCount: number;
  onlyCurrentPose: boolean;
  onToggleOnlyCurrentPose: (next: boolean) => void;
  poseLabelText: string;
}) {
  const min = years[0] ?? 1999;
  const max = years[years.length - 1] ?? 2026;

  const presets = useMemo(
    () =>
      ERA_PRESETS.map((preset) => ({
        ...preset,
        from: Math.max(min, preset.from),
        to: Math.min(max, preset.to),
      })).filter((preset) => preset.from <= preset.to),
    [min, max],
  );

  return (
    <section className={styles.panel} aria-label="Диапазон дат">
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>ДИАПАЗОН</span>
        <span className={styles.panelMeta}>
          в диапазоне {countInRange.toLocaleString("ru-RU")} из {totalCount.toLocaleString("ru-RU")}
          {countInRange < 2 && " · для пары нужно минимум два кадра"}
        </span>
      </div>

      <div className={styles.rangeRow}>
        <label className={styles.rangeField}>
          С
          <input
            type="range"
            min={min}
            max={max}
            value={value.from}
            onChange={(event) => {
              const from = Number(event.target.value);
              onChange({ from, to: Math.max(from, value.to) });
            }}
            aria-label="Начало диапазона"
          />
          <span className={styles.sliderValue}>{value.from}</span>
        </label>
        <label className={styles.rangeField}>
          По
          <input
            type="range"
            min={min}
            max={max}
            value={value.to}
            onChange={(event) => {
              const to = Number(event.target.value);
              onChange({ from: Math.min(to, value.from), to });
            }}
            aria-label="Конец диапазона"
          />
          <span className={styles.sliderValue}>{value.to}</span>
        </label>
      </div>

      <div className={styles.modeBar} role="group" aria-label="Пресеты периода">
        {presets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={styles.modeButton}
            aria-pressed={value.from === preset.from && value.to === preset.to}
            onClick={() => onChange({ from: preset.from, to: preset.to })}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <label className={styles.checkboxRow}>
        <input
          type="checkbox"
          checked={onlyCurrentPose}
          onChange={(event) => onToggleOnlyCurrentPose(event.target.checked)}
        />
        Только текущий ракурс ({poseLabelText})
        <span className={styles.hint}>
          Сравнивать геометрию можно лишь внутри одного бина, поэтому кадры других
          ракурсов в паре всё равно недопустимы.
        </span>
      </label>
    </section>
  );
}
