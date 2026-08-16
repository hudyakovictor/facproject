import { describe, expect, test } from "vitest";
import {
  sidecarSchema,
  claimedDateDelta,
  SIDECAR_SCHEMA_ID,
} from "../features/data-manager/sidecarSchema";

/**
 * Схема sidecar должна совпадать с канонической
 * `app6/schemas/provenance_sidecar_v1.json`: интерфейс, принимающий то, что
 * backend отвергнет, обещает пользователю несуществующий результат.
 */

const ok = (value: unknown) => sidecarSchema.safeParse(value).success;

describe("схема provenance-sidecar (§7.3)", () => {
  test("идентификатор схемы совпадает с каноническим", () => {
    expect(SIDECAR_SCHEMA_ID).toBe("deeputin-provenance-sidecar-v1");
  });

  test("нужен хотя бы один адрес — источника или архива", () => {
    // anyOf в канонической схеме: запись без ссылки нечем проверить.
    expect(ok({ publisher: "Издание" })).toBe(false);
    expect(ok({ source_url: "https://example.org/a" })).toBe(true);
    expect(ok({ archive_url: "https://web.archive.org/x" })).toBe(true);
  });

  test("адрес без протокола отклоняется", () => {
    expect(ok({ source_url: "example.org/a" })).toBe(false);
    expect(ok({ source_url: "ftp://example.org/a" })).toBe(false);
  });

  test("заявленная дата принимается только как ГГГГ-ММ-ДД", () => {
    expect(ok({ source_url: "https://a.b/c", claimed_date: "2014-03-18" })).toBe(true);
    expect(ok({ source_url: "https://a.b/c", claimed_date: "18.03.2014" })).toBe(false);
  });

  test("время получения допускает дату и дату со временем", () => {
    expect(ok({ source_url: "https://a.b/c", acquired_at: "2026-08-16" })).toBe(true);
    expect(ok({ source_url: "https://a.b/c", acquired_at: "2026-08-16T12:30" })).toBe(true);
    expect(ok({ source_url: "https://a.b/c", acquired_at: "вчера" })).toBe(false);
  });

  test("пустые необязательные поля не мешают проверке", () => {
    expect(
      ok({ source_url: "https://a.b/c", publisher: "", notes: "", rights: "" }),
    ).toBe(true);
  });
});

describe("расхождение заявленной даты", () => {
  test("конфликт измеряется в днях и не разрешается автоматически", () => {
    const delta = claimedDateDelta("2014-03-20", "2014-03-18");
    expect(delta).toEqual({ days: 2, conflict: true });
  });

  test("совпадение конфликтом не считается", () => {
    expect(claimedDateDelta("2014-03-18", "2014-03-18")?.conflict).toBe(false);
  });

  test("без одной из дат сравнение не выполняется", () => {
    // Отсутствие даты — не повод объявить расхождение нулевым.
    expect(claimedDateDelta(undefined, "2014-03-18")).toBeNull();
    expect(claimedDateDelta("2014-03-18", null)).toBeNull();
  });
});
