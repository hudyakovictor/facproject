/**
 * Tailwind как тонкий слой над `src/styles/tokens.css`.
 *
 * Раньше в проекте сосуществовали две несвязанные палитры: токены в
 * `tokens.css` и палитра Tailwind по умолчанию (slate/cyan/emerald/rose).
 * Экраны были написаны второй, поэтому 253 хардкод-цвета и сотни
 * `text-slate-400` жили мимо дизайн-системы, а объявленные в токенах светлая
 * тема и compact-плотность не могли работать в принципе — их значения никуда
 * не подставлялись.
 *
 * Здесь палитра по умолчанию удалена целиком и заменена токенами. Следствие
 * важнее удобства: класс вроде `text-slate-400` больше не существует, поэтому
 * забытый цвет вне дизайн-системы обнаруживается сразу, а не живёт годами.
 * Все значения — ссылки на CSS-переменные, поэтому смена темы и плотности
 * работает без пересборки.
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    // Именно `colors`, а не `extend.colors`: палитра по умолчанию должна исчезнуть.
    colors: {
      transparent: "transparent",
      current: "currentColor",
      inherit: "inherit",

      surface: {
        canvas: "var(--surface-canvas)",
        base: "var(--surface-base)",
        raised: "var(--surface-raised)",
        overlay: "var(--surface-overlay)",
        subtle: "var(--surface-subtle)",
        hover: "var(--surface-hover)",
        active: "var(--surface-active)",
        inverse: "var(--surface-inverse)",
      },

      /** Цвет текста. Имя `ink`, чтобы не получалось `text-text-primary`. */
      ink: {
        primary: "var(--text-primary)",
        secondary: "var(--text-secondary)",
        muted: "var(--text-muted)",
        disabled: "var(--text-disabled)",
        inverse: "var(--text-inverse)",
      },

      /** Границы. Имя `line`, чтобы не получалось `border-border-default`. */
      line: {
        subtle: "var(--border-subtle)",
        default: "var(--border-default)",
        strong: "var(--border-strong)",
        focus: "var(--border-focus)",
      },

      /*
       * Семантические цвета. По DS 0.1: cyan — навигация и A, green — принято,
       * amber — ограничение и B, red — кандидат на проверку (не вердикт о
       * личности), violet — приватное и гипотезы, серый пунктир — отсутствие.
       */
      cyan: {
        300: "var(--cyan-300)",
        400: "var(--cyan-400)",
        500: "var(--cyan-500)",
        600: "var(--cyan-600)",
        soft: "var(--cyan-soft)",
      },
      amber: {
        300: "var(--amber-300)",
        400: "var(--amber-400)",
        500: "var(--amber-500)",
        soft: "var(--amber-soft)",
      },
      green: {
        300: "var(--green-300)",
        400: "var(--green-400)",
        500: "var(--green-500)",
        soft: "var(--green-soft)",
      },
      red: {
        300: "var(--red-300)",
        400: "var(--red-400)",
        500: "var(--red-500)",
        soft: "var(--red-soft)",
      },
      violet: {
        300: "var(--violet-300)",
        400: "var(--violet-400)",
        soft: "var(--violet-soft)",
      },
      blue: {
        400: "var(--blue-400)",
        soft: "var(--blue-soft)",
      },
      status: {
        ok: "var(--status-ok)",
        info: "var(--status-info)",
        warning: "var(--status-warning)",
        candidate: "var(--status-candidate)",
        private: "var(--status-private)",
        missing: "var(--status-missing)",
      },
    },

    extend: {
      fontFamily: {
        sans: "var(--font-sans)",
        mono: "var(--font-mono)",
      },
      fontSize: {
        "2xs": "var(--text-2xs)",
        xs: "var(--text-xs)",
        sm: "var(--text-sm)",
        md: "var(--text-md)",
        lg: "var(--text-lg)",
        xl: "var(--text-xl)",
        "2xl": "var(--text-2xl)",
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        full: "var(--radius-full)",
      },
      spacing: {
        1: "var(--space-1)",
        2: "var(--space-2)",
        3: "var(--space-3)",
        4: "var(--space-4)",
        5: "var(--space-5)",
        6: "var(--space-6)",
        8: "var(--space-8)",
        10: "var(--space-10)",
        12: "var(--space-12)",
        16: "var(--space-16)",
      },
      height: {
        control: "var(--control-md)",
        header: "var(--header-height)",
        status: "var(--status-height)",
        workspace: "calc(100vh - var(--header-height) - var(--status-height))",
      },
      /**
       * Высота рабочей области. Раньше в тринадцати местах стояло
       * `calc(100vh-49px)` — магическое число, которое разошлось бы с шапкой
       * при первом же изменении её вёрстки (A12).
       */
      minHeight: {
        workspace: "calc(100vh - var(--header-height) - var(--status-height))",
      },
      maxHeight: {
        workspace: "calc(100vh - var(--header-height) - var(--status-height))",
      },
      boxShadow: {
        popover: "var(--shadow-popover)",
        focus: "var(--shadow-focus)",
      },
      zIndex: {
        sticky: "var(--z-sticky)",
        popover: "var(--z-popover)",
        dialog: "var(--z-dialog)",
        toast: "var(--z-toast)",
      },
      transitionTimingFunction: {
        standard: "var(--ease-standard)",
      },
      transitionDuration: {
        fast: "var(--duration-fast)",
        normal: "var(--duration-normal)",
      },
      maxWidth: {
        content: "var(--content-max)",
      },
    },
  },
  plugins: [],
};
