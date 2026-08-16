import { useMemo, useState } from "react";
import {
  METRIC_CATALOG,
  METRIC_GROUPS,
  METRIC_GROUP_LABELS,
  availabilityOf,
  type MetricDescriptor,
  type MetricGroup,
} from "../../shared/metrics";
import { METRIC_COLORS } from "../../shared/ui/tokenColors";
import type { ResearchPhoto } from "../../shared/researchApi";
import styles from "./timeline.module.css";

/**
 * Меню «Метрики» (§8.1 ТЗ).
 *
 * Для каждой величины показываются единица измерения, система координат,
 * статус (калиброванная / диагностическая) и число кадров, где значение
 * действительно есть. Последнее важнее остального: дорожка, построенная по
 * четырём кадрам из тысячи, выглядит на экране так же уверенно, как дорожка по
 * всем — отличить их можно только по этому счётчику.
 *
 * Порядок дорожек меняется кнопками, а не перетаскиванием мышью: HTML5 drag
 * недоступен с клавиатуры, а порядок дорожек — часть рабочего состояния, а не
 * украшение.
 */

export interface MetricsMenuProps {
  photos: readonly ResearchPhoto[];
  visible: readonly string[];
  onChange: (next: string[]) => void;
}

export function MetricsMenu({ photos, visible, onChange }: MetricsMenuProps) {
  const [open, setOpen] = useState(false);

  const availability = useMemo(() => {
    const map = new Map<string, number>();
    for (const metric of METRIC_CATALOG) {
      map.set(metric.id, availabilityOf(metric, photos));
    }
    return map;
  }, [photos]);

  const byGroup = useMemo(() => {
    const map = new Map<MetricGroup, MetricDescriptor[]>();
    for (const group of METRIC_GROUPS) map.set(group, []);
    for (const metric of METRIC_CATALOG) map.get(metric.group)?.push(metric);
    return map;
  }, []);

  const toggle = (id: string) => {
    onChange(visible.includes(id) ? visible.filter((item) => item !== id) : [...visible, id]);
  };

  /** Solo: оставить одну дорожку. Повторное нажатие возвращает прежний набор. */
  const [beforeSolo, setBeforeSolo] = useState<string[] | null>(null);
  const solo = (id: string) => {
    if (visible.length === 1 && visible[0] === id && beforeSolo) {
      onChange(beforeSolo);
      setBeforeSolo(null);
      return;
    }
    setBeforeSolo([...visible]);
    onChange([id]);
  };

  const move = (id: string, delta: number) => {
    const index = visible.indexOf(id);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= visible.length) return;
    const next = [...visible];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  return (
    <div className={styles.menuRoot}>
      <button
        type="button"
        className={styles.menuTrigger}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        Метрики · {visible.length}
      </button>

      {open ? (
        <div className={styles.menuPanel} role="group" aria-label="Выбор метрик">
          <p className={styles.menuNote}>
            Единицы и системы координат описаны в интерфейсе: каталог метрик backend не
            присылает. Счётчик показывает, у скольких кадров из {photos.length} значение есть.
          </p>

          {METRIC_GROUPS.map((group) => {
            const metrics = byGroup.get(group) ?? [];
            if (metrics.length === 0) return null;
            return (
              <section key={group} className={styles.menuGroup}>
                <h4 className={styles.menuGroupTitle}>{METRIC_GROUP_LABELS[group]}</h4>
                {metrics.map((metric) => {
                  const count = availability.get(metric.id) ?? 0;
                  const checked = visible.includes(metric.id);
                  const order = visible.indexOf(metric.id);
                  return (
                    <div key={metric.id} className={styles.menuRow}>
                      <label className={styles.menuLabel}>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={count === 0}
                          onChange={() => toggle(metric.id)}
                        />
                        <span
                          className={styles.menuSwatch}
                          style={{
                            background: METRIC_COLORS[metric.id] ?? "var(--text-muted)",
                          }}
                          aria-hidden="true"
                        />
                        <span className={styles.menuName}>
                          {metric.label}
                          {metric.unit ? (
                            <span className={styles.menuUnit}> · {metric.unit}</span>
                          ) : null}
                        </span>
                      </label>

                      <span
                        className={
                          metric.status === "calibrated"
                            ? styles.menuBadgeCalibrated
                            : styles.menuBadgeDiagnostic
                        }
                        title={
                          metric.status === "calibrated"
                            ? "Приведена к базовой линии калибровки, сопоставима между кадрами"
                            : "Сырой признак: годится, чтобы заметить аномалию, но не для вывода о тождестве"
                        }
                      >
                        {metric.status === "calibrated" ? "калибр." : "диагн."}
                      </span>

                      <span
                        className={count === 0 ? styles.menuCountEmpty : styles.menuCount}
                        title={`${metric.space}`}
                      >
                        {`${count}/${photos.length}`}
                      </span>

                      {checked ? (
                        <span className={styles.menuOrder}>
                          <button
                            type="button"
                            aria-label={`Поднять дорожку ${metric.label}`}
                            disabled={order <= 0}
                            onClick={() => move(metric.id, -1)}
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            aria-label={`Опустить дорожку ${metric.label}`}
                            disabled={order < 0 || order >= visible.length - 1}
                            onClick={() => move(metric.id, 1)}
                          >
                            ↓
                          </button>
                        </span>
                      ) : null}

                      <button
                        type="button"
                        className={styles.menuSolo}
                        disabled={count === 0}
                        aria-label={`Показать только ${metric.label}`}
                        onClick={() => solo(metric.id)}
                      >
                        solo
                      </button>
                    </div>
                  );
                })}
              </section>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
