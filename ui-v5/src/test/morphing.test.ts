import { describe, expect, it } from "vitest";
import {
  buildAnchors,
  interpolatePositions,
  nearestAnchor,
  parseMeshBinary,
  residualColors,
  segmentAt,
} from "../features/morphing/meshData";
import { parseObj } from "../shared/ui/objParser";

/**
 * Тесты 3D-хронологии (§12).
 *
 * Главное свойство страницы: интерполяция — визуализация, а не измерение.
 * Тесты закрепляют, что концы отрезка совпадают с реальными кадрами точно,
 * что исключённые якоря не участвуют в интерполяции, и что бинарный разбор
 * не путает границы массивов (ошибка смещения дала бы «модель», собранную из
 * чужих чисел, и выглядела бы правдоподобно).
 */

/** Сборка бинарного ответа той же раскладки, что отдаёт backend. */
function makeBinary(vertexCount: number, triangleCount: number): ArrayBuffer {
  const header = JSON.stringify({
    schema: "deeputin-api-compare-v1.0-full-mesh-binary",
    photo_a: "1998_01_01__aaa",
    photo_b: "2026_05_13__bbb",
    vertex_count: vertexCount,
    triangle_count: triangleCount,
    residual_stats: { min: 0.01, max: 0.5, median: 0.1, p95: 0.4 },
  });
  const headerBytes = new TextEncoder().encode(header);
  const size =
    4 + headerBytes.length + vertexCount * 3 * 4 * 2 + vertexCount * 4 + triangleCount * 3 * 4;
  const buffer = new ArrayBuffer(size);
  const view = new DataView(buffer);
  view.setUint32(0, headerBytes.length, true);
  new Uint8Array(buffer, 4, headerBytes.length).set(headerBytes);

  /*
   * Массивы собираются отдельно и копируются побайтно: длина заголовка не
   * кратна четырём, а типизированный вид на невыровненное смещение создать
   * нельзя. Backend тоже не выравнивает заголовок — именно поэтому разбор в
   * `parseMeshBinary` идёт через `slice()` с копированием, а не через вид на
   * общий буфер. Тест закрепляет, что этот случай работает.
   */
  const a = new Float32Array(vertexCount * 3);
  for (let i = 0; i < a.length; i += 1) a[i] = i;
  const b = new Float32Array(vertexCount * 3);
  for (let i = 0; i < b.length; i += 1) b[i] = i + 100;
  const residuals = new Float32Array(vertexCount);
  for (let i = 0; i < residuals.length; i += 1) residuals[i] = i / vertexCount;
  const triangles = new Uint32Array(triangleCount * 3);
  for (let i = 0; i < triangles.length; i += 1) triangles[i] = i % vertexCount;

  const bytes = new Uint8Array(buffer);
  let offset = 4 + headerBytes.length;
  for (const chunk of [a, b, residuals, triangles]) {
    bytes.set(new Uint8Array(chunk.buffer), offset);
    offset += chunk.byteLength;
  }
  return buffer;
}

describe("разбор бинарного меша", () => {
  const payload = parseMeshBinary(makeBinary(6, 4));

  it("работает при невыровненной длине заголовка", () => {
    // Заголовок здесь не кратен четырём; разбор обязан это выдержать.
    expect(payload.verticesA[1]).toBe(1);
    expect(payload.triangles[0]).toBe(0);
  });

  it("читает заголовок и размеры", () => {
    expect(payload.vertexCount).toBe(6);
    expect(payload.triangleCount).toBe(4);
    expect(payload.photoA).toBe("1998_01_01__aaa");
    expect(payload.stats.p95).toBeCloseTo(0.4);
  });

  it("не смешивает массивы между собой", () => {
    expect(payload.verticesA).toHaveLength(18);
    expect(payload.verticesB).toHaveLength(18);
    expect(payload.residuals).toHaveLength(6);
    expect(payload.triangles).toHaveLength(12);
    expect(payload.verticesA[0]).toBe(0);
    expect(payload.verticesA[17]).toBe(17);
    expect(payload.verticesB[0]).toBe(100);
    expect(payload.verticesB[17]).toBe(117);
  });
});

describe("интерполяция позиций", () => {
  const a = new Float32Array([0, 0, 0, 10, 10, 10]);
  const b = new Float32Array([100, 100, 100, 110, 110, 110]);

  it("на концах отрезка совпадает с реальными кадрами точно", () => {
    const out = new Float32Array(6);
    expect(Array.from(interpolatePositions(a, b, 0, out))).toEqual(Array.from(a));
    expect(Array.from(interpolatePositions(a, b, 1, out))).toEqual(Array.from(b));
  });

  it("в середине даёт промежуточное положение", () => {
    const out = new Float32Array(6);
    expect(Array.from(interpolatePositions(a, b, 0.5, out))).toEqual([50, 50, 50, 60, 60, 60]);
  });

  it("значения вне [0,1] прижимаются к концам, а не экстраполируются", () => {
    const out = new Float32Array(6);
    expect(Array.from(interpolatePositions(a, b, -3, out))).toEqual(Array.from(a));
    expect(Array.from(interpolatePositions(a, b, 7, out))).toEqual(Array.from(b));
  });

  it("пишет в переданный буфер, не выделяя новый", () => {
    const out = new Float32Array(6);
    expect(interpolatePositions(a, b, 0.25, out)).toBe(out);
  });
});

