/**
 * Загрузка полного меша пары и подготовка данных для морфинга (§12.2).
 *
 * `/api/v1/compare/full_mesh` в каноническом API отдаёт 35 709 вершин, 70 789
 * треугольников и residual по каждой вершине в JSON. Это десятки мегабайт
 * текста на одну пару: браузер потратит больше времени на разбор чисел, чем на
 * рендер. Поэтому используется бинарная раскладка — заголовок JSON, затем
 * сырые `Float32Array` и `Uint32Array`, которые попадают в буферы GPU без
 * поэлементного преобразования.
 *
 * 🚨 WARNING: интерполяция между A и B — **визуализация, а не измерение**
 * (правило `AGENTS.md`). Промежуточное положение вершины не является
 * наблюдением: между двумя снимками нет данных, и любой кадр морфа —
 * предположение о плавном переходе. Ни одно число из промежуточного состояния
 * не попадает в метрики и не экспортируется как результат.
 */

export interface MeshPayload {
  schema: string;
  photoA: string;
  photoB: string;
  vertexCount: number;
  triangleCount: number;
  /** Позиции A: 3 float на вершину. */
  verticesA: Float32Array;
  /** Позиции B после жёсткого выравнивания на A. */
  verticesB: Float32Array;
  /** Расстояние между соответствующими вершинами A и B. */
  residuals: Float32Array;
  triangles: Uint32Array;
  stats: { min: number; max: number; median: number; p95: number };
}

/** Разбор бинарного ответа. Раскладка описана в поле `layout` заголовка. */
export function parseMeshBinary(buffer: ArrayBuffer): MeshPayload {
  const view = new DataView(buffer);
  const headerLength = view.getUint32(0, true);
  const headerText = new TextDecoder().decode(new Uint8Array(buffer, 4, headerLength));
  const header = JSON.parse(headerText) as {
    schema: string;
    photo_a: string;
    photo_b: string;
    vertex_count: number;
    triangle_count: number;
    residual_stats: { min: number; max: number; median: number; p95: number };
  };

  const vertexCount = header.vertex_count;
  const triangleCount = header.triangle_count;

  let offset = 4 + headerLength;
  const verticesA = new Float32Array(buffer.slice(offset, offset + vertexCount * 3 * 4));
  offset += vertexCount * 3 * 4;
  const verticesB = new Float32Array(buffer.slice(offset, offset + vertexCount * 3 * 4));
  offset += vertexCount * 3 * 4;
  const residuals = new Float32Array(buffer.slice(offset, offset + vertexCount * 4));
  offset += vertexCount * 4;
  const triangles = new Uint32Array(buffer.slice(offset, offset + triangleCount * 3 * 4));

  return {
    schema: header.schema,
    photoA: header.photo_a,
    photoB: header.photo_b,
    vertexCount,
    triangleCount,
    verticesA,
    verticesB,
    residuals,
    triangles,
    stats: header.residual_stats,
  };
}

function flattenXYZ(points: number[][]): Float32Array {
  const out = new Float32Array(points.length * 3);
  for (let i = 0; i < points.length; i += 1) {
    const point = points[i] ?? [];
    out[i * 3] = point[0] ?? 0;
    out[i * 3 + 1] = point[1] ?? 0;
    out[i * 3 + 2] = point[2] ?? 0;
  }
  return out;
}

function flattenTriangles(faces: number[][]): Uint32Array {
  const out = new Uint32Array(faces.length * 3);
  for (let i = 0; i < faces.length; i += 1) {
    const face = faces[i] ?? [];
    out[i * 3] = face[0] ?? 0;
    out[i * 3 + 1] = face[1] ?? 0;
    out[i * 3 + 2] = face[2] ?? 0;
  }
  return out;
}

/** Живой контракт: POST /api/v1/compare/full_mesh, JSON с вершинами A/B. */
export async function fetchMeshPair(photoA: string, photoB: string): Promise<MeshPayload> {
  const response = await fetch("/api/v1/compare/full_mesh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_a: photoA, photo_b: photoB }),
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // тело не JSON
    }
    const error = new Error(detail) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  const payload = (await response.json()) as {
    schema?: string;
    photo_a?: { id?: string } | string;
    photo_b?: { id?: string } | string;
    vertex_count?: number;
    triangle_count?: number;
    vertices_a?: number[][];
    vertices_b_aligned?: number[][];
    residuals?: number[];
    triangles?: number[][];
    residual_stats?: { min: number; max: number; median: number; p95: number };
  };
  const verticesA = flattenXYZ(payload.vertices_a ?? []);
  const verticesB = flattenXYZ(payload.vertices_b_aligned ?? []);
  const residuals = Float32Array.from(payload.residuals ?? []);
  const triangles = flattenTriangles(payload.triangles ?? []);
  const idOf = (value: { id?: string } | string | undefined, fallback: string) =>
    typeof value === "string" ? value : value?.id ?? fallback;
  return {
    schema: payload.schema ?? "compare-full-mesh",
    photoA: idOf(payload.photo_a, photoA),
    photoB: idOf(payload.photo_b, photoB),
    vertexCount: payload.vertex_count ?? verticesA.length / 3,
    triangleCount: payload.triangle_count ?? triangles.length / 3,
    verticesA,
    verticesB,
    residuals,
    triangles,
    stats: payload.residual_stats ?? { min: 0, max: 0, median: 0, p95: 0 },
  };
}

