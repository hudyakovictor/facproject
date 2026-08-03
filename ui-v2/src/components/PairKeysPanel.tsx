import { useEffect, useMemo, useState } from "react";
import { fetchPairMetrics, type KeyCategories, type PairMetrics } from "../api";
import { CATEGORY_ORDER } from "../keys";
import { isVisibleAt, useDetailLevel } from "../settings";
import { KeyCategory } from "./KeyTable";
import { Spinner } from "./Loading";
import Icon from "./Icon";
import { getLanguage, t } from "../i18n";

/** Полные метрики пары: все 186 колонок `pair_metrics.csv` по категориям A–G.
 *
 * Раньше интерфейс показывал результат единственного канала — движения
 * landmarks, — а поправку на множественные сравнения, корроборацию по
 * ракурсам, mesh-канал (52 колонки), текстуру и дескрипторы не показывал
 * вовсе. При 1700 фотографиях это тысячи пар, и часть «аномалий» ложные по
 * построению: без q-value и cross-bin интерфейс выдавал их за факты.
 *
 * Панель ничего не вычисляет — читает `GET /api/v1/pairs/{a}/{b}/metrics`.
 */
export default function PairKeysPanel({ photoA, photoB }: { photoA: string; photoB: string }) {
  const [data, setData] = useState<PairMetrics | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "unavailable" | "error">("idle");
  const [message, setMessage] = useState("");
  const [active, setActive] = useState<string>("A");
  // Уровень детализации управляет составом вкладок: на «простом» уровне
  // служебные категории (провенанс, выравнивание) только зашумляют вывод,
  // на «экспертном» нужны целиком. Раньше настройка не влияла ни на что.
  const detailLevel = useDetailLevel();

  useEffect(() => {
    if (!photoA || !photoB) return;
    let cancelled = false;
    setState("loading");
    setData(null);
    fetchPairMetrics(photoA, photoB)
      .then(payload => {
        if (cancelled) return;
        setData(payload);
        setState("idle");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const text = err instanceof Error ? err.message : String(err);
        // 409 — нет вывода Stage 2; 404 — пара не построена. Это разные
        // состояния, и пользователь должен видеть какое именно.
        setState(/409|404/.test(text) ? "unavailable" : "error");
        setMessage(text);
      });
    return () => { cancelled = true; };
  }, [photoA, photoB]);

  const tabs = useMemo(() => {
    if (!data) return [];
    return CATEGORY_ORDER
      .filter(id => data.categories[id])
      .filter(id => isVisibleAt(CATEGORY_DETAIL[id] ?? "standard", detailLevel))
      .map(id => ({ id, title: categoryTitle(data, id), count: countKeys(data.categories, id) }));
  }, [data, detailLevel]);

  useEffect(() => {
    if (tabs.length && !tabs.some(tab => tab.id === active)) setActive(tabs[0].id);
  }, [tabs, active]);

  if (state === "loading") {
    return (
      <Spinner label={t.keysLoading} />
    );
  }

  if (state === "unavailable") {
    return (
      <div role="status" className="bg-warning/10 border border-warning/40 p-2 font-mono text-[9px] text-warning flex items-start gap-1.5">
        <Icon name="alert-triangle" size={11} color="#e8af34" className="mt-0.5 flex-shrink-0" />
        <div>
          <div>{t.keysUnavailable}</div>
          <div className="text-text-faint mt-0.5 break-words">{message}</div>
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div role="alert" className="bg-critical/15 border border-critical p-2 font-mono text-[9px] text-critical break-words">
        {t.keysLoadFailed}: {message}
      </div>
    );
  }

  if (!data) return null;

  const groups = data.categories[active] ?? {};

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="font-mono text-[9px] tracking-forensic text-text-muted">
          {t.keysPairTitle}
          {/* Честный охват: сколько колонок реально имеют значение. */}
          <span className="text-text-faint"> · {data.available_count}/{data.column_count}</span>
        </div>
        {data.reversed_order && (
          <div className="font-mono text-[8px] text-warning" title={t.keysReversedTitle}>
            {t.keysReversed}
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-px" role="tablist" aria-label={t.keysPairTitle}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={active === tab.id}
            onClick={() => setActive(tab.id)}
            className={`px-2 py-1 font-mono text-[9px] tracking-forensic border ${active === tab.id ? "bg-info/25 border-info text-text" : "border-border text-text-muted hover:text-text"}`}>
            {tab.title} <span className="text-text-faint">{tab.count}</span>
          </button>
        ))}
      </div>

      <div role="tabpanel" className="space-y-1.5">
        {active === "A" && <SignificanceBanner groups={groups} />}
        <KeyCategory
          title={categoryTitle(data, active)}
          groups={groups}
          note={CATEGORY_NOTES[active]?.()}
        />
      </div>

      <div className="font-mono text-[8px] text-text-faint border-t border-border pt-1">
        {t.keysReadOnlyNote}
      </div>
    </div>
  );
}

