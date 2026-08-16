/**
 * Компактные факты о кадре (§10.3) и производные для вкладок инспектора.
 *
 * Спека требует «без больших таблиц»: поза, размеры изображения, площадь лица,
 * репроекция, число видимых точек, статус качества, флаги выражения, полнота
 * артефактов, состояние источника и даты. Всё это лежит в `info.json` на
 * разной глубине и под разными именами — модуль вытаскивает их в один список.
 *
 * 🚨 WARNING: если ключа нет, факт получает `value: null` и рисуется как «н/д».
 * Ни один факт не вычисляется «примерно» и не заполняется нулём: отсутствие
 * измерения — это результат, а не пустое место, которое надо чем-то закрыть.
 */

import type { PhotoInfoKeys } from "../../shared/api/schemas";

export interface CompactFact {
  key: string;
  label: string;
  value: string | null;
  /** Пояснение под значением: единицы, оговорки, источник числа. */
  hint?: string;
  /** Факт требует внимания эксперта (конфликт даты, неполные артефакты). */
  warn?: boolean;
}

/** Безопасный доступ по пути `a.b.c`. */
function pick(source: Record<string, unknown>, path: string): unknown {
  let current: unknown = source;
  for (const part of path.split(".")) {
    if (current === null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

function num(source: Record<string, unknown>, path: string): number | null {
  const raw = pick(source, path);
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

function str(source: Record<string, unknown>, path: string): string | null {
  const raw = pick(source, path);
  if (typeof raw === "string" && raw !== "") return raw;
  if (typeof raw === "number") return String(raw);
  return null;
}

function fixed(value: number | null, digits: number, unit = ""): string | null {
  if (value === null) return null;
  return `${value.toFixed(digits)}${unit}`;
}

/**
 * Ожидаемый набор файлов Stage 1. Список нужен, чтобы отличить «артефакт не
 * создавался» от «артефакт есть, но мы его не запросили»: без эталона полнота
 * не считается, а показывать «100%» от фактически найденного — самообман.
 */
export const EXPECTED_ARTIFACTS: readonly string[] = [
  "original.jpg",
  "face_crop.jpg",
  "face_mask.png",
  "face_mask.npz",
  "thumb.jpg",
  "info.json",
  "validation.json",
  "texture.json",
  "mesh.obj",
  "mesh.mtl",
  "reconstruction.npz",
  "semantic_channels.npz",
  "uv.npz",
  "uv_texture.png",
  "ldm106_original.csv",
  "ldm106_raw.csv",
  "ldm106_aligned.csv",
  "ldm106_chronology.csv",
  "ldm134_original.csv",
  "ldm134_raw.csv",
  "ldm134_aligned.csv",
  "ldm134_chronology.csv",
];

export interface ArtifactCompleteness {
  present: string[];
  missing: string[];
  extra: string[];
  ratio: string;
}

export function artifactCompleteness(artifacts: string[]): ArtifactCompleteness {
  const set = new Set(artifacts);
  const present = EXPECTED_ARTIFACTS.filter((name) => set.has(name));
  const missing = EXPECTED_ARTIFACTS.filter((name) => !set.has(name));
  const expected = new Set(EXPECTED_ARTIFACTS);
  const extra = artifacts.filter((name) => !expected.has(name)).sort();
  return {
    present,
    missing,
    extra,
    ratio: `${present.length} из ${EXPECTED_ARTIFACTS.length}`,
  };
}

/**
 * Площадь лица в пикселях исходного кадра по `crop.bbox_original`.
 * Возвращает `null`, если рамки нет: оценивать площадь по кропу 224×224
 * нельзя — это площадь ресайза, а не лица.
 */
export function faceAreaPx(info: Record<string, unknown>): {
  width: number;
  height: number;
  share: number | null;
} | null {
  const bbox = pick(info, "crop.bbox_original");
  if (!Array.isArray(bbox) || bbox.length < 4) return null;
  const [x0, y0, x1, y1] = bbox.map((v) => (typeof v === "number" ? v : NaN));
  if ([x0, y0, x1, y1].some((v) => !Number.isFinite(v))) return null;
  const width = Math.abs(x1 - x0);
  const height = Math.abs(y1 - y0);
  const size = pick(info, "image.decode.encoded_size");
  let share: number | null = null;
  if (Array.isArray(size) && size.length >= 2) {
    const [iw, ih] = size.map((v) => (typeof v === "number" ? v : NaN));
    if (Number.isFinite(iw) && Number.isFinite(ih) && iw > 0 && ih > 0) {
      share = (width * height) / (iw * ih);
    }
  }
  return { width, height, share };
}

/** Состояние даты: авторитет, конфликт, расхождение с EXIF. */
export function dateState(info: Record<string, unknown>): {
  authority: string | null;
  conflicts: string[];
  deltaDays: number | null;
  exif: string | null;
  policy: string | null;
} {
  const conflictsRaw = pick(info, "date_provenance.conflict_sources");
  return {
    authority: str(info, "date_provenance.authority"),
    conflicts: Array.isArray(conflictsRaw) ? conflictsRaw.map(String) : [],
    deltaDays: num(info, "date_provenance.delta_days"),
    exif: str(info, "date_provenance.exif_date"),
    policy: str(info, "date_provenance.policy"),
  };
}

/**
 * Компактные факты в порядке §10.3.
 */
export function compactFacts(data: PhotoInfoKeys): CompactFact[] {
  const info = data.info as Record<string, unknown>;
  const facts: CompactFact[] = [];

  const yaw = num(info, "pose.yaw");
  const pitch = num(info, "pose.pitch");
  const roll = num(info, "pose.roll");
  const canonical = num(info, "pose.canonical_yaw");
  facts.push({
    key: "pose",
    label: "Поза",
    value:
      yaw === null && pitch === null && roll === null
        ? null
        : `yaw ${fixed(yaw, 1, "°") ?? "н/д"} · pitch ${fixed(pitch, 1, "°") ?? "н/д"} · roll ${fixed(roll, 1, "°") ?? "н/д"}`,
    hint:
      canonical === null
        ? "бин ракурса из Stage 1"
        : `канонический yaw бина: ${canonical.toFixed(1)}°`,
  });

  const size = pick(info, "image.decode.encoded_size");
  const dims =
    Array.isArray(size) && size.length >= 2 ? `${size[0]} × ${size[1]} px` : null;
  facts.push({
    key: "dimensions",
    label: "Размер изображения",
    value: dims,
    hint: str(info, "image.decode.encoded_mode")
      ? `режим ${str(info, "image.decode.encoded_mode")}`
      : undefined,
  });

  const area = faceAreaPx(info);
  facts.push({
    key: "face-area",
    label: "Площадь лица",
    value: area ? `${Math.round(area.width)} × ${Math.round(area.height)} px` : null,
    hint:
      area && area.share !== null
        ? `${(area.share * 100).toFixed(1)}% кадра · рамка ${str(info, "crop.crop_source") ?? "н/д"}`
        : "рамка crop.bbox_original",
  });

  const rmse106 = num(info, "reprojection.ldm106_224.rmse");
  const p95 = num(info, "reprojection.ldm106_224.p95");
  facts.push({
    key: "reprojection",
    label: "Репроекция LDM106",
    value: rmse106 === null ? null : `RMSE ${rmse106.toFixed(3)} px`,
    hint: p95 === null ? "в системе кропа 224×224" : `p95 ${p95.toFixed(3)} px · кроп 224×224`,
  });

  const visible106 = num(info, "chronology.visible_landmarks_106");
  const visible134 = num(info, "chronology.visible_landmarks_134");
  const visibleFraction = num(info, "quality_inputs.combined_visible_fraction");
  facts.push({
    key: "visible",
    label: "Видимых точек",
    value:
      visible106 === null && visible134 === null
        ? null
        : `${visible106 ?? "н/д"} из 106 · ${visible134 ?? "н/д"} из 134`,
    hint:
      visibleFraction === null
        ? "по карте видимости в хронологическом пространстве"
        : `видимая доля лица ${(visibleFraction * 100).toFixed(1)}%`,
    // Больше половины точек закрыто — геометрию по такому кадру считать рискованно.
    warn: visible106 !== null && visible106 < 53,
  });

  const qStatus = str(info, "skin_quality_status");
  const qScore = num(info, "skin_quality_score");
  facts.push({
    key: "quality",
    label: "Качество кожи",
    value: qStatus === null ? null : qStatus,
    hint: qScore === null ? undefined : `оценка ${qScore.toFixed(3)}`,
  });

  const auth = str(info, "skin_authenticity_status");
  const authScore = num(info, "skin_authenticity_score");
  facts.push({
    key: "authenticity",
    label: "Аутентичность кожи",
    value: auth,
    hint:
      authScore === null
        ? "НЕ ВЕРДИКТ о подлинности личности"
        : `оценка ${authScore.toFixed(3)} · НЕ ВЕРДИКТ`,
  });

  const expressionMagnitude = num(info, "chronology.expression_magnitude");
  const hardStop = pick(info, "skin.hard_stop");
  const hardStopReason = str(info, "skin.hard_stop_reason");
  facts.push({
    key: "expression",
    label: "Выражение лица",
    value:
      expressionMagnitude === null
        ? null
        : `магнитуда ${expressionMagnitude.toFixed(2)}`,
    hint:
      hardStop === true
        ? `стоп-фактор кожи: ${hardStopReason ?? "причина не указана"}`
        : "отклонение от нейтрального выражения в хронологическом пространстве",
    warn: hardStop === true,
  });

  const completeness = artifactCompleteness(data.artifacts ?? []);
  facts.push({
    key: "artifacts",
    label: "Полнота артефактов",
    value: completeness.ratio,
    hint:
      completeness.missing.length === 0
        ? "все ожидаемые файлы на месте"
        : `нет: ${completeness.missing.slice(0, 3).join(", ")}${completeness.missing.length > 3 ? "…" : ""}`,
    warn: completeness.missing.length > 0,
  });

  const dates = dateState(info);
  const sourceStatus = str(info, "source_provenance.status");
  facts.push({
    key: "date-state",
    label: "Дата и источник",
    value: dates.authority === null ? null : `авторитет: ${dates.authority}`,
    hint:
      dates.conflicts.length > 0
        ? `конфликт: ${dates.conflicts.join(", ")}`
        : `sidecar: ${sourceStatus ?? "н/д"}`,
    warn: dates.conflicts.length > 0 || sourceStatus === "not_provided",
  });

  return facts;
}

/**
 * Ограничения кадра для вкладки Summary. Формулируются как ограничения
 * применимости, а не как выводы: инспектор показывает один кадр и по одному
 * кадру ничего об идентичности сказать нельзя.
 */
export function limitations(data: PhotoInfoKeys): string[] {
  const info = data.info as Record<string, unknown>;
  const notes: string[] = [];

  const dates = dateState(info);
  if (dates.authority === "filename") {
    notes.push(
      "Дата взята из имени файла. EXIF и заявления источника её не переопределяют — они могут только подтвердить.",
    );
  }
  if (dates.conflicts.length > 0) {
    notes.push(
      `Источники даты расходятся (${dates.conflicts.join(", ")}). Расхождение показано, но не устранено: устранять его — работа эксперта.`,
    );
  }
  if (str(info, "source_provenance.status") === "not_provided") {
    notes.push(
      "Провенанс-сайдкар не приложен: происхождение файла не подтверждено ничем, кроме имени.",
    );
  }
  const dup = pick(info, "near_duplicate_of");
  if (typeof dup === "string" && dup !== "") {
    notes.push(`Кадр помечен как близкий дубликат ${dup}: считать его независимым наблюдением нельзя.`);
  }
  const completeness = artifactCompleteness(data.artifacts ?? []);
  if (completeness.missing.length > 0) {
    notes.push(
      `Не все артефакты Stage 1 созданы (нет ${completeness.missing.length} из ${EXPECTED_ARTIFACTS.length}). Часть вкладок останется пустой.`,
    );
  }
  const errors = pick(data.validation as Record<string, unknown>, "errors");
  if (Array.isArray(errors) && errors.length > 0) {
    notes.push(`Валидация Stage 1 вернула ошибки: ${errors.map(String).join("; ")}`);
  }
  const warnings = pick(data.validation as Record<string, unknown>, "warnings");
  if (Array.isArray(warnings) && warnings.length > 0) {
    notes.push(`Предупреждения валидации: ${warnings.map(String).join("; ")}`);
  }

  notes.push(
    "Инспектор показывает один кадр. Ни качество, ни аутентичность кожи не являются суждением о личности — это входные данные для сравнения пар.",
  );
  return notes;
}
