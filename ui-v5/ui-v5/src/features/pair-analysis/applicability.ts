/**
 * Карточка применимости пары (§11.5).
 *
 * Спека требует показать её **до метрик**, и это не вопрос вёрстки. Число
 * `ldm134_rmse = 0.066` само по себе ничего не значит: если кадры сняты в
 * разных ракурсах, половина точек закрыта, а калибровки для этого страта нет,
 * то это шум измерения, а не различие лиц. Карточка перечисляет условия и
 * выносит одно из трёх решений — принято / ограниченно применимо / исключено.
 *
 * 🚨 WARNING: решение здесь — о **применимости измерения**, а не о личности.
 * «Исключено» означает «этой парой пользоваться нельзя», а не «это разные
 * люди». Формулировки подобраны так, чтобы их нельзя было прочитать иначе.
 */

import type { MetricValue, PairMetrics } from "../../shared/api/schemas";

export type Verdict = "accepted" | "limited" | "excluded" | "unknown";

export interface ApplicabilityCheck {
  id: string;
  label: string;
  /** Что реально измерено. `null` — Stage 2 не дал значения. */
  value: string | null;
  verdict: Verdict;
  /** Почему проверка привела к такому решению. */
  reason: string;
}

export interface Applicability {
  verdict: Verdict;
  checks: ApplicabilityCheck[];
  /** Краткая причина итогового решения для шапки пары. */
  summary: string;
}

/** Плоский доступ к колонке независимо от того, в какой она категории. */
export function flattenMetrics(data: PairMetrics): Map<string, MetricValue> {
  const flat = new Map<string, MetricValue>();
  if (!data.categories) return flat;
  for (const groups of Object.values(data.categories)) {
    for (const columns of Object.values(groups)) {
      for (const [column, value] of Object.entries(columns)) {
        flat.set(column, value);
      }
    }
  }
  return flat;
}

