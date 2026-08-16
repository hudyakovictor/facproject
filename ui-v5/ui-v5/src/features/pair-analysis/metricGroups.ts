/**
 * Панель метрик пары (§11.6) и A-relative подсветка (§11.3).
 *
 * Stage 2 отдаёт 208 колонок, разложенных по категориям A–I
 * (`key_catalog.categorize_pair_columns`). Спека просит семь пользовательских
 * групп — «первичные точки», «только идентичность», «меш», «локальные
 * дескрипторы», «хронология», «диагностика текстуры», «качество и провенанс».
 * Это не то же самое, что категории backend: одна группа собирается из
 * нескольких категорий.
 *
 * 🚨 WARNING: соответствие задаётся явной таблицей, а не эвристикой по имени.
 * Эвристика ошибётся тихо — колонка уедет не в ту группу и будет прочитана как
 * другая величина. Колонка, не попавшая ни в одну группу, не исчезает: она
 * уходит в «прочее», чтобы новая колонка Stage 2 стала видна, а не пропала.
 */

import type { MetricValue, PairMetrics } from "../../shared/api/schemas";

export interface MetricRow {
  column: string;
  value: MetricValue;
  /** Категория backend — показывается как происхождение значения. */
  category: string;
  group: string;
  unit: string | null;
  /** Пояснение метода: чем измерено и что означает. */
  tooltip: string | null;
}

export interface MetricGroup {
  id: string;
  title: string;
  description: string;
  rows: MetricRow[];
  /** Сколько колонок группы реально имеют значение. */
  measured: number;
}

/** Порядок групп по §11.6. */
const GROUP_DEFS: ReadonlyArray<{
  id: string;
  title: string;
  description: string;
  /** Категория backend → подгруппы, попадающие в эту группу. `*` — все. */
  sources: Record<string, string[] | "*">;
}> = [
  {
    id: "primary-landmarks",
    title: "Первичные точки",
    description:
      "Расхождение по анатомическим точкам после выравнивания. Основная измеряемая величина пары.",
    sources: { A: ["primary", "header"], D: ["anchors", "alignment", "coverage", "residual_transform"] },
  },
  {
    id: "identity-only",
    title: "Только идентичность",
    description:
      "Величины, из которых вычтена мимика: сравнивается форма, а не выражение лица.",
    sources: { F: ["identity_vs_expression"] },
  },
  {
    id: "mesh",
    title: "Меш",
    description:
      "Сравнение полной поверхности, а не отдельных точек. Отдельный измерительный канал.",
    sources: { B: "*" },
  },
  {
    id: "descriptors",
    title: "Локальные дескрипторы",
    description: "Движение отдельных точек и их семейств, без агрегирования в одно число.",
    sources: { D: ["descriptors", "point_motion", "artifact"] },
  },
  {
    id: "chronology",
    title: "Хронология",
    description: "Скорость изменения во времени и ведущие области.",
    sources: { F: ["rate", "leads", "date"] },
  },
  {
    id: "texture",
    title: "Диагностика текстуры",
    description:
      "Диагностика поверхности кожи. Служит проверкой условий, а не мерой сходства лиц.",
    sources: { E: "*" },
  },
  {
    id: "quality-provenance",
    title: "Качество и провенанс",
    description: "Условия съёмки и происхождение кадров — контекст, в котором получены числа.",
    sources: { C: "*", G: "*" },
  },
  {
    id: "significance",
    title: "Статистическая значимость",
    description:
      "Поправка на множественные сравнения и подтверждение по другим ракурсам. Без неё отдельное большое значение ничего не доказывает.",
    sources: { A: ["multiple_testing", "corroboration", "limits"] },
  },
];

