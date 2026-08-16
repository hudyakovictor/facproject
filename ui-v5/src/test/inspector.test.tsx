import { describe, expect, it } from "vitest";
import {
  CATEGORY_ORDER,
  categorizeKey,
  flattenInfo,
  formatLeafValue,
  groupByCategory,
  shortenHash,
} from "../features/photo-inspector/infoKeys";
import {
  EXPECTED_ARTIFACTS,
  artifactCompleteness,
  compactFacts,
  dateState,
  faceAreaPx,
  limitations,
} from "../features/photo-inspector/compactFacts";
import { buildReview, reviewBlockers } from "../features/photo-inspector/review";
import { LAYERS } from "../features/photo-inspector/layers";
import type { PhotoInfoKeys } from "../shared/api/schemas";

/**
 * Тесты инспектора кадра (§10).
 *
 * Проверяется главное свойство страницы: отсутствующее измерение остаётся
 * отсутствующим. Ноль, пустая строка и «0%» вместо пропуска — именно та подмена,
 * которую запрещает `app6/AGENTS.md`, и поймать её должен тест, а не рецензент.
 */

/** Фрагмент настоящего `info.json` из `fixtures/public-sample`. */
const REAL_INFO: Record<string, unknown> = {
  photo_id: "1998_01_01__9714228198ba",
  date: "1998-01-01",
  schema_version: "deeputin-stage1-v2.4",
  source_digest: "9714228198ba28f148665f6523fd145c072579adbbacf4e71c8331ac13e14c8a",
  perceptual_dhash: "9e98e9f8dcdcd8f0",
  near_duplicate_of: null,
  source_filename: "1998_01_01.jpg",
  source_provenance: { sidecar_digest: null, sidecar_path: null, status: "not_provided" },
  date_provenance: {
    authority: "filename",
    conflict_sources: [],
    delta_days: null,
    exif_date: null,
    filename_date: "1998-01-01",
    policy: "EXIF/source claims corroborate but never override filename chronology",
  },
  pose: {
    canonical_yaw: -17.5,
    pitch: 16.61952018737793,
    roll: -6.5660624504089355,
    yaw: -13.421525001525879,
    pose_bin: "left_light",
  },
  reprojection: {
    ldm106_224: { max: 0.0, p95: 0.0, rmse: 0.0 },
    ldm134_224: { max: 0.0, p95: 0.0, rmse: 0.0 },
  },
  crop: {
    bbox_original: [74, 188, 515, 458],
    crop_source: "ldm106_projection",
  },
  image: { decode: { encoded_mode: "RGB", encoded_size: [654, 654], exif_orientation: 1 } },
  skin_quality_status: "high",
  skin_quality_score: 0.81,
  skin_authenticity_status: "high_authenticity",
  skin_authenticity_score: 0.77,
  landmark_contract: { raw: "object identity+expression", aligned: "full-mesh RMS", chronology: "full pose correction" },
  chronology: {
    visible_landmarks_106: 63,
    visible_landmarks_134: 90,
    expression_magnitude: 8.411263465881348,
  },
  quality_inputs: { combined_visible_fraction: 0.619759724439217 },
  skin: { hard_stop: false, hard_stop_reason: null, state: "success" },
};

function makeData(overrides: Partial<PhotoInfoKeys> = {}): PhotoInfoKeys {
  return {
    photo_id: "1998_01_01__9714228198ba",
    info: REAL_INFO,
    validation: { status: "complete", errors: [], warnings: [] },
    texture: { schema: "deeputin-texture-v1", model: "3ddfa_v3", source: "original_pixels" },
    artifacts: [...EXPECTED_ARTIFACTS],
    ...overrides,
  } as PhotoInfoKeys;
}

describe("категоризация ключей info.json", () => {
  it("относит провенанс, хронологию и артефакты к разным категориям", () => {
    expect(categorizeKey("source_digest")).toBe("G");
    expect(categorizeKey("date_provenance.authority")).toBe("G");
    expect(categorizeKey("chronology.index")).toBe("F");
    expect(categorizeKey("pose.yaw")).toBe("C");
    expect(categorizeKey("landmark_contract.raw")).toBe("D");
    expect(categorizeKey("uv.area")).toBe("E");
    expect(categorizeKey("files.mesh_obj")).toBe("H");
  });

  it("неизвестный ключ не теряется, а попадает в артефакты кадра", () => {
    expect(categorizeKey("совершенно_новый_ключ")).toBe("H");
    expect(CATEGORY_ORDER).toContain("H");
  });
});

