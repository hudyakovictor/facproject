import type { HeatmapPoint } from "./api";

/** Класс смещения одной ключевой точки. */
export type ShiftClass = "within" | "suspect" | "anomalous" | "no_data";

/** Пороги классификации смещения. Приходят из настроек и настраиваются
 * пользователем — единой «правильной» границы не существует: допустимый
 * разброс зависит от ракурса, качества съёмки и должен уточняться по
 * калибровочному набору. */
export interface ShiftThresholds {
  /** ≤ tolerance — в пределах внутрисубъектной изменчивости. */
  tolerance: number;
  /** tolerance..suspect — заметное смещение. Выше — аномальное. */
  suspect: number;
  /** Подтверждены ли пороги калибровкой. */
  calibrated: boolean;
}

export const DEFAULT_SHIFT_THRESHOLDS: ShiftThresholds = {
  tolerance: 0.02, suspect: 0.05, calibrated: false,
};

export const SHIFT_COLOR: Record<ShiftClass, string> = {
  within: "#6daa45",     // зелёный — в пределах допустимого
  suspect: "#e8af34",    // жёлтый — среднее смещение
  anomalous: "#ff3b30",  // красный — аномальное
  no_data: "#4a4a52",    // серый — точка не видна на одном из кадров
};

export const SHIFT_LABEL_KEY: Record<ShiftClass, string> = {
  within: "shiftWithin", suspect: "shiftSuspect",
  anomalous: "shiftAnomalous", no_data: "shiftNoData",
};

/** 🎯 Классифицировать смещение точки.
 *
 * `null` residual (точка не видна на одном из кадров) → `no_data`, а НЕ
 * `within`: отсутствие измерения нельзя показывать как «совпало»
 * (`app6/AGENTS.md`).
 */
export function classifyShift(
  residual: number | null | undefined, thresholds: ShiftThresholds,
): ShiftClass {
  if (residual === null || residual === undefined || !Number.isFinite(residual)) return "no_data";
  if (residual <= thresholds.tolerance) return "within";
  if (residual <= thresholds.suspect) return "suspect";
  return "anomalous";
}

export interface LandmarkRow {
  index: number;
  visible: boolean;
  residual: number | null;
  zone: string | null;
  /** Позиция в A и выровненная позиция B — для морфинга. */
  a: [number, number, number] | null;
  b: [number, number, number] | null;
  /** Знаковое смещение по осям. */
  delta: [number, number, number] | null;
  shiftClass: ShiftClass;
}

/** Привести ответ `/api/v1/compare` к строкам таблицы точек. */
export function toLandmarkRows(
  points: HeatmapPoint[], thresholds: ShiftThresholds,
): LandmarkRow[] {
  return points.map(p => ({
    index: p.index,
    visible: p.visible !== false,
    residual: p.residual ?? null,
    zone: p.zone ?? null,
    a: p.x === null || p.x === undefined ? null : [p.x, p.y as number, p.z as number],
    b: p.bx === null || p.bx === undefined ? null : [p.bx, p.by as number, p.bz as number],
    delta: p.dx === null || p.dx === undefined ? null : [p.dx, p.dy as number, p.dz as number],
    shiftClass: classifyShift(p.residual, thresholds),
  }));
}

/** Позиция точки при морфинге A→B: линейная интерполяция между исходной
 * позицией и позицией B, выровненной по Kabsch в систему координат A. */
export function morphPosition(
  row: LandmarkRow, t: number,
): [number, number, number] | null {
  if (!row.a) return null;
  if (!row.b) return row.a;
  const k = Math.min(1, Math.max(0, t));
  return [
    row.a[0] + (row.b[0] - row.a[0]) * k,
    row.a[1] + (row.b[1] - row.a[1]) * k,
    row.a[2] + (row.b[2] - row.a[2]) * k,
  ];
}

export interface ShiftSummary {
  within: number; suspect: number; anomalous: number; no_data: number;
  total: number;
  /** Доля аномальных среди ИЗМЕРЕННЫХ точек (не среди всех). */
  anomalousShare: number | null;
  maxResidual: number | null;
  medianResidual: number | null;
}

/** Сводка по классам смещения. */
export function summarizeShifts(rows: LandmarkRow[]): ShiftSummary {
  const counts = { within: 0, suspect: 0, anomalous: 0, no_data: 0 };
  const measured: number[] = [];
  for (const row of rows) {
    counts[row.shiftClass] += 1;
    if (row.residual !== null && Number.isFinite(row.residual)) measured.push(row.residual);
  }
  measured.sort((a, b) => a - b);
  const mid = Math.floor(measured.length / 2);
  return {
    ...counts,
    total: rows.length,
    // Доля считается от измеренных: включать в знаменатель невидимые точки
    // означало бы занижать выраженность расхождения.
    anomalousShare: measured.length ? counts.anomalous / measured.length : null,
    maxResidual: measured.length ? measured[measured.length - 1] : null,
    medianResidual: measured.length
      ? (measured.length % 2 === 0 ? (measured[mid - 1] + measured[mid]) / 2 : measured[mid])
      : null,
  };
}

/** Сводка по координатным зонам: где сосредоточены аномальные точки. */
export function summarizeByZone(rows: LandmarkRow[]): {
  zone: string; total: number; anomalous: number; medianResidual: number | null;
}[] {
  const groups = new Map<string, LandmarkRow[]>();
  for (const row of rows) {
    const key = row.zone ?? "—";
    const list = groups.get(key);
    if (list) list.push(row); else groups.set(key, [row]);
  }
  return [...groups.entries()]
    .map(([zone, list]) => {
      const measured = list
        .map(r => r.residual)
        .filter((v): v is number => v !== null && Number.isFinite(v))
        .sort((a, b) => a - b);
      const mid = Math.floor(measured.length / 2);
      return {
        zone,
        total: list.length,
        anomalous: list.filter(r => r.shiftClass === "anomalous").length,
        medianResidual: measured.length
          ? (measured.length % 2 === 0 ? (measured[mid - 1] + measured[mid]) / 2 : measured[mid])
          : null,
      };
    })
    .sort((a, b) => b.anomalous - a.anomalous || (b.medianResidual ?? 0) - (a.medianResidual ?? 0));
}