function numberOf(flat: Map<string, MetricValue>, key: string): number | null {
  const raw = flat.get(key);
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

function boolOf(flat: Map<string, MetricValue>, key: string): boolean | null {
  const raw = flat.get(key);
  if (typeof raw === "boolean") return raw;
  if (raw === "True") return true;
  if (raw === "False") return false;
  return null;
}

function textOf(flat: Map<string, MetricValue>, key: string): string | null {
  const raw = flat.get(key);
  if (raw === null || raw === undefined || raw === "") return null;
  return String(raw);
}

/** Худшее из решений: одно «исключено» перевешивает любое число «принято». */
function worst(verdicts: Verdict[]): Verdict {
  if (verdicts.includes("excluded")) return "excluded";
  if (verdicts.includes("limited")) return "limited";
  if (verdicts.every((verdict) => verdict === "unknown")) return "unknown";
  return verdicts.includes("unknown") ? "limited" : "accepted";
}

export const VERDICT_LABELS: Record<Verdict, string> = {
  accepted: "принято",
  limited: "ограниченно применимо",
  excluded: "исключено",
  unknown: "нет данных",
};

/**
 * Условия применимости в порядке §11.5: один бин, разрывы по углам, общие
 * точки, покрытие калибровкой, качество, выражение, провенанс, дубликаты,
 * система координат.
 */
export function applicability(data: PairMetrics): Applicability {
  const flat = flattenMetrics(data);
  const checks: ApplicabilityCheck[] = [];

  const poseBin = textOf(flat, "pose_bin");
  checks.push({
    id: "same-bin",
    label: "Один бин ракурса",
    value: poseBin,
    verdict: poseBin === null ? "unknown" : "accepted",
    reason:
      poseBin === null
        ? "Бин пары не указан в выводе Stage 2."
        : `Stage 2 строит пары только внутри бина; эта пара из «${poseBin}».`,
  });

  const yawGap = numberOf(flat, "yaw_gap_deg");
  const pitchGap = numberOf(flat, "pitch_gap_deg");
  const rollGap = numberOf(flat, "roll_gap_deg");
  const poseDistance = numberOf(flat, "pose_distance");
  const gapReason = textOf(flat, "pose_gap_reason");
  const anyGap = yawGap !== null || pitchGap !== null || rollGap !== null;
  checks.push({
    id: "pose-gap",
    label: "Разрывы по углам",
    value: anyGap
      ? `yaw ${yawGap?.toFixed(1) ?? "н/д"}° · pitch ${pitchGap?.toFixed(1) ?? "н/д"}° · roll ${rollGap?.toFixed(1) ?? "н/д"}°`
      : poseDistance !== null
        ? `расстояние по позе ${poseDistance.toFixed(3)}`
        : null,
    verdict: anyGap || poseDistance !== null ? "accepted" : "unknown",
    reason:
      gapReason ??
      (anyGap
        ? "Разрывы углов измерены."
        : poseDistance !== null
          ? "Поугловые разрывы Stage 2 не записал; есть только суммарное расстояние по позе."
          : "Разрывы углов не измерены."),
  });

  const common106 = numberOf(flat, "common_visible106");
  const common134 = numberOf(flat, "common_visible134");
  const accepted106 = boolOf(flat, "visibility_gate_accepted106");
  const accepted134 = boolOf(flat, "visibility_gate_accepted134");
  const required134 = numberOf(flat, "visibility_gate_required134");
  const visibilityVerdict: Verdict =
    accepted134 === false || accepted106 === false
      ? "excluded"
      : accepted134 === null && accepted106 === null
        ? "unknown"
        : "accepted";
  checks.push({
    id: "common-points",
    label: "Общие видимые точки",
    value:
      common106 === null && common134 === null
        ? null
        : `LDM106: ${common106 ?? "н/д"} · LDM134: ${common134 ?? "н/д"}`,
    verdict: visibilityVerdict,
    reason:
      visibilityVerdict === "excluded"
        ? `Порог видимости не пройден${required134 !== null ? ` (требуется ${required134} точек LDM134)` : ""}.`
        : "Порог видимости пройден: общих точек достаточно для сопоставления.",
  });

  const calibrationLimited = boolOf(flat, "calibration_limited");
  const calibrationReason = textOf(flat, "calibration_limitation_reason");
  const matchedSets = textOf(flat, "matched_calibration_sets");
  checks.push({
    id: "calibration",
    label: "Покрытие калибровкой",
    value: matchedSets,
    verdict:
      calibrationLimited === true ? "limited" : calibrationLimited === false ? "accepted" : "unknown",
    reason:
      calibrationLimited === true
        ? `Калибровка неполная: ${calibrationReason ?? "причина не указана"}. Пороги значимости для этой пары ненадёжны.`
        : calibrationLimited === false
          ? "Калибровочный набор для страта найден."
          : "Статус калибровки не сообщён.",
  });

  const qualityAccepted = boolOf(flat, "quality_gate_accepted");
  const qualityLimited = boolOf(flat, "quality_limited");
  const stratum = textOf(flat, "quality_stratum");
  checks.push({
    id: "quality",
    label: "Качество кадров",
    value: stratum === null ? null : `страт «${stratum}»`,
    verdict:
      qualityAccepted === false
        ? "excluded"
        : qualityLimited === true
          ? "limited"
          : qualityAccepted === true
            ? "accepted"
            : "unknown",
    reason:
      qualityAccepted === false
        ? "Порог качества не пройден: измерения по этой паре не используются."
        : qualityLimited === true
          ? "Качество ограничивает выводы: пороги смягчены по страту."
          : "Порог качества пройден.",
  });

  const jawMismatch = boolOf(flat, "expression_gate_jaw_mismatch");
  const smileMismatch = boolOf(flat, "expression_gate_smile_mismatch");
  const multiplier = numberOf(flat, "expression_gate_multiplier");
  const expressionVerdict: Verdict =
    jawMismatch === true || smileMismatch === true
      ? "limited"
      : jawMismatch === null && smileMismatch === null
        ? "unknown"
        : "accepted";
  checks.push({
    id: "expression",
    label: "Выражение лица",
    value: multiplier === null ? null : `множитель порога ${multiplier}`,
    verdict: expressionVerdict,
    reason:
      expressionVerdict === "limited"
        ? `Выражения различаются (${[jawMismatch === true ? "челюсть" : null, smileMismatch === true ? "улыбка" : null].filter(Boolean).join(", ")}). Часть различий объясняется мимикой, а не формой.`
        : "Выражения сопоставимы.",
  });

  const provenanceLimited = boolOf(flat, "date_provenance_limited");
  const statusA = textOf(flat, "source_provenance_status_a");
  const statusB = textOf(flat, "source_provenance_status_b");
  /*
   * Отсутствие сайдкара — это не «конфликта нет», а «подтверждать нечем».
   * Флаг `date_provenance_limited` говорит только о согласованности дат между
   * известными источниками; если источник вообще не приложен, происхождение
   * кадра ничем не подтверждено, и пара применима с оговоркой.
   */
  const sidecarMissing = statusA === "not_provided" || statusB === "not_provided";
  const provenanceVerdict: Verdict =
    provenanceLimited === true || sidecarMissing
      ? "limited"
      : provenanceLimited === false
        ? "accepted"
        : "unknown";
  checks.push({
    id: "provenance",
    label: "Провенанс",
    value: statusA === null && statusB === null ? null : `A: ${statusA ?? "н/д"} · B: ${statusB ?? "н/д"}`,
    verdict: provenanceVerdict,
    reason:
      provenanceLimited === true
        ? "Источники даты расходятся: хронологические выводы по этой паре ограничены."
        : sidecarMissing
          ? "Провенанс-сайдкар не приложен хотя бы к одному кадру: происхождение не подтверждено ничем, кроме имени файла."
          : "Даты кадров разрешены без конфликта источников.",
  });

  const duplicatePair = boolOf(flat, "near_duplicate_pair");
  checks.push({
    id: "duplicates",
    label: "Дубликаты",
    value: duplicatePair === null ? null : duplicatePair ? "кадры почти совпадают" : "различные кадры",
    verdict: duplicatePair === true ? "excluded" : duplicatePair === false ? "accepted" : "unknown",
    reason:
      duplicatePair === true
        ? "Кадры признаны близкими дубликатами: сравнение измеряет шум сжатия, а не изменение лица."
        : "Кадры не являются дубликатами друг друга.",
  });

  const space = textOf(flat, "analysis_space");
  checks.push({
    id: "space",
    label: "Система координат",
    value: space,
    verdict: space === null ? "unknown" : "accepted",
    reason:
      space === null
        ? "Пространство анализа не указано."
        : `Сравнение выполнено в пространстве «${space}»; смешивать его с другими нельзя.`,
  });

  const verdict = worst(checks.map((check) => check.verdict));
  const blocking = checks.filter((check) => check.verdict === "excluded");
  const limiting = checks.filter((check) => check.verdict === "limited");

  const summary =
    verdict === "excluded"
      ? `Измерения непригодны: ${blocking.map((check) => check.label.toLowerCase()).join(", ")}.`
      : verdict === "limited"
        ? `Применимо с оговорками: ${limiting.map((check) => check.label.toLowerCase()).join(", ")}.`
        : verdict === "accepted"
          ? "Условия применимости выполнены. Это утверждение об измеримости пары, а не о личности."
          : "Данных о применимости недостаточно.";

  return { verdict, checks, summary };
}
