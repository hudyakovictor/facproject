import { describe, expect, it, beforeEach } from "vitest";
import { t, getLanguage, setLanguage } from "../i18n";

describe("i18n", () => {
  beforeEach(() => setLanguage("ru"));

  it("defaults to Russian", () => {
    expect(getLanguage()).toBe("ru");
    expect(t.appName).toBe("DEEPUTIN");
    expect(t.tabGeometry).toBe("ГЕОМЕТРИЯ");
  });

  it("switches live to English without re-import", () => {
    expect(t.tabGeometry).toBe("ГЕОМЕТРИЯ");
    setLanguage("en");
    expect(getLanguage()).toBe("en");
    expect(t.tabGeometry).toBe("GEOMETRY");
    setLanguage("ru");
    expect(t.tabGeometry).toBe("ГЕОМЕТРИЯ");
  });

  it("keeps technical contract keys (H0/H1/H2, ERA_* ids) untranslated", () => {
    setLanguage("en");
    expect(Object.keys(t.hypothesisShort)).toEqual(["H0", "H1", "H2"]);
    expect(Object.keys(t.fuzzy)).toContain("IDENTITY_ANOMALY");
    setLanguage("ru");
  });

  it("mirrors every key between ru and en dictionaries", () => {
    setLanguage("ru");
    const ruKeys = new Set(Object.keys(t));
    setLanguage("en");
    const enKeys = new Set(Object.keys(t));
    setLanguage("ru");
    expect([...ruKeys].sort()).toEqual([...enKeys].sort());
  });

  it("function-valued entries (e.g. flagChinProj) work in both languages", () => {
    setLanguage("ru");
    expect(t.flagChinProj(2.5)).toContain("подбородка");
    setLanguage("en");
    expect(t.flagChinProj(2.5)).toContain("chin");
    setLanguage("ru");
  });
});
