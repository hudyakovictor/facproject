import { describe, expect, it } from "vitest";
import {
  VERDICT_LABELS,
  applicability,
  flattenMetrics,
} from "../features/pair-analysis/applicability";
import {
  TINT_LABELS,
  formatMetric,
  groupMetrics,
  tintLevel,
} from "../features/pair-analysis/metricGroups";
import {
  ALTERNATIVES,
  PAIR_DECISIONS,
  buildPairReview,
  pairReviewBlockers,
} from "../features/pair-analysis/pairReview";
import { PairMetricsSchema, type PairMetrics } from "../shared/api/schemas";

/**
 * Тесты парного сравнения (§11).
 *
 * Данные — настоящая пара из `fixtures/public-sample/stage2_pairs.json`,
 * пропущенная через тот же категоризатор `key_catalog.categorize_pair_columns`,
 * что и backend. Проверяется главное: применимость решается до метрик, ни одна
 * колонка не теряется, а пропуск нигде не превращается в ноль.
 */

/** Ответ `/pairs/{a}/{b}/metrics` в форме, которую строит backend. */
function makeMetrics(overrides: Record<string, unknown> = {}): PairMetrics {
  const base = {
    pair_identity: {
      pair_id: "adjacent__2026_05_09_4__d1d553a1fe75__2026_05_13__13961b16e4b8",
      pose_bin: "frontal",
      photo_a: "2026_05_09_4__d1d553a1fe75",
      photo_b: "2026_05_13__13961b16e4b8",
    },
    source: {
      source_provenance_status_a: "not_provided",
      source_provenance_status_b: "not_provided",
    },
    reproducibility: { analysis_space: "raw_object_normalized" },
    date: { date_provenance_limited: false },
    duplicates: { near_duplicate_pair: false },
  };

  return PairMetricsSchema.parse({
    schema: "deeputin-api-pair-metrics-v1.0",
    not_a_verdict: true,
    source_mode: "research",
    photo_a: "2026_05_09_4__d1d553a1fe75",
    photo_b: "2026_05_13__13961b16e4b8",
    reversed_order: false,
    column_count: 24,
    available_count: 22,
    category_titles: {
      A: { ru: "Статзначимость", en: "Statistical significance" },
      G: { ru: "Провенанс", en: "Provenance" },
    },
    categories: {
      G: base,
      A: {
        header: { status: "coherent_jump_candidate", evidence_state: "coherent_jump_candidate" },
        primary: {
          primary_robust_z: 25.708491334830967,
          primary_calibration_p95: 0.012928783148527141,
          matched_calibration_sets: 7,
        },
        multiple_testing: { mt_q_value: 0.0, mt_significant_fdr10: true },
        limits: { calibration_limited: false, calibration_limitation_reason: null },
      },
      D: {
        anchors: { ldm134_rmse: 0.06627561151981354, ldm134_p95: 0.13332703113555908 },
        coverage: { common_visible106: 56, common_visible134: 77, coverage106: 0.5283018867924528 },
        residual_transform: { pose_distance: 0.3915147063119323 },
      },
      F: { identity_vs_expression: { identity_only_ldm134_rmse: 0.02483510412275791, alpha_id_l2: 4.05 } },
      B: { point_to_point: { mesh_rmse: 0.024052590131759644 }, status: { mesh_status: "measured_uncalibrated" } },
      E: { status: { texture_image_status: "measured" } },
      C: {
        frame_quality: { quality_gate_accepted: true, quality_limited: false, quality_stratum: "low" },
        expression: {
          expression_gate_jaw_mismatch: false,
          expression_gate_smile_mismatch: false,
          expression_gate_multiplier: 1.0,
        },
      },
      I: {
        other: {
          yaw_gap_deg: null,
          pitch_gap_deg: null,
          roll_gap_deg: null,
          pose_gap_reason: null,
          visibility_gate_accepted106: true,
          visibility_gate_accepted134: true,
          visibility_gate_required134: 30,
          smile_detected_a: false,
          ...(overrides.other as Record<string, unknown> | undefined),
        },
      },
      ...(overrides.categories as Record<string, unknown> | undefined),
    },
  });
}

/** Точечная подмена одной колонки внутри готового ответа. */
function withColumn(column: string, value: unknown, category = "C", group = "frame_quality"): PairMetrics {
  const data = makeMetrics();
  const categories = data.categories as Record<string, Record<string, Record<string, unknown>>>;
  categories[category] = categories[category] ?? {};
  categories[category][group] = { ...(categories[category][group] ?? {}), [column]: value };
  return data;
}