/**
 * Линейная интерполяция позиций для кадра морфа.
 *
 * `t = 0` — ровно кадр A, `t = 1` — ровно кадр B. Всё между ними построено, а
 * не измерено; интерфейс обязан подписывать такое состояние как промежуточное.
 * Результат пишется в переданный буфер: на 35 709 вершин выделять новый массив
 * каждый кадр значит собирать мусор шестьдесят раз в секунду.
 */
export function interpolatePositions(
  a: Float32Array,
  b: Float32Array,
  t: number,
  out: Float32Array,
): Float32Array {
  const clamped = Math.min(1, Math.max(0, t));
  for (let index = 0; index < out.length; index += 1) {
    out[index] = a[index] + (b[index] - a[index]) * clamped;
  }
  return out;
}

export type HeatmapScale = "linear" | "log";

/**
 * Цвет вершины по величине отклонения (§12.4).
 *
 * Палитра идёт от нейтрального серого к янтарному и красному: она совпадает по
 * смыслу со статусами интерфейса, где красный означает «требует внимания», а
 * не «плохо». Значения выше `max` прижимаются к границе (clamp), и это
 * состояние подписывается: иначе один выброс перекрасил бы всю модель в
 * зелёный, создав впечатление, что отклонений нет.
 */
export function residualColors(
  residuals: Float32Array,
  max: number,
  scale: HeatmapScale,
  out: Float32Array,
): Float32Array {
  const safeMax = max > 0 ? max : 1;
  for (let index = 0; index < residuals.length; index += 1) {
    const raw = residuals[index] / safeMax;
    const normalized =
      scale === "log" ? Math.log1p(Math.max(0, raw) * 9) / Math.log(10) : raw;
    const t = Math.min(1, Math.max(0, normalized));
    // серый → янтарный → красный
    const r = 0.35 + 0.6 * t;
    const g = 0.38 + 0.42 * Math.max(0, 1 - Math.abs(t - 0.5) * 2) - 0.3 * Math.max(0, t - 0.5) * 2;
    const b = 0.42 * Math.max(0, 1 - t * 1.6);
    out[index * 3] = r;
    out[index * 3 + 1] = Math.max(0, Math.min(1, g));
    out[index * 3 + 2] = Math.max(0, Math.min(1, b));
  }
  return out;
}

/**
 * Опорные кадры морфа (§12.8): реальные снимки, между которыми ведётся
 * интерполяция. Кадр без даты не может быть якорем — его некуда поставить на
 * временной оси, и «примерное» место было бы выдумкой.
 */
export interface Anchor {
  id: string;
  date: string;
  /** Позиция на оси времени в миллисекундах. */
  time: number;
  bucket: string;
  /** Якорь исключён из интерполяции, но показывается (§12.8). */
  excluded: boolean;
  reason: string | null;
}

export function buildAnchors(
  photos: Array<{ id: string; date: string | null; bucket: string; quality: number | null }>,
  options: { bucket: string | null; qualityFloor: number | null },
): Anchor[] {
  const anchors: Anchor[] = [];
  for (const photo of photos) {
    if (!photo.date) continue;
    const time = Date.parse(photo.date);
    if (!Number.isFinite(time)) continue;
    const wrongBucket = options.bucket !== null && photo.bucket !== options.bucket;
    const lowQuality =
      options.qualityFloor !== null &&
      photo.quality !== null &&
      photo.quality < options.qualityFloor;
    anchors.push({
      id: photo.id,
      date: photo.date,
      time,
      bucket: photo.bucket,
      excluded: wrongBucket || lowQuality,
      reason: wrongBucket
        ? "другой бин ракурса: интерполяция между ракурсами смешала бы поворот головы с изменением формы"
        : lowQuality
          ? "качество ниже порога: реконструкция ненадёжна"
          : null,
    });
  }
  anchors.sort((left, right) => left.time - right.time);
  return anchors;
}

/**
 * Отрезок, в котором находится позиция скраббера, и доля внутри него.
 * Возвращает `null`, если пригодных якорей меньше двух: морфить не между чем.
 */
export function segmentAt(
  anchors: Anchor[],
  time: number,
): { from: Anchor; to: Anchor; t: number } | null {
  const usable = anchors.filter((anchor) => !anchor.excluded);
  if (usable.length < 2) return null;
  if (time <= usable[0].time) return { from: usable[0], to: usable[1], t: 0 };
  const last = usable[usable.length - 1];
  if (time >= last.time) {
    return { from: usable[usable.length - 2], to: last, t: 1 };
  }
  for (let index = 0; index < usable.length - 1; index += 1) {
    const from = usable[index];
    const to = usable[index + 1];
    if (time >= from.time && time <= to.time) {
      const span = to.time - from.time;
      return { from, to, t: span === 0 ? 0 : (time - from.time) / span };
    }
  }
  return null;
}

/** Ближайший реальный якорь — для привязки скраббера (§12.6 snap to real photo). */
export function nearestAnchor(anchors: Anchor[], time: number): Anchor | null {
  const usable = anchors.filter((anchor) => !anchor.excluded);
  if (usable.length === 0) return null;
  return usable.reduce((best, anchor) =>
    Math.abs(anchor.time - time) < Math.abs(best.time - time) ? anchor : best,
  );
}