describe("развёртка вложенного JSON", () => {
  const leaves = flattenInfo(REAL_INFO);

  it("доходит до листьев через точку", () => {
    const paths = leaves.map((leaf) => leaf.path);
    expect(paths).toContain("pose.yaw");
    expect(paths).toContain("image.decode.encoded_size.0");
    expect(paths).toContain("date_provenance.authority");
  });

  it("сохраняет null как null, а не как ноль или пустую строку", () => {
    const dup = leaves.find((leaf) => leaf.path === "near_duplicate_of");
    expect(dup?.value).toBeNull();
    expect(dup?.kind).toBe("null");
    expect(formatLeafValue(dup!)).toBe("н/д");
  });

  it("отличает пустой список от отсутствия", () => {
    const conflicts = leaves.find((leaf) => leaf.path === "date_provenance.conflict_sources");
    expect(conflicts?.value).toBe("пустой список");
  });

  it("сворачивает длинные массивы, показывая их длину", () => {
    const flat = flattenInfo({ vertices: Array.from({ length: 500 }, (_, i) => i) });
    expect(flat).toHaveLength(1);
    expect(flat[0].value).toBe("список из 500 значений");
  });

  it("группирует по категориям в фиксированном порядке", () => {
    const groups = groupByCategory(leaves);
    const order = groups.map((group) => group.category);
    expect(order).toEqual(CATEGORY_ORDER.filter((category) => order.includes(category)));
    expect(groups.every((group) => group.leaves.length > 0)).toBe(true);
  });
});

describe("сокращение хешей", () => {
  it("оставляет начало и конец, короткие значения не трогает", () => {
    const digest = String(REAL_INFO.source_digest);
    expect(shortenHash(digest, 10)).toBe("9714228198…ac13e14c8a");
    expect(shortenHash("abc")).toBe("abc");
  });
});

describe("площадь лица", () => {
  it("считается по рамке в исходных пикселях и даёт долю кадра", () => {
    const area = faceAreaPx(REAL_INFO);
    expect(area).not.toBeNull();
    expect(area!.width).toBe(441);
    expect(area!.height).toBe(270);
    expect(area!.share).toBeCloseTo((441 * 270) / (654 * 654), 5);
  });

  it("без рамки возвращает null, а не нулевую площадь", () => {
    expect(faceAreaPx({})).toBeNull();
    expect(faceAreaPx({ crop: { bbox_original: [1, 2] } })).toBeNull();
  });
});

describe("полнота артефактов", () => {
  it("считает недостающие файлы относительно ожидаемого набора", () => {
    const partial = artifactCompleteness(["original.jpg", "info.json", "странный.bin"]);
    expect(partial.present).toEqual(["original.jpg", "info.json"]);
    expect(partial.missing).toContain("mesh.obj");
    expect(partial.extra).toEqual(["странный.bin"]);
    expect(partial.ratio).toBe(`2 из ${EXPECTED_ARTIFACTS.length}`);
  });

  it("полный набор не считается неполным", () => {
    const full = artifactCompleteness([...EXPECTED_ARTIFACTS]);
    expect(full.missing).toEqual([]);
  });
});

describe("компактные факты", () => {
  const facts = compactFacts(makeData());
  const byKey = (key: string) => facts.find((fact) => fact.key === key)!;

  it("магнитуда выражения читается из реального ключа", () => {
    expect(byKey("expression").value).toBe("магнитуда 8.41");
  });

  it("покрывают все пункты §10.3", () => {
    expect(facts.map((fact) => fact.key)).toEqual([
      "pose",
      "dimensions",
      "face-area",
      "reprojection",
      "visible",
      "quality",
      "authenticity",
      "expression",
      "artifacts",
      "date-state",
    ]);
  });

  it("показывают позу и размеры из реальных ключей", () => {
    expect(byKey("pose").value).toContain("yaw -13.4°");
    expect(byKey("dimensions").value).toBe("654 × 654 px");
  });

  it("показывает число видимых точек из хронологического пространства", () => {
    const visible = byKey("visible");
    expect(visible.value).toBe("63 из 106 · 90 из 134");
    expect(visible.hint).toContain("62.0%");
    expect(visible.warn).toBe(false);
  });

  it("предупреждает, когда видна меньшая часть точек", () => {
    const scarce = compactFacts(
      makeData({
        info: { ...REAL_INFO, chronology: { visible_landmarks_106: 20, visible_landmarks_134: 30 } },
      }),
    );
    expect(scarce.find((fact) => fact.key === "visible")!.warn).toBe(true);
  });

  it("отсутствующее измерение остаётся «н/д», а не нулём", () => {
    const bare = compactFacts(makeData({ info: { photo_id: "x" } }));
    for (const fact of bare) expect(fact.value === null || typeof fact.value === "string").toBe(true);
    expect(bare.find((fact) => fact.key === "visible")!.value).toBeNull();
    expect(bare.find((fact) => fact.key === "pose")!.value).toBeNull();
  });

  it("аутентичность кожи сопровождается оговоркой «НЕ ВЕРДИКТ»", () => {
    expect(byKey("authenticity").hint).toContain("НЕ ВЕРДИКТ");
  });

  it("отсутствие сайдкара помечается как требующее внимания", () => {
    expect(byKey("date-state").warn).toBe(true);
  });

  it("неполный набор артефактов помечается предупреждением", () => {
    const partial = compactFacts(makeData({ artifacts: ["original.jpg", "info.json"] }));
    const artifacts = partial.find((fact) => fact.key === "artifacts")!;
    expect(artifacts.warn).toBe(true);
    expect(artifacts.hint).toMatch(/нет:/);
  });
});