/** Баннер над категорией A: главные ограничения вывода — до таблицы.
 *
 * Если пара не проходит FDR-поправку или помечена как ограниченная
 * калибровкой/утечкой позы, это должно быть видно раньше самих чисел,
 * иначе читатель успевает сделать вывод по сырому расхождению. */
function SignificanceBanner({ groups }: { groups: Record<string, Record<string, unknown>> }) {
  const warnings: string[] = [];
  const mt = groups.multiple_testing ?? {};
  const limits = groups.limits ?? {};

  if (mt.mt_significant_fdr10 === false) warnings.push(t.keysWarnNotSignificant);
  if (limits.calibration_limited === true) warnings.push(t.keysWarnCalibrationLimited);
  if (limits.pose_leakage_limited === true) warnings.push(t.keysWarnPoseLeakage);

  const corroboration = groups.corroboration ?? {};
  if (corroboration.cross_bin_support_count === 0) warnings.push(t.keysWarnNoCorroboration);

  if (warnings.length === 0) return null;
  return (
    <div role="status" className="bg-warning/10 border-l-2 border-warning px-2 py-1.5 space-y-0.5">
      {warnings.map(text => (
        <div key={text} className="font-mono text-[9px] text-warning flex items-start gap-1.5">
          <Icon name="alert-triangle" size={10} color="#e8af34" className="mt-0.5 flex-shrink-0" />
          <span>{text}</span>
        </div>
      ))}
    </div>
  );
}

/** Минимальный уровень детализации, на котором категория показывается.
 *
 * A (статзначимость) и C (качество) — «простой»: без них вывод читать
 * нельзя вообще. B/D/E/F — «стандартный»: содержательные измерения.
 * G (провенанс) — «экспертный»: хэши и идентификаторы нужны при проверке
 * воспроизводимости, а не при чтении результата. */
const CATEGORY_DETAIL: Record<string, "simple" | "standard" | "expert"> = {
  A: "simple", C: "simple",
  B: "standard", D: "standard", E: "standard", F: "standard",
  G: "expert", H: "expert", I: "expert",
};

/** Пояснения к категориям — почему ключи важны, а не что они значат. */
const CATEGORY_NOTES: Record<string, () => string> = {
  A: () => t.keysNoteA,
  B: () => t.keysNoteB,
  C: () => t.keysNoteC,
  D: () => t.keysNoteD,
  E: () => t.keysNoteE,
  F: () => t.keysNoteF,
  G: () => t.keysNoteG,
};

function categoryTitle(data: { category_titles: Record<string, { ru: string; en: string }> }, id: string): string {
  const entry = data.category_titles[id];
  if (!entry) return id;
  return getLanguage() === "en" ? entry.en : entry.ru;
}

function countKeys(categories: KeyCategories, id: string): number {
  const groups = categories[id];
  if (!groups) return 0;
  return Object.values(groups).reduce((sum, values) => sum + Object.keys(values).length, 0);
}
