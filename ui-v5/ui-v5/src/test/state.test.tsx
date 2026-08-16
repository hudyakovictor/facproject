import { beforeEach, describe, expect, test } from "vitest";
import { useAnalysisStore, DEFAULT_VISIBLE_METRICS } from "../shared/state/analysisStore";
import { toSearchParams, validateAnalysisSearch } from "../shared/state/urlState";
import { collectContractIssues, missingFields } from "../shared/api/contract";
import { blindAlias, frameLabel, frameTitle } from "../shared/blind";
import type { ResearchPhoto } from "../shared/researchApi";

/**
 * Проверки общего состояния и контракта полей.
 *
 * Эти сценарии соответствуют дефектам BUG-1 (состояние шапки не доходило до
 * экранов), инварианту 5 (запрет межбиновых пар) и требованию §4 ТЗ о
 * воспроизводимости экрана по ссылке.
 */

const initial = useAnalysisStore.getState();

beforeEach(() => {
  useAnalysisStore.setState(initial, true);
});

const photo = (over: Partial<ResearchPhoto> = {}): ResearchPhoto => ({
  id: "p1",
  date: "2020-01-01",
  t: 0.5,
  bucket: "frontal",
  era: "2020-2026",
  quality: 0.8,
  yaw: 1,
  pitch: 2,
  roll: 3,
  fuzzy: "",
  measurementStatus: "compared",
  flags: [],
  sourceMode: "research",
  analysisStage: "stage2",
  boneScore: 0.7,
  p0: 0.1,
  p1: 0.2,
  p2: 0.3,
  ...over,
});

describe("общий стор анализа", () => {
  test("умолчания соответствуют каноническому справочнику бинов", () => {
    const state = useAnalysisStore.getState();
    expect(state.activePose).toBe("frontal");
    expect(state.multiPose).toBe(false);
    expect(state.visibleMetrics).toEqual(DEFAULT_VISIBLE_METRICS);
  });

  test("первый выбранный кадр становится A", () => {
    const rejection = useAnalysisStore
      .getState()
      .assignToPair("a", "frontal", () => "frontal");
    expect(rejection).toBeNull();
    expect(useAnalysisStore.getState().pairA).toBe("a");
    expect(useAnalysisStore.getState().pairB).toBeNull();
  });

  test("инвариант 5: пара из разных бинов ракурса отвергается с причиной", () => {
    const buckets: Record<string, string> = { a: "frontal", b: "left_profile" };
    const store = useAnalysisStore.getState();
    store.assignToPair("a", "frontal", (id) => buckets[id]);
    const rejection = useAnalysisStore
      .getState()
      .assignToPair("b", "left_profile", (id) => buckets[id]);

    expect(rejection).toMatch(/разным бинам ракурса/);
    // Отказ не должен молча назначить B: иначе запрет обходится повторным кликом.
    expect(useAnalysisStore.getState().pairB).toBeNull();
  });

  test("пара внутри одного бина принимается", () => {
    const buckets: Record<string, string> = { a: "left_mid", b: "left_mid" };
    const store = useAnalysisStore.getState();
    store.assignToPair("a", "left_mid", (id) => buckets[id]);
    const rejection = useAnalysisStore
      .getState()
      .assignToPair("b", "left_mid", (id) => buckets[id]);
    expect(rejection).toBeNull();
    expect(useAnalysisStore.getState().pairB).toBe("b");
  });

  test("swapPair меняет местами A и B", () => {
    useAnalysisStore.setState({ pairA: "a", pairB: "b" });
    useAnalysisStore.getState().swapPair();
    expect(useAnalysisStore.getState()).toMatchObject({ pairA: "b", pairB: "a" });
  });

  test("toggleMetric снимает и возвращает дорожку", () => {
    useAnalysisStore.getState().toggleMetric("quality");
    expect(useAnalysisStore.getState().visibleMetrics).not.toContain("quality");
    useAnalysisStore.getState().toggleMetric("quality");
    expect(useAnalysisStore.getState().visibleMetrics).toContain("quality");
  });
});