describe("цвета тепловой карты", () => {
  it("значения выше границы прижимаются к ней", () => {
    const colors = new Float32Array(6);
    residualColors(new Float32Array([1, 1000]), 1, "linear", colors);
    expect(colors[0]).toBeCloseTo(colors[3], 5);
  });

  it("нулевой предел не приводит к делению на ноль", () => {
    const colors = new Float32Array(3);
    residualColors(new Float32Array([0.5]), 0, "linear", colors);
    expect(Number.isFinite(colors[0])).toBe(true);
  });

  it("логарифмическая шкала поднимает малые отклонения выше линейной", () => {
    const linear = new Float32Array(3);
    const log = new Float32Array(3);
    residualColors(new Float32Array([0.05]), 1, "linear", linear);
    residualColors(new Float32Array([0.05]), 1, "log", log);
    expect(log[0]).toBeGreaterThan(linear[0]);
  });
});

describe("якоря последовательности", () => {
  const photos = [
    { id: "b", date: "2010-05-05", bucket: "frontal", quality: 0.9 },
    { id: "a", date: "1999-01-01", bucket: "frontal", quality: 0.8 },
    { id: "c", date: "2020-01-01", bucket: "left_profile", quality: 0.9 },
    { id: "d", date: null, bucket: "frontal", quality: 0.9 },
    { id: "e", date: "2015-01-01", bucket: "frontal", quality: 0.2 },
  ];

  it("сортирует по времени и отбрасывает кадры без даты", () => {
    const anchors = buildAnchors(photos, { bucket: null, qualityFloor: null });
    expect(anchors.map((anchor) => anchor.id)).toEqual(["a", "b", "e", "c"]);
  });

  it("кадр чужого ракурса исключается с объяснением, но остаётся виден", () => {
    const anchors = buildAnchors(photos, { bucket: "frontal", qualityFloor: null });
    const foreign = anchors.find((anchor) => anchor.id === "c")!;
    expect(foreign.excluded).toBe(true);
    expect(foreign.reason).toMatch(/другой бин/);
    expect(anchors).toHaveLength(4);
  });

  it("порог качества исключает кадр, но не удаляет его из списка", () => {
    const anchors = buildAnchors(photos, { bucket: "frontal", qualityFloor: 0.5 });
    const weak = anchors.find((anchor) => anchor.id === "e")!;
    expect(weak.excluded).toBe(true);
    expect(weak.reason).toMatch(/качество/);
  });
});

describe("отрезок под скраббером", () => {
  const anchors = buildAnchors(
    [
      { id: "a", date: "2000-01-01", bucket: "frontal", quality: 1 },
      { id: "b", date: "2010-01-01", bucket: "frontal", quality: 1 },
      { id: "c", date: "2020-01-01", bucket: "frontal", quality: 1 },
    ],
    { bucket: "frontal", qualityFloor: null },
  );

  it("находит отрезок и долю внутри него", () => {
    const segment = segmentAt(anchors, Date.parse("2005-01-01"));
    expect(segment?.from.id).toBe("a");
    expect(segment?.to.id).toBe("b");
    expect(segment?.t).toBeGreaterThan(0.4);
    expect(segment?.t).toBeLessThan(0.6);
  });

  it("на самом якоре доля равна ровно нулю или единице", () => {
    expect(segmentAt(anchors, Date.parse("2000-01-01"))?.t).toBe(0);
    expect(segmentAt(anchors, Date.parse("2020-01-01"))?.t).toBe(1);
  });

  it("исключённые якоря не участвуют в интерполяции", () => {
    const withExcluded = buildAnchors(
      [
        { id: "a", date: "2000-01-01", bucket: "frontal", quality: 1 },
        { id: "bad", date: "2010-01-01", bucket: "left_profile", quality: 1 },
        { id: "c", date: "2020-01-01", bucket: "frontal", quality: 1 },
      ],
      { bucket: "frontal", qualityFloor: null },
    );
    const segment = segmentAt(withExcluded, Date.parse("2010-06-01"));
    expect(segment?.from.id).toBe("a");
    expect(segment?.to.id).toBe("c");
  });

  it("одного пригодного якоря недостаточно: морфить не между чем", () => {
    const single = buildAnchors([{ id: "a", date: "2000-01-01", bucket: "frontal", quality: 1 }], {
      bucket: "frontal",
      qualityFloor: null,
    });
    expect(segmentAt(single, Date.parse("2000-01-01"))).toBeNull();
  });

  it("ближайший якорь находится по обе стороны", () => {
    expect(nearestAnchor(anchors, Date.parse("2009-01-01"))?.id).toBe("b");
    expect(nearestAnchor(anchors, Date.parse("2019-01-01"))?.id).toBe("c");
    expect(nearestAnchor([], 0)).toBeNull();
  });
});

describe("разбор OBJ", () => {
  it("читает вершины и треугольники", () => {
    const mesh = parseObj(
      ["v 0 0 0", "v 1 0 0", "v 0 1 0", "vt 0 0", "f 1/1 2/2 3/3", "# комментарий"].join("\n"),
    );
    expect(mesh.vertexCount).toBe(3);
    expect(mesh.triangleCount).toBe(1);
    expect(Array.from(mesh.indices)).toEqual([0, 1, 2]);
    expect(Array.from(mesh.positions)).toEqual([0, 0, 0, 1, 0, 0, 0, 1, 0]);
  });

  it("разбивает четырёхугольник веером, а не отбрасывает его", () => {
    const mesh = parseObj(
      ["v 0 0 0", "v 1 0 0", "v 1 1 0", "v 0 1 0", "f 1 2 3 4"].join("\n"),
    );
    expect(mesh.triangleCount).toBe(2);
    expect(Array.from(mesh.indices)).toEqual([0, 1, 2, 0, 2, 3]);
  });

  it("пустой файл не приводит к исключению", () => {
    const mesh = parseObj("");
    expect(mesh.vertexCount).toBe(0);
    expect(mesh.triangleCount).toBe(0);
  });
});
