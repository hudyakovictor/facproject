import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { PairMetrics } from "../../shared/api/schemas";
import { formatMetric, groupMetrics } from "./metricGroups";
import styles from "./pair.module.css";

/**
 * Панель метрик пары (§11.6).
 *
 * Показывает все 208 колонок Stage 2, сгруппированные по смыслу. Пропуски
 * видны как «н/д» и посчитаны в заголовке группы: «измерено 12 из 19» — сразу
 * понятно, насколько группа наполнена, и не нужно листать её целиком.
 *
 * 🚨 WARNING: колонки не фильтруются по «интересности». Скрыть неизмеренные
 * значило бы показать пару полнее, чем она есть.
 */
export function MetricsPanel({ data }: { data: PairMetrics }) {
  const [filter, setFilter] = useState("");
  const [onlyMeasured, setOnlyMeasured] = useState(false);
  const groups = useMemo(() => groupMetrics(data), [data]);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return groups
      .map((group) => ({
        ...group,
        rows: group.rows.filter((row) => {
          if (onlyMeasured && row.value === null) return false;
          if (!needle) return true;
          return (
            row.column.toLowerCase().includes(needle) ||
            String(row.value ?? "").toLowerCase().includes(needle)
          );
        }),
      }))
      .filter((group) => group.rows.length > 0);
  }, [groups, filter, onlyMeasured]);

  const shown = visible.reduce((sum, group) => sum + group.rows.length, 0);

  return (
    <section className={styles.panel} aria-label="Метрики пары">
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>МЕТРИКИ ПАРЫ</span>
        <span className={styles.panelMeta}>
          измерено {data.available_count} из {data.column_count} колонок
          {data.reversed_order && " · порядок кадров в Stage 2 обратный"}
        </span>
      </div>

      <label className={styles.metricSearch}>
        <Search className="h-3.5 w-3.5" aria-hidden="true" />
        <input
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Поиск по колонке или значению"
          aria-label="Поиск по метрикам пары"
        />
        <span className={styles.hint}>показано {shown}</span>
      </label>

      <label className={styles.checkboxRow}>
        <input
          type="checkbox"
          checked={onlyMeasured}
          onChange={(event) => setOnlyMeasured(event.target.checked)}
        />
        Только измеренные
        <span className={styles.hint}>
          скрытые пропуски остаются пропусками, а не нулями
        </span>
      </label>

      {visible.length === 0 && <p className={styles.note}>Ничего не найдено.</p>}

      {visible.map((group) => (
        <details key={group.id} className={styles.metricGroup} open={group.id === "primary-landmarks"}>
          <summary className={styles.groupSummary}>
            {group.title} · измерено {group.rows.filter((row) => row.value !== null).length} из{" "}
            {group.rows.length}
          </summary>
          <p className={styles.groupDescription}>{group.description}</p>
          {group.rows.map((row) => (
            <div key={row.column} className={styles.metricRow}>
              <span className={styles.metricName} title={row.tooltip ?? `категория ${row.category} · ${row.group}`}>
                {row.column}
              </span>
              <span className={styles.metricValue} data-null={row.value === null}>
                {formatMetric(row)}
              </span>
              <span className={styles.metricUnit}>{row.unit ?? ""}</span>
            </div>
          ))}
        </details>
      ))}

      <p className={styles.note}>
        Калиброванные пороги, z и q показаны там, где Stage 2 их посчитал. Отдельная
        ссылка на пакет доказательств появится вместе с эндпоинтом каталога метрик
        (задача B-09): подписывать метод по догадке нельзя.
      </p>
    </section>
  );
}
