/**
 * Единый список разделов.
 *
 * Раньше пункты навигации были четырнадцать раз скопированным блоком JSX внутри
 * `TopBar`, а командная палитра держала бы пятнадцатую копию. Один литеральный
 * массив даёт типобезопасные пути (`as const` сохраняет литералы, поэтому
 * `Link` и `navigate` проверяются компилятором) и исключает расхождение между
 * шапкой и палитрой.
 */
export const NAV_ROUTES = [
  { to: "/overview", label: "Обзор", full: "Обзор" },
  { to: "/timeline", label: "Таймлайн", full: "Таймлайн" },
  { to: "/data-manager", label: "Данные", full: "Данные и provenance" },
  { to: "/inspector", label: "Инспектор", full: "Инспектор фотографии" },
  { to: "/morphing", label: "Морфинг", full: "Покадровый просмотр" },
  { to: "/pair-analysis", label: "Сравнение", full: "Парное сравнение" },
  { to: "/clustering", label: "Кластеры", full: "Хронологическое распределение" },
  { to: "/calibration", label: "Калибровка", full: "Калибровка" },
  { to: "/hypotheses", label: "Гипотезы", full: "Валидация гипотез" },
  { to: "/reports", label: "Отчеты", full: "Отчёты" },
  { to: "/articles", label: "Статьи", full: "Материалы" },
  { to: "/monetization", label: "Монетизация", full: "Монетизация" },
  { to: "/audit", label: "Аудит", full: "Провенанс и аудит" },
  { to: "/settings", label: "Настройки", full: "Настройки рабочего места" },
  { to: "/design-system", label: "UI-v5", full: "Дизайн-система" },
] as const;

export type NavRoute = (typeof NAV_ROUTES)[number];