describe("плоский доступ к колонкам", () => {
  it("собирает все колонки из всех категорий", () => {
    const flat = flattenMetrics(makeMetrics());
    expect(flat.get("pose_bin")).toBe("frontal");
    expect(flat.get("primary_robust_z")).toBeCloseTo(25.7085, 3);
    expect(flat.get("yaw_gap_deg")).toBeNull();
  });
});

describe("карточка применимости", () => {
  it("перечисляет условия §11.5 в заданном порядке", () => {
    expect(applicability(makeMetrics()).checks.map((check) => check.id)).toEqual([
      "same-bin",
      "pose-gap",
      "common-points",
      "calibration",
      "quality",
      "expression",
      "provenance",
      "duplicates",
      "space",
    ]);
  });

  it("отсутствие сайдкара ограничивает применимость, а не проходит как «конфликта нет»", () => {
    const result = applicability(makeMetrics());
    const provenance = result.checks.find((check) => check.id === "provenance")!;
    expect(provenance.verdict).toBe("limited");
    expect(provenance.reason).toMatch(/не приложен/);
    expect(result.verdict).toBe("limited");
  });

  it("непройденный порог качества исключает пару целиком", () => {
    const result = applicability(withColumn("quality_gate_accepted", false));
    expect(result.checks.find((check) => check.id === "quality")!.verdict).toBe("excluded");
    expect(result.verdict).toBe("excluded");
    expect(result.summary).toMatch(/непригодны/);
  });

  it("дубликат пары исключает сравнение", () => {
    const result = applicability(withColumn("near_duplicate_pair", true, "G", "duplicates"));
    expect(result.checks.find((check) => check.id === "duplicates")!.verdict).toBe("excluded");
    expect(result.verdict).toBe("excluded");
  });

  it("непройденный порог видимости исключает пару", () => {
    const result = applicability(
      withColumn("visibility_gate_accepted134", false, "I", "other"),
    );
    expect(result.checks.find((check) => check.id === "common-points")!.verdict).toBe("excluded");
  });

  it("различие мимики ограничивает, но не исключает", () => {
    const result = applicability(
      withColumn("expression_gate_jaw_mismatch", true, "C", "expression"),
    );
    const expression = result.checks.find((check) => check.id === "expression")!;
    expect(expression.verdict).toBe("limited");
    expect(expression.reason).toMatch(/челюсть/);
  });

  it("неполная калибровка ограничивает выводы", () => {
    const data = withColumn("calibration_limited", true, "A", "limits");
    const result = applicability(data);
    expect(result.checks.find((check) => check.id === "calibration")!.verdict).toBe("limited");
  });

  it("итог «принято» говорит об измеримости, а не о личности", () => {
    const data = makeMetrics();
    const categories = data.categories as Record<string, Record<string, Record<string, unknown>>>;
    categories.G.source = { source_provenance_status_a: "verified", source_provenance_status_b: "verified" };
    const result = applicability(data);
    expect(result.verdict).toBe("accepted");
    expect(result.summary).toMatch(/не о личности/);
  });

  it("одно «исключено» перевешивает любое число «принято»", () => {
    const data = withColumn("quality_gate_accepted", false);
    const result = applicability(data);
    expect(result.checks.filter((check) => check.verdict === "accepted").length).toBeGreaterThan(3);
    expect(result.verdict).toBe("excluded");
  });

  it("подписи решений переведены", () => {
    expect(VERDICT_LABELS.excluded).toBe("исключено");
    expect(VERDICT_LABELS.unknown).toBe("нет данных");
  });
});

describe("группировка метрик §11.6", () => {
  const data = makeMetrics();
  const groups = groupMetrics(data);

  it("не теряет ни одной колонки", () => {
    const total = groups.reduce((sum, group) => sum + group.rows.length, 0);
    const flat = flattenMetrics(data);
    expect(total).toBe(flat.size);
  });

  it("не дублирует колонки между группами", () => {
    const seen = groups.flatMap((group) => group.rows.map((row) => row.column));
    expect(new Set(seen).size).toBe(seen.length);
  });

  it("раскладывает по группам спеки", () => {
    const titles = groups.map((group) => group.title);
    expect(titles).toContain("Первичные точки");
    expect(titles).toContain("Только идентичность");
    expect(titles).toContain("Меш");
    expect(titles).toContain("Статистическая значимость");
  });

  it("забирает пороги видимости и разрывы углов из backend-категории «прочее»", () => {
    const primary = groups.find((group) => group.id === "primary-landmarks")!;
    const columns = primary.rows.map((row) => row.column);
    expect(columns).toContain("visibility_gate_accepted134");
    expect(columns).toContain("yaw_gap_deg");
    expect(groups.some((group) => group.id === "other")).toBe(false);
  });

  it("считает измеренные колонки отдельно от пропусков", () => {
    const primary = groups.find((group) => group.id === "primary-landmarks")!;
    expect(primary.measured).toBeLessThan(primary.rows.length);
    expect(primary.rows.some((row) => row.value === null)).toBe(true);
  });
});

