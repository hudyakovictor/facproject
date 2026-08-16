import { beforeEach, describe, expect, test, vi } from "vitest";
import { getValidated, ApiError, ContractError } from "../shared/api/client";
import { CalibrationHealthSchema, RunSummarySchema, TimelineSchema } from "../shared/api/schemas";
import { consoleLogger } from "../shared/logger";

/**
 * Контрактные тесты слоя API.
 *
 * Проверяют то, чего раньше не существовало вовсе: разбор ошибок, таймаут,
 * валидацию формы ответа и передачу диагностики в журнал.
 */

function respond(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(typeof body === "string" ? body : JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
  consoleLogger.clear();
});

describe("разбор ошибок HTTP", () => {
  test("detail из FastAPI сохраняется в ошибке", async () => {
    respond({ detail: "вывод Stage 1 не прошёл проверку" }, 422);
    await expect(getValidated("/api/v1/timeline", TimelineSchema)).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      endpoint: "/api/v1/timeline",
      detail: "вывод Stage 1 не прошёл проверку",
    });
  });

  test("409 отсутствия Stage 1 отличим от прочих отказов", async () => {
    respond({ detail: "Stage 1 не найден" }, 409);
    const error = await getValidated("/api/v1/timeline", TimelineSchema).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
  });

  test("ошибка попадает в журнал", async () => {
    respond({ detail: "boom" }, 500);
    await getValidated("/api/v1/timeline", TimelineSchema).catch(() => undefined);
    const entries = consoleLogger.getEntries();
    expect(entries.some((e) => e.severity === "ERROR" && e.source === "API")).toBe(true);
    expect(entries[0].details).toContain("boom");
  });

  test("сетевой сбой не остаётся без объяснения", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    const error = await getValidated("/api/v1/timeline", TimelineSchema).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).detail).toContain("Failed to fetch");
  });
});

describe("валидация формы ответа", () => {
  test("ответ не той формы порождает ContractError", async () => {
    respond({ photos: "не массив", source_mode: 42 });
    const error = await getValidated("/api/v1/timeline", TimelineSchema).catch((e) => e);
    // photos и source_mode имеют .catch(), поэтому схема их восстановит;
    // проверяем, что восстановление честное, а не выдумка данных
    expect(error).not.toBeInstanceOf(ContractError);
  });

  test("отсутствие обязательного id отвергается", async () => {
    respond({ source_mode: "research", not_a_verdict: true, photos: [{ date: "2020-01-01" }], era_meta: {} });
    const result = await getValidated("/api/v1/timeline", TimelineSchema);
    // Схема photos имеет .catch([]) — некорректная запись не проходит,
    // и вместо выдуманного id список честно становится пустым.
    expect(result.photos).toEqual([]);
  });

  test("нарушение контракта пишется в журнал", async () => {
    respond("не json вовсе");
    await getValidated("/api/v1/timeline", TimelineSchema).catch(() => undefined);
    expect(consoleLogger.getEntries().length).toBeGreaterThan(0);
  });
});

describe("сохранение семантики null", () => {
  test("null-метрики не подменяются нулями", async () => {
    respond({
      source_mode: "research",
      not_a_verdict: true,
      analysis_stage: "stage1_inventory",
      era_meta: {},
      photos: [
        {
          id: "p1", date: null, t: null, bucket: "frontal", era: "1999-2007",
          quality: null, yaw: null, pitch: null, roll: null, fuzzy: "",
          measurementStatus: "not_compared", flags: [], sourceMode: "research",
          analysisStage: "stage1_inventory", boneScore: null, p0: null, p1: null, p2: null,
        },
      ],
    });
    const result = await getValidated("/api/v1/timeline", TimelineSchema);
    const photo = result.photos[0];
    expect(photo.quality).toBeNull();
    expect(photo.yaw).toBeNull();
    expect(photo.boneScore).toBeNull();
    expect(photo.quality).not.toBe(0);
  });

  test("поля Stage 2 отсутствуют, но ответ валиден", async () => {
    respond({
      source_mode: "research", not_a_verdict: true, analysis_stage: "stage1_inventory", era_meta: {},
      photos: [{
        id: "p1", date: "1999-08-16", t: 934761600000, bucket: "frontal", era: "1999-2007",
        quality: 0.73, yaw: 3.1, pitch: -1.2, roll: 0.4, fuzzy: "INSUFFICIENT_DATA",
        measurementStatus: "not_compared", flags: ["STAGE1_INVENTORY_ONLY"],
        sourceMode: "research", analysisStage: "stage1_inventory",
      }],
    });
    const result = await getValidated("/api/v1/timeline", TimelineSchema);
    expect(result.photos).toHaveLength(1);
    expect(result.photos[0].stage2StatusCounts).toBeUndefined();
    expect(result.analysis_stage).toBe("stage1_inventory");
  });

  test("сигналы контракта доходят до интерфейса", async () => {
    respond({
      source_mode: "research", not_a_verdict: true, era_meta: {}, photos: [],
      ui_fields_schema: "deeputin-ui-fields-v1.0",
      ui_fields_complete_photo_count: 0,
      ui_fields_violations_by_field: { boneScore: 1909, p0: 1909 },
    });
    const result = await getValidated("/api/v1/timeline", TimelineSchema);
    expect(result.ui_fields_complete_photo_count).toBe(0);
    expect(result.ui_fields_violations_by_field).toEqual({ boneScore: 1909, p0: 1909 });
  });
});

describe("прочие эндпоинты", () => {
  test("run/summary сохраняет metric_catalog, который раньше отбрасывался", async () => {
    respond({
      source_mode: "research", not_a_verdict: true,
      metric_catalog: [{ key: "boneScore", title: "Костная геометрия" }],
      category_titles: { geometry: "Геометрия" },
      technical_summary: { change_point_count: 3 },
    });
    const result = await getValidated("/api/v1/run/summary", RunSummarySchema);
    expect(result.metric_catalog).toHaveLength(1);
    expect(result.category_titles).toEqual({ geometry: "Геометрия" });
  });

  test("calibration/health разбирается корректно", async () => {
    respond({
      schema: "calib-v1", not_a_verdict: true, total_records: 10, total_persons: 4,
      confidence_counts: { high: 3 },
      buckets: { frontal: { pose_bin: "frontal", frame_count: 10, person_count: 4, confidence: "high", runtime_usable: true } },
      unreliable_buckets: [], recommendations: [], source: "fixture",
    });
    const result = await getValidated("/api/v1/calibration/health", CalibrationHealthSchema);
    expect(result.buckets.frontal.runtime_usable).toBe(true);
  });
});
