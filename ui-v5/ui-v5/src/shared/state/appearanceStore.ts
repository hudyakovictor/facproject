import { create } from "zustand";

/**
 * Тема и плотность интерфейса (§25 ТЗ, задача З3.3).
 *
 * `tokens.css` с самого начала содержал полный набор значений для светлой темы
 * (`html[data-theme="light"]`) и compact-плотности (`html[data-density]`), но
 * ни один атрибут никогда не выставлялся — оба режима существовали только в
 * виде мёртвого CSS.
 *
 * Выбор сохраняется в localStorage: рабочая станция открывается десятки раз за
 * смену, и сбрасывать настройку рабочего места при каждой перезагрузке значит
 * заставлять эксперта настраивать её заново.
 */

export type Theme = "dark" | "light" | "system";
export type Density = "comfortable" | "compact";

const THEME_KEY = "deeputin.theme";
const DENSITY_KEY = "deeputin.density";

function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  if (typeof localStorage === "undefined") return fallback;
  const value = localStorage.getItem(key);
  return allowed.includes(value as T) ? (value as T) : fallback;
}

/** Системная тема учитывается, когда пользователь не задал явную. */
function prefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return true;
  return !window.matchMedia("(prefers-color-scheme: light)").matches;
}

export function resolveTheme(theme: Theme): "dark" | "light" {
  if (theme === "system") return prefersDark() ? "dark" : "light";
  return theme;
}

/** Применение к корню документа: именно эти атрибуты читает `tokens.css`. */
export function applyAppearance(theme: Theme, density: Density) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset.theme = resolveTheme(theme);
  root.dataset.density = density === "compact" ? "compact" : "comfortable";
}

interface AppearanceState {
  theme: Theme;
  density: Density;
  setTheme: (theme: Theme) => void;
  setDensity: (density: Density) => void;
}

export const useAppearanceStore = create<AppearanceState>((set) => ({
  theme: readStored<Theme>(THEME_KEY, ["dark", "light", "system"], "dark"),
  density: readStored<Density>(DENSITY_KEY, ["comfortable", "compact"], "comfortable"),

  setTheme: (theme) => {
    if (typeof localStorage !== "undefined") localStorage.setItem(THEME_KEY, theme);
    set((state) => {
      applyAppearance(theme, state.density);
      return { theme };
    });
  },

  setDensity: (density) => {
    if (typeof localStorage !== "undefined") localStorage.setItem(DENSITY_KEY, density);
    set((state) => {
      applyAppearance(state.theme, density);
      return { density };
    });
  },
}));

/** Применить сохранённый выбор до первого рендера, чтобы не мигала тема. */
export function initAppearance() {
  const { theme, density } = useAppearanceStore.getState();
  applyAppearance(theme, density);
}
