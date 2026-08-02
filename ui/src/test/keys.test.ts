import { describe, expect, it } from "vitest";
import {
  commonPrefix, filledCount, flattenKeys, formatKeyValue, groupTitle, isLongValue, keyLabel,
  keyTone, CATEGORY_ORDER,
} from "../keys";
import { NO_DATA } from "../format";

describe("подписи ключей", () => {
  it("снимает общий префикс группы", () => {
    const keys = ["mesh_point_to_plane_rmse", "mesh_point_to_plane_median", "mesh_point_to_plane_p95"];
    const prefix = commonPrefix(keys);
    expect(prefix).toBe("mesh_point_to_plane_");
    expect(keyLabel(keys[0], prefix)).toBe("rmse");
  });

  it("не снимает префикс, когда ключ один", () => {
    expect(commonPrefix(["mesh_status"])).toBe("");
  });

  it("не снимает префикс, если группа разнородна", () => {
    expect(commonPrefix(["mesh_rmse", "texture_status"])).toBe("");
  });

  it("никогда не оставляет подпись пустой", () => {
    const keys = ["quality_limited", "quality_limited_extra"];
    const prefix = commonPrefix(keys);
    for (const key of keys) expect(keyLabel(key, prefix).length).toBeGreaterThan(0);
  });

  it("подставляет идентификатор для неизвестной подгруппы", () => {
    expect(groupTitle("brand_new_group")).toBe("brand new group");
  });
});

describe("форматирование значений", () => {
  it("показывает отсутствие данных прочерком, а не нулём", () => {
    expect(formatKeyValue(null)).toBe(NO_DATA);
    expect(formatKeyValue(null)).not.toBe("0");
  });

  it("сохраняет настоящий ноль", () => {
    expect(formatKeyValue(0)).toBe("0");
  });

  it("не превращает мелкие q-value в 0.0000", () => {
    expect(formatKeyValue(0.00004)).toBe("4.00e-5");
  });

  it("целые числа без дробной части", () => {
    expect(formatKeyValue(23)).toBe("23");
  });

  it("длинный хэш помечается как длинное значение", () => {
    expect(isLongValue("a".repeat(64))).toBe(true);
    expect(isLongValue("frontal")).toBe(false);
  });
});

describe("тон значения", () => {
  it("ограничение калибровки — плохо", () => {
    expect(keyTone("calibration_limited", true)).toBe("bad");
    expect(keyTone("calibration_limited", false)).toBe("good");
  });

  it("применимость метрики — хорошо при true", () => {
    expect(keyTone("forehead_wrinkle_supported_a", true)).toBe("good");
  });

  it("статусная строка распознаётся", () => {
    expect(keyTone("mesh_status", "measured_uncalibrated")).toBe("warn");
    expect(keyTone("expression_qc_status", "calibrated_within_threshold")).toBe("good");
    expect(keyTone("status", "quality_limited")).toBe("bad");
  });

  it("числа не раскрашиваются: пороги задаёт пайплайн, не интерфейс", () => {
    expect(keyTone("mesh_rmse", 999)).toBe("neutral");
    expect(keyTone("primary_robust_z", -3)).toBe("neutral");
  });

  it("отсутствие данных нейтрально", () => {
    expect(keyTone("calibration_limited", null)).toBe("neutral");
  });
});

describe("уплощение вложенных ключей", () => {
  it("раскрывает три уровня Stage 1", () => {
    const flat = flattenKeys({ crop: { letterbox: { offset_x: 4 } } });
    expect(flat["crop.letterbox.offset_x"]).toBe(4);
  });

  it("массив становится строкой, а не теряется", () => {
    const flat = flattenKeys({ principal_point: [112, 112] });
    expect(flat.principal_point).toBe("112, 112");
  });

  it("пустой массив — это отсутствие данных", () => {
    expect(flattenKeys({ warnings: [] }).warnings).toBeNull();
  });

  it("null сохраняется как отсутствие, а не как ноль", () => {
    expect(flattenKeys({ a: { b: null } })["a.b"]).toBeNull();
  });

  it("NaN приводится к отсутствию данных", () => {
    expect(flattenKeys({ x: Number.NaN }).x).toBeNull();
  });
});

describe("счётчик заполненности", () => {
  it("считает только измеренные ключи", () => {
    expect(filledCount({ a: 1, b: null, c: "x", d: null })).toBe(2);
  });

  it("ноль считается измерением", () => {
    expect(filledCount({ a: 0, b: false })).toBe(2);
  });
});

describe("порядок категорий", () => {
  it("девять категорий, статзначимость первая", () => {
    expect(CATEGORY_ORDER).toHaveLength(9);
    expect(CATEGORY_ORDER[0]).toBe("A");
  });
});