describe("ограничения применимости", () => {
  it("называют авторитет даты и отсутствие сайдкара", () => {
    const notes = limitations(makeData());
    expect(notes.some((note) => note.includes("имени файла"))).toBe(true);
    expect(notes.some((note) => note.includes("сайдкар"))).toBe(true);
  });

  it("всегда напоминают, что кадр не даёт суждения о личности", () => {
    const notes = limitations(makeData());
    expect(notes[notes.length - 1]).toMatch(/не являются суждением о личности/);
  });

  it("сообщают о дубликате и об ошибках валидации", () => {
    const notes = limitations(
      makeData({
        info: { ...REAL_INFO, near_duplicate_of: "1998_01_02__aaaa" },
        validation: { status: "failed", errors: ["меш не построен"], warnings: [] },
      }),
    );
    expect(notes.some((note) => note.includes("1998_01_02__aaaa"))).toBe(true);
    expect(notes.some((note) => note.includes("меш не построен"))).toBe(true);
  });
});

describe("состояние даты", () => {
  it("возвращает конфликт источников, когда он есть", () => {
    const state = dateState({
      date_provenance: { authority: "filename", conflict_sources: ["exif"], delta_days: 1200 },
    });
    expect(state.conflicts).toEqual(["exif"]);
    expect(state.deltaDays).toBe(1200);
  });

  it("отсутствие расхождения не превращается в ноль дней", () => {
    expect(dateState(REAL_INFO).deltaDays).toBeNull();
  });
});

describe("слои левой области", () => {
  it("перечисляют переключатели §10.2", () => {
    expect(LAYERS.map((layer) => layer.id)).toEqual([
      "original",
      "face_crop",
      "face_mask",
      "uv_texture",
      "landmarks",
      "visibility",
    ]);
  });

  it("кроп и маска помечены как чужая система координат", () => {
    const crop = LAYERS.find((layer) => layer.id === "face_crop")!;
    const mask = LAYERS.find((layer) => layer.id === "face_mask")!;
    expect(crop.inOriginalSpace).toBe(false);
    expect(mask.inOriginalSpace).toBe(false);
    expect(LAYERS.find((layer) => layer.id === "original")!.inOriginalSpace).toBe(true);
  });
});

describe("ручной контроль качества", () => {
  it("не даёт сохранить отклонение без причины", () => {
    expect(
      reviewBlockers({ decision: "reject_reconstruction", comment: "  ", reviewer: "эксперт" }),
    ).toContain("отклонение требует комментария с причиной");
  });

  it("принятие без комментария допустимо, но рецензент обязателен", () => {
    expect(reviewBlockers({ decision: "approve", comment: "", reviewer: "эксперт" })).toEqual([]);
    expect(reviewBlockers({ decision: "approve", comment: "", reviewer: "" })).toContain(
      "не указан рецензент",
    );
  });

  it("без решения сохранять нечего", () => {
    expect(reviewBlockers({ decision: null, comment: "", reviewer: "эксперт" })).toContain(
      "не выбрано решение",
    );
  });

  it("собирает запись отзыва отдельным слоем, не трогая Stage 1", () => {
    const record = buildReview({
      photoId: "1998_01_01__9714228198ba",
      decision: "needs_recrop",
      comment: "  рамка срезает подбородок  ",
      reviewer: "  эксперт  ",
      createsIssue: true,
      now: new Date("2026-08-16T10:00:00Z"),
    });
    expect(record).toEqual({
      schema: "deeputin-ui-review-v1",
      photo_id: "1998_01_01__9714228198ba",
      decision: "needs_recrop",
      comment: "рамка срезает подбородок",
      reviewer: "эксперт",
      created_at: "2026-08-16T10:00:00.000Z",
      creates_issue: true,
    });
  });
});
