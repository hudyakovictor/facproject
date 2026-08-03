import { describe, expect, it } from "vitest";
import {
  ANOMALY_KINDS, anomalyCounts, anomalyKind, collectAnomalies, isQualityFlag,
  nextAnomalyIndex, photoAnomalies, topSeverity,
} from "../anomalies";
import { type Photo } from "../data";
import { buildDemoPhotos } from "../demoData";

/** Демо-набор как тестовая фикстура: генератор вынесен из основного
 * бандла (аудит №27), поэтому строим его явно. */
const DEMO_PHOTOS = buildDemoPhotos();

const withFlags = (id: string, flags: string[]): Photo => ({ ...DEMO_PHOTOS[0], id, flags });

describe("anomaly taxonomy", () => {
  it("covers every flag the filter offers, each with its own icon", () => {
    // Регрессия: раньше на таймлайне рисовался 1 тип из 6.
    const ALL_FLAGS = ["IMPOSSIBLE_SHORT", "RETURN_TO_BASELINE", "TRANSITION",
      "TEXTURE_SPIKE", "TEMPORAL_IMPOSSIBILITY", "IDENTITY_ANOMALY"];
    for (const flag of ALL_FLAGS) {
      expect(ANOMALY_KINDS[flag], `нет описания для ${flag}`).toBeDefined();
    }
    const icons = ALL_FLAGS.map(f => ANOMALY_KINDS[f].icon);
    expect(new Set(icons).size).toBe(icons.length); // иконки различимы
  });

  it("degrades unknown backend flags instead of dropping them", () => {
    const kind = anomalyKind("SOME_NEW_BACKEND_FLAG");
    expect(kind.id).toBe("SOME_NEW_BACKEND_FLAG");
    expect(kind.labelKey).toBe("anomUnknown");
  });

  it("sorts a photo's flags with the most critical first", () => {
    const photo = withFlags("p", ["TRANSITION", "TEMPORAL_IMPOSSIBILITY", "TEXTURE_SPIKE"]);
    expect(photoAnomalies(photo).map(k => k.id)[0]).toBe("TEMPORAL_IMPOSSIBILITY");
    expect(topSeverity(photo)).toBe("critical");
  });

  it("reports no severity for a clean photo", () => {
    expect(topSeverity(withFlags("clean", []))).toBeNull();
  });

  it("collects only flagged frames, preserving their index", () => {
    const photos = [withFlags("a", []), withFlags("b", ["TRANSITION"]), withFlags("c", [])];
    const buckets = collectAnomalies(photos);
    expect(buckets).toHaveLength(1);
    expect(buckets[0].index).toBe(1);
  });

  it("navigates forward and backward, wrapping around", () => {
    const photos = [
      withFlags("a", ["TRANSITION"]), withFlags("b", []),
      withFlags("c", ["IDENTITY_ANOMALY"]), withFlags("d", []),
    ];
    const buckets = collectAnomalies(photos);   // индексы 0 и 2
    expect(nextAnomalyIndex(buckets, 0, 1)).toBe(2);
    expect(nextAnomalyIndex(buckets, 2, 1)).toBe(0);   // цикл вперёд
    expect(nextAnomalyIndex(buckets, 2, -1)).toBe(0);
    expect(nextAnomalyIndex(buckets, 0, -1)).toBe(2);  // цикл назад
    expect(nextAnomalyIndex([], 0, 1)).toBeNull();
  });

  it("counts flags per type for the legend, criticals first", () => {
    const photos = [
      withFlags("a", ["TRANSITION"]), withFlags("b", ["TRANSITION"]),
      withFlags("c", ["TEMPORAL_IMPOSSIBILITY"]),
    ];
    const stats = anomalyCounts(photos);
    expect(stats[0].kind.id).toBe("TEMPORAL_IMPOSSIBILITY");
    expect(stats.find(s => s.kind.id === "TRANSITION")!.count).toBe(2);
  });
});

describe("quality flags vs real anomalies", () => {
  it("covers the flags the demo backend actually emits", () => {
    // Найдено прогоном против API: 110 LOW_VISIBILITY + 58 EXPRESSION_ACTIVE.
    for (const flag of ["LOW_VISIBILITY", "EXPRESSION_ACTIVE"]) {
      expect(ANOMALY_KINDS[flag], `нет описания для ${flag}`).toBeDefined();
      expect(isQualityFlag(ANOMALY_KINDS[flag])).toBe(true);
    }
  });

  it("excludes applicability limits from the anomaly count", () => {
    const photos = [
      withFlags("a", ["LOW_VISIBILITY"]),
      withFlags("b", ["EXPRESSION_ACTIVE"]),
      withFlags("c", ["IDENTITY_ANOMALY"]),
    ];
    // Плохая видимость — не подмена личности: счётчик аномалий должен быть 1.
    expect(collectAnomalies(photos)).toHaveLength(1);
    expect(collectAnomalies(photos)[0].photo.id).toBe("c");
    // При явном запросе они доступны отдельно.
    expect(collectAnomalies(photos, true)).toHaveLength(3);
  });

  it("keeps quality flags visually distinct from identity anomalies", () => {
    expect(ANOMALY_KINDS.LOW_VISIBILITY.severity).toBe("quality");
    expect(isQualityFlag(ANOMALY_KINDS.IDENTITY_ANOMALY)).toBe(false);
  });
});