describe("состояние в строке запроса", () => {
  test("умолчания не попадают в URL", () => {
    expect(toSearchParams(useAnalysisStore.getState())).toEqual({});
  });

  test("изменённые значения кодируются", () => {
    useAnalysisStore.setState({
      activePose: "right_deep",
      qualityThreshold: 0.6,
      findingsMode: true,
      pairA: "x",
      blindMode: true,
    });
    expect(toSearchParams(useAnalysisStore.getState())).toEqual({
      pose: "right_deep",
      q: 0.6,
      findings: true,
      a: "x",
      blind: true,
    });
  });

  test("повреждённый параметр не роняет навигацию, а отбрасывается", () => {
    expect(validateAnalysisSearch({ q: "не число" })).toEqual({});
    expect(validateAnalysisSearch({ q: "0.5" })).toMatchObject({ q: 0.5 });
  });

  test("неизвестная метрика в URL игнорируется", () => {
    const parsed = validateAnalysisSearch({ metrics: "quality,вымышленная,yaw" });
    expect(parsed.metrics).toEqual(["quality", "yaw"]);
  });

  test("булев параметр принимается и как 1, и как true", () => {
    expect(validateAnalysisSearch({ blind: "1" }).blind).toBe(true);
    expect(validateAnalysisSearch({ blind: "false" }).blind).toBe(false);
  });
});

describe("зеркало контракта полей ui_fields.py", () => {
  test("полная запись Stage 2 не нарушает контракт", () => {
    expect(missingFields(photo())).toEqual([]);
  });

  test("строка Stage 1 сообщает об отсутствии boneScore и p0–p2", () => {
    const row = photo({ boneScore: null, p0: null, p1: null, p2: null });
    expect(missingFields(row)).toEqual(["boneScore", "p0", "p1", "p2"]);
  });

  test("ноль — законная величина метрики, а не отсутствие поля", () => {
    expect(missingFields(photo({ quality: 0, boneScore: 0 }))).toEqual([]);
  });

  test("при отсутствии серверной сводки проверка считается на клиенте", () => {
    const issues = collectContractIssues([photo(), photo({ id: "p2", p0: null })]);
    expect(issues.computedLocally).toBe(true);
    expect(issues.completeCount).toBe(1);
    expect(issues.violationsByField).toEqual({ p0: 1 });
  });

  test("серверная сводка имеет приоритет над клиентской", () => {
    const issues = collectContractIssues([photo()], {
      completeCount: 0,
      violationsByField: { boneScore: 1 },
    });
    expect(issues.computedLocally).toBe(false);
    expect(issues.violationsByField).toEqual({ boneScore: 1 });
  });
});

describe("слепой режим", () => {
  test("псевдоним устойчив и читается вслух", () => {
    expect(blindAlias("DEEPUTIN_2014_0301_007", 0)).toBe("КАДР-001");
    expect(blindAlias("DEEPUTIN_2014_0301_007", 41)).toBe("КАДР-042");
  });

  test("в обычном режиме подпись — дата, в слепом — псевдоним", () => {
    const frame = { id: "DEEPUTIN_2014_0301_007", date: "2014-03-01", order: 2 };
    expect(frameLabel(frame, false)).toBe("2014-03-01");
    expect(frameLabel(frame, true)).toBe("КАДР-003");
  });

  test("слепая подпись не содержит ни даты, ни идентификатора", () => {
    const frame = { id: "DEEPUTIN_2014_0301_007", date: "2014-03-01", order: 0 };
    const title = frameTitle(frame, true);
    expect(title).not.toContain("2014");
    expect(title).not.toContain("DEEPUTIN");
  });

  test("кадр без даты в обычном режиме подписан идентификатором, а не пустотой", () => {
    expect(frameLabel({ id: "p9", date: null, order: 0 }, false)).toBe("p9");
  });
});
