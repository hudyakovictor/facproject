import { describe, expect, it } from "vitest";
import { buildDemoPhotos } from "../demoData";
import { REF, loadDemoPhotos } from "../data";

/** Демо-генератор вынесен из основного бандла (аудит №27).
 *
 * Раньше 170 строк генератора и построенный им массив из 1809 объектов
 * попадали в основной чанк и исполнялись на старте — даже при полностью
 * рабочем backend, когда демо-набор не нужен ни разу.
 */
describe("демо-набор", () => {
  it("детерминирован: два вызова дают одинаковый результат", () => {
    // Генератор на seeded PRNG. Недетерминизм здесь означал бы, что
    // «встроенный демо-набор» меняется между перезагрузками, и снимок
    // экрана невозможно воспроизвести.
    const first = buildDemoPhotos();
    const second = buildDemoPhotos();
    expect(first.length).toBe(second.length);
    expect(first[0]).toEqual(second[0]);
    expect(first.at(-1)).toEqual(second.at(-1));
  });

  it("кадры отсортированы по времени", () => {
    const photos = buildDemoPhotos();
    for (let i = 1; i < photos.length; i++) {
      expect(photos[i].t).toBeGreaterThanOrEqual(photos[i - 1].t);
    }
  });

  it("идентификаторы уникальны", () => {
    const photos = buildDemoPhotos();
    expect(new Set(photos.map(p => p.id)).size).toBe(photos.length);
  });

  it("загружается динамическим импортом", async () => {
    const photos = await loadDemoPhotos();
    expect(photos.length).toBeGreaterThan(1000);
  });
});

/** Страж констант REF.
 *
 * `REF` был вычисляемым (`refMedians()` прогоняла весь демо-массив на
 * старте) и стал статической таблицей. Значения детерминированы, но если
 * генератор изменится, таблица молча разойдётся с ним — и baseline
 * демо-режима начнёт считаться от неверных медиан.
 */
describe("REF соответствует генератору", () => {
  it("медианы и разбросы совпадают с фактическим демо-набором", () => {
    const era1 = buildDemoPhotos().filter(p => p.era === "ERA_1_BASELINE");
    expect(era1.length).toBeGreaterThan(0);

    const median = (values: number[]) => {
      const sorted = [...values].sort((a, b) => a - b);
      return sorted[Math.floor(sorted.length / 2)];
    };
    const stdev = (values: number[], m: number) =>
      Math.sqrt(values.reduce((s, v) => s + (v - m) ** 2, 0) / values.length);

    for (const key of Object.keys(REF)) {
      const values = era1.map(p => p[key as keyof typeof p] as number);
      const m = median(values);
      expect(REF[key].median, `REF.${key}.median`).toBeCloseTo(m, 5);
      expect(REF[key].std, `REF.${key}.std`).toBeCloseTo(Math.max(0.001, stdev(values, m)), 5);
    }
  });

  it("покрывает все метрики, используемые интерфейсом", () => {
    for (const key of ["boneScore", "orbit", "chin", "jaw", "cheek", "symmetry",
      "siliconeProb", "specular", "lbpEntropy", "frangi", "wrinkle", "subsurface", "visualAge"]) {
      expect(REF[key], `REF.${key}`).toBeDefined();
    }
  });
});