/** Единицы и пояснения для колонок, где они не очевидны из имени. */
const COLUMN_HINTS: Record<string, { unit?: string; tooltip: string }> = {
  ldm106_rmse: { tooltip: "Среднеквадратичное расхождение 106 точек после выравнивания, в нормированных единицах." },
  ldm134_rmse: { tooltip: "Среднеквадратичное расхождение 134 точек после выравнивания." },
  ldm134_p95: { tooltip: "95-й процентиль расхождения: устойчив к отдельным выбросам." },
  identity_only_ldm134_rmse: {
    tooltip: "То же расхождение, но по identity-компоненте: вклад мимики вычтен.",
  },
  alpha_id_l2: { tooltip: "Норма разности identity-коэффициентов модели формы." },
  alpha_exp_l2: { tooltip: "Норма разности коэффициентов выражения: насколько различается мимика." },
  primary_robust_z: {
    tooltip: "Робастный z основной метрики относительно калибровочного распределения.",
  },
  primary_calibration_p95: {
    tooltip: "95-й процентиль калибровки: типичный разброс между кадрами одного лица.",
  },
  mt_q_value: { tooltip: "q-значение после поправки FDR на число сравнений." },
  mt_p_approx: { tooltip: "Приближённое p-значение до поправки." },
  mesh_rmse: { tooltip: "Расхождение поверхностей точка-к-точке." },
  mesh_point_to_plane_rmse: {
    tooltip: "Расхождение точка-к-плоскости: устойчивее к скольжению вдоль поверхности.",
  },
  coverage106: { unit: "доля", tooltip: "Доля из 106 точек, видимых на обоих кадрах." },
  coverage134: { unit: "доля", tooltip: "Доля из 134 точек, видимых на обоих кадрах." },
  pose_distance: { tooltip: "Суммарное расстояние между позами кадров." },
  expression_influence: { tooltip: "Оценка вклада мимики в наблюдаемое расхождение." },
};

/**
 * Колонки, которые backend не разложил по категориям и оставил в `I/other`
 * (23 штуки на реальной паре): пороги видимости, разрывы углов, признаки
 * мимики. Смысл у них есть, поэтому они распределяются по группам явным
 * списком, а не остаются в куче «прочее».
 *
 * Правка тут не заменяет исправления `key_catalog.py` на backend — она лишь
 * не даёт значимым колонкам выглядеть мусором в интерфейсе.
 */
const COLUMN_TO_GROUP: Record<string, string> = {
  visibility_gate_accepted106: "primary-landmarks",
  visibility_gate_accepted134: "primary-landmarks",
  visibility_gate_common106: "primary-landmarks",
  visibility_gate_common134: "primary-landmarks",
  visibility_gate_required106: "primary-landmarks",
  visibility_gate_required134: "primary-landmarks",
  calibrated_point_count: "primary-landmarks",
  yaw_gap_deg: "primary-landmarks",
  pitch_gap_deg: "primary-landmarks",
  roll_gap_deg: "primary-landmarks",
  pose_gap_reason: "primary-landmarks",
  corner_lift_ioc_a: "quality-provenance",
  corner_lift_ioc_b: "quality-provenance",
  jaw_open_ratio_a: "quality-provenance",
  jaw_open_ratio_b: "quality-provenance",
  jaw_open_detected_a: "quality-provenance",
  jaw_open_detected_b: "quality-provenance",
  smile_detected_a: "quality-provenance",
  smile_detected_b: "quality-provenance",
  qc_skip_reason: "quality-provenance",
  date_conflict_sources_a: "quality-provenance",
  date_conflict_sources_b: "quality-provenance",
  archive_url_b: "quality-provenance",
  archive_url_a: "quality-provenance",
  source_url_a: "quality-provenance",
  source_url_b: "quality-provenance",
};

const UNIT_BY_SUFFIX: ReadonlyArray<readonly [string, string]> = [
  ["_deg", "°"],
  ["_days", "дней"],
  ["_count", "шт."],
  ["_fraction", "доля"],
];

function unitFor(column: string): string | null {
  const explicit = COLUMN_HINTS[column]?.unit;
  if (explicit) return explicit;
  for (const [suffix, unit] of UNIT_BY_SUFFIX) {
    if (column.endsWith(suffix)) return unit;
  }
  return null;
}

