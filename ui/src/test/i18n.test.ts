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

/** Страж от накопления мёртвых ключей.
 *
 * На момент написания в словаре скопилось 34 ключа, не используемых ни
 * одним компонентом: остатки удалённых панелей и переименованных режимов.
 * Мёртвый ключ вреден не размером бандла, а тем, что при переводе на
 * новый язык его придётся переводить, и тем, что он выглядит как
 * действующий контракт.
 *
 * Тест читает исходники, а не собранный бандл: `t` — Proxy, и обращение
 * `t.foo` невозможно отследить в рантайме.
 */
describe("словарь не накапливает мёртвые ключи", () => {
  it("каждый ключ ru-словаря используется в коде", async () => {
    const { readFileSync, readdirSync } = await import("node:fs");
    const { join } = await import("node:path");

    const source = readFileSync(join(process.cwd(), "src/i18n.ts"), "utf8");
    const ruBlock = /const ru = \{(.*?)\n\};/s.exec(source);
    expect(ruBlock).not.toBeNull();
    const keys = [...ruBlock![1].matchAll(/^ {2}([a-zA-Z][a-zA-Z0-9_]*):/gm)].map(m => m[1]);
    expect(keys.length).toBeGreaterThan(300);

    // Все файлы, где ключ может быть использован, включая тесты и
    // динамический доступ через строковый литерал (`labelKey: "anomX"`).
    const dirs = ["src", "src/components", "src/test"];
    let code = "";
    for (const dir of dirs) {
      for (const name of readdirSync(join(process.cwd(), dir))) {
        if (!/\.tsx?$/.test(name) || name === "i18n.ts") continue;
        code += readFileSync(join(process.cwd(), dir, name), "utf8");
      }
    }

    const dead = keys.filter(key => !code.includes(`t.${key}`) && !code.includes(`"${key}"`));
    expect(dead, `неиспользуемые ключи: ${dead.join(", ")}`).toEqual([]);
  });
});
