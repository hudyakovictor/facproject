import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { fetchSettings, type AppSettings, type ThresholdSettings } from "./api";

/** Единый источник пользовательских настроек для всего интерфейса.
 *
 * Проблема, которую решает модуль (аудит №8, №9): настройки существовали,
 * сохранялись на backend и показывались в `SettingsModal`, но **ни на что
 * не влияли**.
 *
 *   * `detail_level` (простой / стандартный / экспертный) — ни один
 *     компонент его не читал;
 *   * шесть порогов `thresholds.*` — тоже; при этом `ComparisonPanel`
 *     содержал `POLICY_DELTA = {geometry: 0.018, texture: 0.04}` —
 *     буквально копию дефолтных значений `geometry_zone_delta_limit` и
 *     `texture_zone_delta_limit`, вшитую в код. Пользователь двигал
 *     ползунок, значение уезжало на диск, а сравнение продолжало считать
 *     по константе.
 *
 * Это худший вид дефекта из запрещённых `app6/AGENTS.md`: интерфейс
 * заявляет управление, которого нет. В forensic-контексте следователь
 * решит, что ужесточил порог, и получит прежний результат под видом нового.
 *
 * Настройки грузятся один раз на уровне `App` и раздаются контекстом; при
 * сохранении в `SettingsModal` контекст обновляется, и все потребители
 * пересчитываются.
 */

/** Уровень детализации: сколько служебных данных показывать. */
export type DetailLevel = "simple" | "standard" | "expert";

export const DETAIL_LEVELS: readonly DetailLevel[] = ["simple", "standard", "expert"] as const;

/** Пороги по умолчанию — те же, что в `app6/api/settings.DEFAULT_SETTINGS`.
 *
 * Дублирование осознанное: это fallback на случай, когда backend недоступен.
 * Значения обязаны совпадать, и это проверяется тестом
 * `settings.test.ts::дефолты совпадают с контрактом backend`. */
export const DEFAULT_THRESHOLDS: ThresholdSettings = {
  confidence_min: 0,
  quality_min: 0,
  geometry_zone_delta_limit: 0.018,
  texture_zone_delta_limit: 0.04,
  expression_smile: 0.92,
  expression_jaw_open: 0.28,
};

export interface SettingsState {
  /** `null`, пока настройки не загружены или backend недоступен. */
  settings: AppSettings | null;
  thresholds: ThresholdSettings;
  detailLevel: DetailLevel;
  /** Настройки взяты с backend, а не из встроенных значений. */
  loaded: boolean;
  /** Обновить состояние после сохранения в модалке. */
  apply: (next: AppSettings) => void;
}

const FALLBACK: SettingsState = {
  settings: null,
  thresholds: DEFAULT_THRESHOLDS,
  detailLevel: "standard",
  loaded: false,
  apply: () => undefined,
};

export const SettingsContext = createContext<SettingsState>(FALLBACK);

export function useSettings(): SettingsState {
  return useContext(SettingsContext);
}

/** Пороги текущих настроек (или встроенные, если backend недоступен). */
export function useThresholds(): ThresholdSettings {
  return useSettings().thresholds;
}

/** Уровень детализации. */
export function useDetailLevel(): DetailLevel {
  return useSettings().detailLevel;
}

/** Показывать ли блок указанной сложности при текущем уровне детализации.
 *
 * Правило: `simple` — только выводы, `standard` — плюс метрики,
 * `expert` — плюс служебные данные (политики выравнивания, хэши, схемы).
 * Порог сравнивается по возрастанию, поэтому «expert»-блок виден только
 * на экспертном уровне, а «simple»-блок — всегда. */
export function isVisibleAt(required: DetailLevel, current: DetailLevel): boolean {
  return DETAIL_LEVELS.indexOf(required) <= DETAIL_LEVELS.indexOf(current);
}

function normalizeDetailLevel(raw: unknown): DetailLevel {
  return DETAIL_LEVELS.includes(raw as DetailLevel) ? (raw as DetailLevel) : "standard";
}

/** Числовое поле порога: `NaN`/`null` заменяются встроенным значением.
 *
 * Ноль — валидный порог (означает «не фильтровать»), поэтому `|| default`
 * здесь был бы ошибкой: он превратил бы осознанный 0 в дефолт. */
function normalizeThresholds(raw: Partial<ThresholdSettings> | undefined): ThresholdSettings {
  const out = { ...DEFAULT_THRESHOLDS };
  if (!raw) return out;
  for (const key of Object.keys(DEFAULT_THRESHOLDS) as (keyof ThresholdSettings)[]) {
    const value = raw[key];
    if (typeof value === "number" && Number.isFinite(value)) out[key] = value;
  }
  return out;
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then(value => { if (!cancelled) { setSettings(value); setLoaded(true); } })
      // Backend недоступен — работаем на встроенных значениях. Это
      // отражается в `loaded: false`, и интерфейс может это показать.
      .catch(() => { if (!cancelled) setLoaded(false); });
    return () => { cancelled = true; };
  }, []);

  const apply = useCallback((next: AppSettings) => {
    setSettings(next);
    setLoaded(true);
  }, []);

  const value = useMemo<SettingsState>(() => ({
    settings,
    thresholds: normalizeThresholds(settings?.thresholds),
    detailLevel: normalizeDetailLevel(settings?.detail_level),
    loaded,
    apply,
  }), [settings, loaded, apply]);

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}
