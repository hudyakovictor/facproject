import { describe, expect, it } from "vitest";
import { buildDemoPhotos } from "../demoData";

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

  it("модуль допускает динамический импорт как тестовая фикстура", async () => {
    const { buildDemoPhotos: loadFixture } = await import("../demoData");
    const photos = loadFixture();
    expect(photos.length).toBeGreaterThan(1000);
  });
});
