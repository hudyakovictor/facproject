/**
 * DEEPUTIN icon collection (Iteration 14).
 *
 * Stroke-based icon set (24×24 grid, currentColor) for the forensic
 * workstation UI. Every icon is a small, unambiguous glyph tied to one
 * interface element:
 *
 *   nav       — main navigation modules
 *   findings  — timeline findings layer (anomalies / shape / texture / …)
 *   widgets   — expert widgets (landmark compare, morphing, heatmap, …)
 *   actions   — run/preflight/retry/restore/archive/export/…
 *   evidence  — data & evidence (Stage 1 immutability, provenance, …)
 *   status    — ok / warn / error / within-noise / elevated / persistent
 *
 * Usage: <Icon name="shape" size={18}/> — inherits currentColor, so it
 * works in buttons, nav, panels and status chips without extra styles.
 */
import type { ReactNode, SVGProps } from "react";

export type IconCategory = "nav" | "findings" | "widgets" | "actions" | "evidence" | "status";

export interface IconDef {
  category: IconCategory;
  label: string;
  hint: string;
  element: ReactNode;
}

export const ICONS: Record<string, IconDef> = {
  // ---------------------------------------------------------------- nav
  timeline: {
    category: "nav", label: "Timeline", hint: "хронология, слой находок",
    element: <path d="M2 12h5l2-6 3 12 3-9 2 3h5" />,
  },
  runs: {
    category: "nav", label: "Run Manager", hint: "прогоны Stage 2/3",
    element: <><rect x="3.5" y="4" width="17" height="16" rx="3.5" /><path d="M10.2 8.8l5 3.2-5 3.2z" /></>,
  },
  calibration: {
    category: "nav", label: "Calibration", hint: "7 персон × 9 ракурсов",
    element: <><circle cx="12" cy="12" r="7.5" /><circle cx="12" cy="12" r="2.2" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
  },
  dataset: {
    category: "nav", label: "Data Manager", hint: "подключение Stage 1",
    element: <><ellipse cx="12" cy="6" rx="8" ry="2.6" /><path d="M4 6v12c0 1.4 3.6 2.6 8 2.6s8-1.2 8-2.6V6" /><path d="M4 12c0 1.4 3.6 2.6 8 2.6s8-1.2 8-2.6" /></>,
  },
  profiles: {
    category: "nav", label: "Profiles", hint: "выборки и курация",
    element: <><path d="M12 3l9 4.5-9 4.5-9-4.5z" /><path d="M3 12.5l9 4.5 9-4.5" /><path d="M3 17l9 4.5 9-4.5" /></>,
  },
  settings: {
    category: "nav", label: "Settings", hint: "пороги и настройки",
    element: <><circle cx="12" cy="12" r="3.2" /><path d="M20.5 12h-2.3M18 18l-1.6-1.6M12 20.5v-2.3M6 18l1.6-1.6M3.5 12h2.3M6 6l1.6 1.6M12 3.5v2.3M18 6l-1.6 1.6" /></>,
  },
  photoLab: {
    category: "nav", label: "Photo Lab", hint: "фото, артефакты, mesh",
    element: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9" r="1.8" /><path d="M3 17.5l5-5 4 4 3.5-3.5 5.5 5.5" /></>,
  },
  logs: {
    category: "nav", label: "Logs", hint: "журнал событий",
    element: <><path d="M4 5.5h9M4 9.5h14M4 13.5h7M4 17.5h11" /><circle cx="18.5" cy="5.5" r="1.1" /><circle cx="16.5" cy="17.5" r="1.1" /></>,
  },
  advisor: {
    category: "nav", label: "Advisor", hint: "рекомендации системы",
    element: <><path d="M12 3a5.6 5.6 0 0 0-2.6 10.5c.8.5 1.6 1.2 1.6 2.5h2c0-1.3.8-2 1.6-2.5A5.6 5.6 0 0 0 12 3z" /><path d="M10 19h4M10.6 21.5h2.8" /></>,
  },
  grid: {
    category: "nav", label: "Иконки", hint: "галерея набора",
    element: <><rect x="3" y="3" width="7.5" height="7.5" rx="1.5" /><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" /><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" /><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" /></>,
  },

  // ----------------------------------------------------------- findings
  findings: {
    category: "findings", label: "Находки", hint: "слой находок на таймлайне",
    element: <><path d="M12 21s-6.8-6.3-6.8-10.8a6.8 6.8 0 0 1 13.6 0c0 4.5-6.8 10.8-6.8 10.8z" /><circle cx="12" cy="10" r="2.6" /></>,
  },
  shape: {
    category: "findings", label: "Форма", hint: "мост смещения формы (⌁)",
    element: <><circle cx="4.5" cy="17" r="1.8" /><circle cx="19.5" cy="17" r="1.8" /><path d="M6.2 16.2c2.6-6.5 9-6.5 11.6 0" /></>,
  },
  texture: {
    category: "findings", label: "Текстура кожи", hint: "канал текстуры (◈)",
    element: <><path d="M12 3.5l8.5 4-8.5 4-8.5-4z" /><path d="M3.5 11.5l8.5 4 8.5-4" /><circle cx="9" cy="8" r="0.8" /><circle cx="15" cy="15" r="0.8" /><circle cx="12" cy="19" r="0.8" /></>,
  },
  change: {
    category: "findings", label: "Change point", hint: "флаг изменения (⚑)",
    element: <><path d="M6 21V4" /><path d="M6 4.5h9.5l-2.4 4.3 2.4 4.2H6" /></>,
  },
  returnIcon: {
    category: "findings", label: "Возврат", hint: "возврат к состоянию (↩)",
    element: <><path d="M9 14L4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H9" /></>,
  },
  dense: {
    category: "findings", label: "Перекопирование", hint: "зона плотных копий (▦)",
    element: <><rect x="4" y="4" width="4.5" height="4.5" rx="1" /><rect x="11.5" y="4" width="4.5" height="4.5" rx="1" /><rect x="15.5" y="11" width="4.5" height="4.5" rx="1" /><rect x="7.5" y="12" width="4.5" height="4.5" rx="1" /></>,
  },
  anomaly: {
    category: "findings", label: "Аномалия", hint: "тревожная точка/пара",
    element: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5v5" /><path d="M12 15.5h.01" /></>,
  },
  rate: {
    category: "findings", label: "Темп", hint: "аномальный темп изменения (⚡)",
    element: <path d="M13 2.5L5.5 13h5L9.5 21.5 18.5 11h-5z" />,
  },

  // ------------------------------------------------------------ widgets
  landmarks: {
    category: "widgets", label: "Ключевые точки", hint: "скелет лица 106/134",
    element: <><ellipse cx="12" cy="12.5" rx="8.5" ry="9.5" /><circle cx="9" cy="10.5" r="1" /><circle cx="15" cy="10.5" r="1" /><path d="M9.4 15.6c1.7 1.5 3.5 1.5 5.2 0" /></>,
  },
  ldm106: {
    category: "widgets", label: "LDM 106", hint: "модель из 106 точек",
    element: <><ellipse cx="12" cy="12.5" rx="8.5" ry="9.5" /><circle cx="12" cy="3.2" r="0.8" /><circle cx="4" cy="8.5" r="0.8" /><circle cx="20" cy="8.5" r="0.8" /><circle cx="5.2" cy="16" r="0.8" /><circle cx="18.8" cy="16" r="0.8" /><circle cx="12" cy="21.5" r="0.8" /></>,
  },
  ldm134: {
    category: "widgets", label: "LDM 134", hint: "модель из 134 точек",
    element: <><ellipse cx="12" cy="12.5" rx="8.5" ry="9.5" /><circle cx="7" cy="5.5" r="0.75" /><circle cx="17" cy="5.5" r="0.75" /><circle cx="4.6" cy="12" r="0.75" /><circle cx="19.4" cy="12" r="0.75" /><circle cx="7" cy="19" r="0.75" /><circle cx="17" cy="19" r="0.75" /><circle cx="12" cy="3" r="0.75" /><circle cx="12" cy="21.8" r="0.75" /></>,
  },
  axes: {
    category: "widgets", label: "Оси X/Y/Z", hint: "составляющие смещения",
    element: <><path d="M12 20V4M12 4l-3 3M12 4l3 3" /><path d="M4 12h16M17 9l3 3-3 3" /><path d="M8.5 8.5l7 7M11 15.5h4.5V11" /></>,
  },
  overlay: {
    category: "widgets", label: "Наложение", hint: "режим overlay A+B",
    element: <><circle cx="9.3" cy="12" r="6.2" /><circle cx="14.7" cy="12" r="6.2" /></>,
  },
  sidebyside: {
    category: "widgets", label: "Рядом", hint: "режим side-by-side",
    element: <><rect x="3" y="4" width="8" height="16" rx="1.5" /><rect x="13" y="4" width="8" height="16" rx="1.5" /></>,
  },
  blink: {
    category: "widgets", label: "Мигание", hint: "режим blink-сравнения",
    element: <><path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z" /><circle cx="12" cy="12" r="2.6" /></>,
  },
  morphing: {
    category: "widgets", label: "Morphing", hint: "переход A→B",
    element: <><path d="M17 4.5l3 3-3 3" /><path d="M20 7.5H9a5 5 0 0 0-5 5" /><path d="M7 19.5l-3-3 3-3" /><path d="M4 16.5h11a5 5 0 0 0 5-5" /></>,
  },
  wireframe: {
    category: "widgets", label: "Wireframe", hint: "каркас меша",
    element: <><path d="M3.5 20L12 4l8.5 16z" /><path d="M7.6 20L12 11l4.4 9" /><path d="M4.8 15h14.4" /></>,
  },
  heatmap: {
    category: "widgets", label: "Тепловая карта", hint: "per-vertex смещение",
    element: <><rect x="4" y="4" width="7" height="7" rx="1.2" fill="currentColor" fillOpacity="0.9" stroke="none" /><rect x="13" y="4" width="7" height="7" rx="1.2" fill="currentColor" fillOpacity="0.45" stroke="none" /><rect x="4" y="13" width="7" height="7" rx="1.2" fill="currentColor" fillOpacity="0.2" stroke="none" /><rect x="13" y="13" width="7" height="7" rx="1.2" /></>,
  },

  // ------------------------------------------------------------ actions
  runAction: {
    category: "actions", label: "Запуск", hint: "запустить Stage 2",
    element: <><circle cx="12" cy="12" r="8.5" /><path d="M10.2 8.8l5 3.2-5 3.2z" /></>,
  },
  preflight: {
    category: "actions", label: "Preflight", hint: "оценка пар до запуска",
    element: <><rect x="5.5" y="4" width="13" height="17" rx="2" /><path d="M9 4h6v2.5H9z" /><path d="M9.5 13l2 2 3.5-4" /></>,
  },
  retry: {
    category: "actions", label: "Retry", hint: "новый run с тем же конфигом",
    element: <><path d="M20.5 12a8.5 8.5 0 1 1-2.5-6" /><path d="M20.5 4.5V9H16" /></>,
  },
  restore: {
    category: "actions", label: "Restore", hint: "вернуть из архива",
    element: <><rect x="3.5" y="13.5" width="17" height="7" rx="1.5" /><path d="M12 12.5V6" /><path d="M8.5 9.5L12 6l3.5 3.5" /></>,
  },
  archive: {
    category: "actions", label: "В архив", hint: "архивировать прогон",
    element: <><rect x="3.5" y="13.5" width="17" height="7" rx="1.5" /><path d="M12 6.5V13" /><path d="M8.5 9.5l3.5 3.5 3.5-3.5" /></>,
  },
  delete: {
    category: "actions", label: "Удалить", hint: "failed/cancelled run",
    element: <><path d="M4 7h16" /><path d="M9.5 7V4.5h5V7" /><path d="M6.5 7l1 13h9l1-13" /><path d="M10 11v5.5M14 11v5.5" /></>,
  },
  cancel: {
    category: "actions", label: "Отмена", hint: "отменить задачу/прогон",
    element: <><circle cx="12" cy="12" r="8.5" /><path d="M9 9l6 6M15 9l-6 6" /></>,
  },
  export: {
    category: "actions", label: "Экспорт", hint: "выгрузить CSV/JSON/PNG",
    element: <><path d="M4 15.5v3a2.5 2.5 0 0 0 2.5 2.5h11a2.5 2.5 0 0 0 2.5-2.5v-3" /><path d="M12 4v10" /><path d="M8.5 10.5L12 14l3.5-3.5" /></>,
  },
  screenshot: {
    category: "actions", label: "Снимок", hint: "PNG текущего вида",
    element: <><rect x="3" y="6" width="18" height="13" rx="2" /><path d="M8 6l1.5-2.5h5L16 6" /><circle cx="12" cy="12.5" r="3.4" /></>,
  },
  compare: {
    category: "actions", label: "Сравнить", hint: "сравнение A/B",
    element: <><path d="M4 8h13l-3-3" /><path d="M17 5l3 3-3 3" /><path d="M20 16H7l3 3" /><path d="M10 19l-3-3 3-3" /></>,
  },
  zoom: {
    category: "actions", label: "Масштаб", hint: "лупа / приближение",
    element: <><circle cx="11" cy="11" r="7" /><path d="M16.5 16.5L21 21" /></>,
  },
  date: {
    category: "actions", label: "Дата", hint: "перейти к дате",
    element: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 9.5h18M8 3v4M16 3v4" /><path d="M8 14h3M13 14h3M8 17.5h3" /></>,
  },

  // ----------------------------------------------------------- evidence
  immutable: {
    category: "evidence", label: "Immutable", hint: "Stage 1 неизменен",
    element: <><path d="M12 3l7 3v6c0 5-3.2 8-7 9-3.8-1-7-4-7-9V6z" /><rect x="9.5" y="11" width="5" height="4.2" rx="1" /><path d="M10.5 11V9.8a1.5 1.5 0 0 1 3 0V11" /></>,
  },
  integrity: {
    category: "evidence", label: "Целостность", hint: "хэш-проверка evidence",
    element: <><path d="M12 3l7 3v6c0 5-3.2 8-7 9-3.8-1-7-4-7-9V6z" /><path d="M9 12.3l2.2 2.2 4-4.5" /></>,
  },
  dateConflict: {
    category: "evidence", label: "Конфликт дат", hint: "filename vs EXIF",
    element: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 9.5h18M8 3v4M16 3v4" /><path d="M12 12.5v3.5" /><path d="M12 18.5h.01" /></>,
  },
  duplicate: {
    category: "evidence", label: "Дубликат", hint: "near-duplicate связь",
    element: <><path d="M10 13.5a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.5 1.5" /><path d="M14 10.5a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.5-1.5" /></>,
  },
  provenance: {
    category: "evidence", label: "Провенанс", hint: "датировка и источник",
    element: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M8.5 8h7M8.5 12h7M8.5 16h4" /><circle cx="16.2" cy="16.8" r="2.1" /><path d="M16.2 15v1.3l1.3 1.3" opacity="0.6" /></>,
  },
  person: {
    category: "evidence", label: "Персона", hint: "калибровочный субъект",
    element: <><circle cx="12" cy="8" r="3.6" /><path d="M5 20.5c1.4-4.2 3.9-6 7-6s5.6 1.8 7 6" /></>,
  },
  personCal: {
    category: "evidence", label: "Персона · калибр", hint: "калибровка с прицелом",
    element: <><circle cx="10.5" cy="8" r="3.2" /><path d="M4 19.5c1.3-3.8 3.5-5.5 6.5-5.5s5.2 1.7 6.5 5.5" /><circle cx="18.5" cy="5.5" r="2.4" /><path d="M18.5 1.5v1.8M18.5 7.7v1.8M15.3 5.5h1.8M20.3 5.5h1.8" /></>,
  },
  blind: {
    category: "evidence", label: "Слепой режим", hint: "рецензия без дат/ID",
    element: <><path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z" /><path d="M4 4.5l16 15" /><path d="M12 9.5a2.5 2.5 0 0 1 2.5 2.5" /></>,
  },

  // ------------------------------------------------------------- status
  ok: {
    category: "status", label: "OK", hint: "в пределах нормы",
    element: <><circle cx="12" cy="12" r="8.5" /><path d="M8.5 12.5l2.5 2.5 5-5.5" /></>,
  },
  warn: {
    category: "status", label: "Предупреждение", hint: "обратить внимание",
    element: <><path d="M12 3.5L21 20H3z" /><path d="M12 10v4.5" /><path d="M12 17.5h.01" /></>,
  },
  error: {
    category: "status", label: "Ошибка", hint: "провал/критично",
    element: <><circle cx="12" cy="12" r="8.5" /><path d="M9 9l6 6M15 9l-6 6" /></>,
  },
  info: {
    category: "status", label: "Информация", hint: "справка/уточнение",
    element: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v4.5" /><path d="M12 7.5h.01" /></>,
  },
  noise: {
    category: "status", label: "В пределах шума", hint: "внутри калибровочного шума",
    element: <><circle cx="12" cy="12" r="8.5" /><path d="M7 12h1.5l1-3 2 6 2-4 1 1H17" /></>,
  },
  elevated: {
    category: "status", label: "Повышено", hint: "выше шума, требует проверки",
    element: <><path d="M12 4v10" /><path d="M8.5 7.5L12 4l3.5 3.5" /><path d="M4 18h16" /></>,
  },
  persistent: {
    category: "status", label: "Устойчивое", hint: "закреплённое изменение",
    element: <><path d="M12 21s-5.5-4.6-5.5-9a5.5 5.5 0 0 1 11 0c0 4.4-5.5 9-5.5 9z" /><circle cx="12" cy="11.5" r="2.3" /></>,
  },
};

export const ICON_CATEGORIES: Array<{ key: IconCategory; label: string }> = [
  { key: "nav", label: "Навигация" },
  { key: "findings", label: "Слой находок · таймлайн" },
  { key: "widgets", label: "Экспертные виджеты" },
  { key: "actions", label: "Действия и управление" },
  { key: "evidence", label: "Данные и доказательства" },
  { key: "status", label: "Статусы" },
];

export function Icon({ name, size = 18, ...rest }: { name: string; size?: number } & Omit<SVGProps<SVGSVGElement>, "name">) {
  const def = ICONS[name];
  if (!def) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {def.element}
    </svg>
  );
}