describe("форматирование значений", () => {
  const row = (value: unknown) => ({
    column: "x",
    value,
    category: "A",
    group: "g",
    unit: null,
    tooltip: null,
  }) as Parameters<typeof formatMetric>[0];

  it("пропуск остаётся «н/д», а не нулём", () => {
    expect(formatMetric(row(null))).toBe("н/д");
    expect(formatMetric(row(0))).toBe("0");
  });

  it("булево читается словами", () => {
    expect(formatMetric(row(true))).toBe("да");
    expect(formatMetric(row(false))).toBe("нет");
  });

  it("очень малые значения не округляются в ноль", () => {
    expect(formatMetric(row(0.0000123))).toBe("1.23e-5");
    expect(formatMetric(row(0.06627561151981354))).toBe("0.0663");
  });
});

describe("A-relative подсветка §11.3", () => {
  it("без калибровочного порога уровень неизвестен, а не «малый»", () => {
    expect(tintLevel(0.5, null, true)).toBe("unknown");
    expect(tintLevel(0.5, 0, true)).toBe("unknown");
  });

  it("неизмеренное значение не красится", () => {
    expect(tintLevel(null, 1, true)).toBe("unknown");
  });

  it("неприменимый кадр помечается отдельно от неизмеренного", () => {
    expect(tintLevel(0.5, 1, false)).toBe("inapplicable");
    expect(TINT_LABELS.inapplicable).toBe("неприменимо");
  });

  it("уровни считаются по отношению к порогу", () => {
    expect(tintLevel(0.9, 1, true)).toBe("near");
    expect(tintLevel(2, 1, true)).toBe("moderate");
    expect(tintLevel(10, 1, true)).toBe("far");
  });

  it("ни одна подпись не говорит о личности", () => {
    for (const label of Object.values(TINT_LABELS)) {
      expect(label).not.toMatch(/личност|совпаден|тот же|identity/i);
    }
  });
});

describe("рецензирование пары §11.10", () => {
  it("в решениях нет суждений о личности", () => {
    for (const decision of PAIR_DECISIONS) {
      expect(decision.label).not.toMatch(/тот же человек|разные люди|личност/i);
    }
  });

  it("кандидат без двух проверенных альтернатив не сохраняется", () => {
    expect(
      pairReviewBlockers({
        decision: "candidate",
        observation: "смещение линии челюсти между кадрами",
        reviewer: "эксперт",
        alternatives: ["pose"],
      }),
    ).toContain("для кандидата нужно отметить минимум две проверенные альтернативы");
  });

  it("с двумя альтернативами кандидат допустим", () => {
    expect(
      pairReviewBlockers({
        decision: "candidate",
        observation: "смещение линии челюсти между кадрами",
        reviewer: "эксперт",
        alternatives: ["pose", "expression"],
      }),
    ).toEqual([]);
  });

  it("наблюдение обязательно описать словами", () => {
    expect(
      pairReviewBlockers({
        decision: "inconclusive",
        observation: "ок",
        reviewer: "эксперт",
        alternatives: [],
      }),
    ).toContain("наблюдение должно быть описано словами");
  });

  it("перечень альтернатив покрывает основные ложные объяснения", () => {
    const ids = ALTERNATIVES.map((item) => item.id);
    expect(ids).toContain("pose");
    expect(ids).toContain("expression");
    expect(ids).toContain("lighting");
    expect(ids).toContain("aging");
  });

  it("карточка пары собирается воспроизводимо", () => {
    const record = buildPairReview({
      photoA: "a",
      photoB: "b",
      decision: "limited",
      observation: "  различие в пределах калибровки  ",
      confidence: "medium",
      alternatives: ["pose", "expression"],
      reviewer: "  эксперт  ",
      secondReviewer: "",
      now: new Date("2026-08-16T12:00:00Z"),
    });
    expect(record).toEqual({
      schema: "deeputin-ui-pair-review-v1",
      photo_a: "a",
      photo_b: "b",
      decision: "limited",
      observation: "различие в пределах калибровки",
      confidence: "medium",
      alternatives_checked: ["expression", "pose"],
      reviewer: "эксперт",
      second_reviewer: null,
      created_at: "2026-08-16T12:00:00.000Z",
    });
  });
});
