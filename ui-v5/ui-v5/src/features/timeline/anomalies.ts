import type { ResearchPhoto, ResearchTimeline } from "../../shared/researchApi";

/**
 * Зафиксированные аномалии — уже посчитанные Stage 2 сущности.
 * Не пересчитываются в интерфейсе. Одна аномалия живёт на дате/границе,
 * а не как дополнительная фотография.
 */

export type AnomalyKind =
  | "change_point"
  | "persistent_change"
  | "return"
  | "rapid_rate"
  | "same_day"
  | "provenance"
  | "review";

export interface AnomalyEvent {
  id: string;
  kind: AnomalyKind;
  label: string;
  /** epoch ms; null — только годовая метка из манифеста. */
  time: number | null;
  year?: number;
  photoId?: string;
}

const KIND_LABEL: Record<AnomalyKind, string> = {
  change_point: "точка перелома",
  persistent_change: "устойчивое изменение",
  return: "возврат к базе",
  rapid_rate: "аномальный темп",
  same_day: "конфликт одного дня",
  provenance: "конфликт датировки",
  review: "нужна проверка",
};

function yearToTime(year: number): number {
  return Date.UTC(year, 6, 1);
}

function yearsOf(payload: unknown): number[] {
  if (!payload || typeof payload !== "object") return [];
  const years = (payload as { years?: unknown }).years;
  if (!Array.isArray(years)) return [];
  return years
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value));
}

/** Собрать события из ответа /timeline: манифест + флаги кадров. */
export function collectAnomalies(
  timeline: ResearchTimeline | undefined,
  photos: readonly ResearchPhoto[],
  times: ReadonlyMap<string, number>,
): AnomalyEvent[] {
  const events: AnomalyEvent[] = [];
  const anomalies = timeline?.chronology_anomalies ?? {};
  const manifest = timeline?.analysis_manifest ?? {};

  const addYears = (key: string, kind: AnomalyKind, source: Record<string, unknown>) => {
    const payload = source[key];
    for (const year of yearsOf(payload)) {
      events.push({
        id: `${kind}-${key}-${year}`,
        kind,
        label: `${KIND_LABEL[kind]} · ${year}`,
        time: yearToTime(year),
        year,
      });
    }
  };

  addYears("irreversible_return", "return", anomalies);
  addYears("baseline_return", "return", anomalies);
  addYears("chronology_rate", "rapid_rate", anomalies);
  addYears("biological_rate", "rapid_rate", anomalies);
  addYears("change_points", "change_point", manifest);
  addYears("change_points", "change_point", anomalies);

  for (const photo of photos) {
    const time = times.get(photo.id) ?? null;
    const flags = photo.flags ?? [];
    const push = (kind: AnomalyKind, reason: string) => {
      events.push({
        id: `${kind}-${photo.id}-${reason}`,
        kind,
        label: `${KIND_LABEL[kind]} · ${photo.date ?? photo.id}`,
        time,
        photoId: photo.id,
      });
    };
    if (flags.includes("RETURN_TO_BASELINE")) push("return", "flag");
    if (flags.includes("GEOMETRY_REVIEW_PAIR") || flags.includes("QUALITY_LIMITED_PAIR")) {
      push("review", "pair");
    }
    if (flags.includes("TEMPORAL_REVIEW_PAIR") || flags.includes("DATE_PROVENANCE_CONFLICT")) {
      push("same_day", "temporal");
    }
    if (photo.dateProvenanceStatus === "conflict" || photo.exifAnomaly) {
      push("provenance", "date");
    }
    const counts = photo.stage2StatusCounts ?? {};
    if ((counts.coherent_jump_candidate ?? 0) > 0 || (counts.persistent_geometric_change ?? 0) > 0) {
      push("persistent_change", "status");
    }
  }

  const seen = new Set<string>();
  return events.filter((event) => {
    const key = `${event.kind}:${event.year ?? event.photoId ?? event.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export const ANOMALY_LANES: Array<{ kind: AnomalyKind; title: string }> = [
  { kind: "persistent_change", title: "ИЗМЕНЕНИЯ" },
  { kind: "return", title: "ВОЗВРАТЫ" },
  { kind: "change_point", title: "ПЕРЕЛОМЫ" },
  { kind: "rapid_rate", title: "ТЕМП" },
  { kind: "same_day", title: "ОДИН ДЕНЬ" },
  { kind: "provenance", title: "ДАТЫ" },
  { kind: "review", title: "ПРОВЕРКА" },
];