/** Разложение метрик пары по группам §11.6. */
export function groupMetrics(data: PairMetrics): MetricGroup[] {
  const used = new Set<string>();
  const groups: MetricGroup[] = [];

  /** Колонки, приписанные к группе поимённо, независимо от категории backend. */
  const byExplicitGroup = new Map<string, MetricRow[]>();
  for (const [category, subgroups] of Object.entries(data.categories)) {
    for (const [subgroup, columns] of Object.entries(subgroups)) {
      for (const [column, value] of Object.entries(columns)) {
        const target = COLUMN_TO_GROUP[column];
        if (!target) continue;
        const row: MetricRow = {
          column,
          value,
          category,
          group: subgroup,
          unit: unitFor(column),
          tooltip: COLUMN_HINTS[column]?.tooltip ?? null,
        };
        const bucket = byExplicitGroup.get(target);
        if (bucket) bucket.push(row);
        else byExplicitGroup.set(target, [row]);
        used.add(column);
      }
    }
  }

  for (const def of GROUP_DEFS) {
    const rows: MetricRow[] = [...(byExplicitGroup.get(def.id) ?? [])];
    for (const [category, subgroups] of Object.entries(def.sources)) {
      const categoryData = data.categories[category];
      if (!categoryData) continue;
      const names = subgroups === "*" ? Object.keys(categoryData) : subgroups;
      for (const subgroup of names) {
        const columns = categoryData[subgroup];
        if (!columns) continue;
        for (const [column, value] of Object.entries(columns)) {
          if (used.has(column)) continue;
          used.add(column);
          rows.push({
            column,
            value,
            category,
            group: subgroup,
            unit: unitFor(column),
            tooltip: COLUMN_HINTS[column]?.tooltip ?? null,
          });
        }
      }
    }
    if (rows.length === 0) continue;
    rows.sort((a, b) => a.column.localeCompare(b.column));
    groups.push({
      id: def.id,
      title: def.title,
      description: def.description,
      rows,
      measured: rows.filter((row) => row.value !== null).length,
    });
  }

  // Колонки, не попавшие ни в одну группу, показываются отдельно, а не теряются.
  const leftovers: MetricRow[] = [];
  for (const [category, subgroups] of Object.entries(data.categories)) {
    for (const [subgroup, columns] of Object.entries(subgroups)) {
      for (const [column, value] of Object.entries(columns)) {
        if (used.has(column)) continue;
        used.add(column);
        leftovers.push({
          column,
          value,
          category,
          group: subgroup,
          unit: unitFor(column),
          tooltip: COLUMN_HINTS[column]?.tooltip ?? null,
        });
      }
    }
  }
  if (leftovers.length > 0) {
    leftovers.sort((a, b) => a.column.localeCompare(b.column));
    groups.push({
      id: "other",
      title: "Прочие колонки прогона",
      description:
        "Колонки, для которых интерфейс не задал группу. Показаны как есть, чтобы новая колонка Stage 2 не исчезла молча.",
      rows: leftovers,
      measured: leftovers.filter((row) => row.value !== null).length,
    });
  }

  return groups;
}

/** Отображение значения метрики. Пропуск остаётся пропуском. */
export function formatMetric(row: MetricRow): string {
  if (row.value === null) return "н/д";
  if (typeof row.value === "boolean") return row.value ? "да" : "нет";
  if (typeof row.value === "number") {
    if (Number.isInteger(row.value)) return String(row.value);
    const abs = Math.abs(row.value);
    if (abs !== 0 && (abs < 0.001 || abs >= 1e6)) return row.value.toExponential(2);
    return row.value.toFixed(4);
  }
  return row.value;
}

// ---------------------------------------------------------------------------
// A-relative подсветка (§11.3)
// ---------------------------------------------------------------------------

export type TintLevel = "near" | "moderate" | "far" | "unknown" | "inapplicable";

export const TINT_LABELS: Record<TintLevel, string> = {
  near: "малое расхождение",
  moderate: "среднее расхождение",
  far: "большое расхождение",
  unknown: "не измерено",
  inapplicable: "неприменимо",
};

/**
 * Уровень подсветки миниатюры относительно выбранного кадра A.
 *
 * 🚨 WARNING: спека прямо запрещает называть это вероятностью совпадения
 * личности. Величина — расхождение выбранной метрики относительно
 * калибровочного порога, и подписи обязаны говорить именно это. Уровень
 * дублируется числом и текстом, а не только цветом (§11.3 и требование
 * доступности: различение цветом одним каналом недопустимо).
 */
export function tintLevel(
  value: number | null,
  threshold: number | null,
  applicable: boolean,
): TintLevel {
  if (!applicable) return "inapplicable";
  if (value === null) return "unknown";
  if (threshold === null || threshold <= 0) return "unknown";
  const ratio = value / threshold;
  if (ratio <= 1) return "near";
  if (ratio <= 3) return "moderate";
  return "far";
}
