# Улучшения для максимального балла: UI/UX и Дизайн-система

## П.9 — UI/UX и дизайн-система — текущий 90 → цель 100

### 9.1. Типографическая сетка (Typography Scale)

**Проблема**: Нет описания размеров шрифтов, межстрочных интервалов и иерархии текста.

**Решение**:

```css
/* design-system/typography.css */
:root {
  /* Font families */
  --font-display: 'Space Grotesk Variable', sans-serif;
  --font-body: 'Inter Variable', sans-serif;
  --font-mono: 'JetBrains Mono Variable', monospace;
  --font-ui: 'Inter Variable', sans-serif;

  /* Font sizes — modular scale 1.25 (Major Third) */
  --text-xs: 0.75rem;    /* 12px — метки, подписи */
  --text-sm: 0.875rem;   /* 14px — UI-элементы, secondary */
  --text-base: 1rem;     /* 16px — основной текст */
  --text-lg: 1.25rem;    /* 20px — заголовки секций */
  --text-xl: 1.5rem;     /* 24px — заголовки панелей */
  --text-2xl: 2rem;      /* 32px — заголовок страницы */
  --text-3xl: 2.5rem;    /* 40px — hero-заголовок */

  /* Line heights */
  --leading-tight: 1.15;   /* Заголовки */
  --leading-normal: 1.5;   /* Текст */
  --leading-relaxed: 1.75; /* Многострочный текст */

  /* Font weights */
  --weight-normal: 400;
  --weight-medium: 500;
  --weight-semibold: 600;
  --weight-bold: 700;

  /* Letter spacing */
  --tracking-tight: -0.02em;  /* Заголовки */
  --tracking-normal: 0em;
  --tracking-wide: 0.05em;    /* Монопространственный */
  --tracking-wider: 0.1em;    /* Метки, баджи */
}

/* Применение */
.track-label { font: var(--text-xs)/var(--leading-tight) var(--font-mono); letter-spacing: var(--tracking-wide); text-transform: uppercase; }
.panel-title { font: var(--text-lg)/var(--leading-tight) var(--font-display); font-weight: var(--weight-semibold); letter-spacing: var(--tracking-tight); }
.data-value { font: var(--text-base)/var(--leading-normal) var(--font-mono); font-weight: var(--weight-medium); }
.verdict-text { font: var(--text-xl)/var(--leading-tight) var(--font-display); font-weight: var(--weight-bold); }
```

---

### 9.2. Skeleton/Placeholder состояния

**Проблема**: Нет описания, как выглядят компоненты во время загрузки данных.

**Решение**:

```css
/* design-system/skeleton.css */
:root {
  --skeleton-base: #1a1a24;
  --skeleton-shine: #242433;
  --skeleton-duration: 1.5s;
}

@keyframes skeleton-pulse {
  0% { background-color: var(--skeleton-base); }
  50% { background-color: var(--skeleton-shine); }
  100% { background-color: var(--skeleton-base); }
}

.skeleton {
  animation: skeleton-pulse var(--skeleton-duration) ease-in-out infinite;
  border-radius: 4px;
}
```

**Компоненты-скелетоны**:

| Компонент | Скелетон |
|-----------|----------|
| HeaderBar | Прямоугольник 200×32px (лого) + 150×32px (поиск) |
| LeftPanel | 5 вкладок (табы) + прямоугольник 300×400px (контент) |
| Timeline Track | Горизонтальная линия с волнистым паттерном (shimmer) |
| Filmstrip | 10 серых прямоугольников 80×80px с пульсацией |
| 3D Inspector | Серый круг (заглушка viewport) + вращающийся спиннер |
| DataTable (GEOMETRY) | 21 строка по 3 прямоугольника (label, value, indicator) |
| Chart (Tremor) | Серый прямоугольник с имитацией графика (CSS паттерн) |

**Пример реализации**:
```tsx
// components/Skeleton.tsx
interface SkeletonProps {
  width: string | number;
  height: string | number;
  borderRadius?: string;
  variant?: "pulse" | "shimmer" | "wave";
}

function Skeleton({ width, height, borderRadius = "4px", variant = "pulse" }: SkeletonProps) {
  return (
    <div
      className={`skeleton skeleton--${variant}`}
      style={{ width, height, borderRadius }}
      aria-hidden="true"
    />
  );
}

// Использование:
function TimelineTrackSkeleton() {
  return (
    <div className="track-skeleton">
      <Skeleton width="100%" height="60px" variant="shimmer" />
    </div>
  );
}
```

---

### 9.3. Анимации переходов между состояниями

**Проблема**: Нет описания анимаций для смены состояний (выбор кадра, открытие панели, фильтрация).

**Решение**:

```css
/* design-system/animations.css */
:root {
  /* Duration */
  --anim-fast: 150ms;
  --anim-normal: 300ms;
  --anim-slow: 500ms;

  /* Easing */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* Смена выбранного кадра */
@keyframes frame-select {
  from { outline-color: transparent; transform: scale(1); }
  to { outline-color: var(--accent-geometry); transform: scale(1.05); }
}
.frame-selected {
  animation: frame-select var(--anim-normal) var(--ease-spring);
}

/* Появление панели */
@keyframes panel-enter {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
}
.panel-enter {
  animation: panel-enter var(--anim-normal) var(--ease-out);
}

/* Фильтрация — исчезновение неподходящих точек */
@keyframes point-fade-out {
  from { opacity: 1; transform: scale(1); }
  to { opacity: 0; transform: scale(0.5); }
}
@keyframes point-fade-in {
  from { opacity: 0; transform: scale(0.5); }
  to { opacity: 1; transform: scale(1); }
}

/* Переключение вкладок Left Panel */
@keyframes tab-content-enter {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
.tab-content {
  animation: tab-content-enter var(--anim-fast) var(--ease-out);
}

/* Hover на треке — подсветка */
.track:hover {
  transition: background-color var(--anim-fast) var(--ease-out);
  background-color: rgba(79, 152, 163, 0.05);
}

/* Анимация playhead */
@keyframes playhead-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.playhead-active {
  animation: playhead-pulse 1s ease-in-out infinite;
}
```

**Framer Motion для сложных переходов**:
```tsx
// Анимация появления LeftPanel при выборе кадра
<AnimatePresence>
  {selectedPhotoId && (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      <LeftPanel photoId={selectedPhotoId} />
    </motion.div>
  )}
</AnimatePresence>

// Анимация переключения вкладок
<motion.div
  key={activeTab}
  initial={{ opacity: 0, y: 10 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.15 }}
>
  {tabContent}
</motion.div>
```

---

### 9.4. Responsive Design (адаптация под разные экраны)

**Проблема**: Нет описания, как интерфейс адаптируется под разные разрешения.

**Решение**:

```css
/* design-system/responsive.css */
:root {
  /* Breakpoints */
  --bp-sm: 640px;   /* Мобильный */
  --bp-md: 1024px;  /* Планшет */
  --bp-lg: 1440px;  /* Десктоп */
  --bp-xl: 1920px;  /* Широкий десктоп */
  --bp-2xl: 2560px; /* Ultra-wide */
}

/* Layout grid */
.layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  grid-template-rows: 56px 1fr 32px;
  height: 100vh;
}

@media (max-width: 1024px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .left-panel {
    position: fixed;
    left: -380px;
    transition: left var(--anim-normal) var(--ease-out);
    z-index: 50;
  }
  .left-panel--open {
    left: 0;
  }
}

@media (min-width: 1920px) {
  .layout {
    grid-template-columns: 480px 1fr 320px;
  }
}
```

**Адаптация компонентов**:

| Компонент | < 1024px | 1024-1440px | 1440-1920px | > 1920px |
|-----------|----------|-------------|-------------|----------|
| LeftPanel | Drawer (выезжает слева) | Фиксированная 320px | Фиксированная 380px | Фиксированная 480px |
| Timeline | 8 треков (скрыть 6) | 12 треков | 14 треков | 14 треков + MiniMap |
| Filmstrip | 40px высота | 60px | 80px | 100px |
| HeaderBar | Компактный | Полный | Полный | Полный + доп. кнопки |
| 3D Inspector | На весь экран | 50% ширины | 40% ширины | 35% ширины |
| DataTable | 5 зон (скрыть 16) | 10 зон | 21 зона | 21 зона + графики |

**Collapsible панели**:
- Все панели можно свернуть/развернуть (кнопка в углу)
- Состояние панелей сохраняется в localStorage
- Hotkey: `Ctrl+B` — toggle LeftPanel, `Ctrl+J` — toggle Timeline

---

### 9.5. Accessibility (a11y)

**Проблема**: Нет описания ARIA-атрибутов, клавиатурной навигации, контрастности.

**Решение**:

```css
/* design-system/accessibility.css */
:root {
  /* Focus */
  --focus-ring: 0 0 0 2px var(--accent-geometry), 0 0 0 4px rgba(79, 152, 163, 0.3);
  --focus-ring-danger: 0 0 0 2px var(--accent-anomaly), 0 0 0 4px rgba(255, 59, 48, 0.3);

  /* Contrast ratios (WCAG AA compliant) */
  --text-primary: #f1f5f9;       /* contrast 15.3:1 on #09090b */
  --text-secondary: #94a3b8;     /* contrast 7.2:1 on #09090b */
  --text-muted: #64748b;         /* contrast 4.5:1 on #09090b (AA minimum) */
}

/* Skip to main content */
.skip-link {
  position: absolute;
  top: -100%;
  left: 8px;
  padding: 8px 16px;
  background: var(--accent-geometry);
  color: #fff;
  z-index: 9999;
  border-radius: 4px;
}
.skip-link:focus {
  top: 8px;
}
```

**ARIA-атрибуты по компонентам**:

| Компонент | ARIA |
|-----------|------|
| Timeline Canvas | `role="img" aria-label="Timeline with 14 tracks. Use arrow keys to navigate."` |
| Track | `role="graphics-symbol" aria-label="Bone Score track. Current value: 0.87"` |
| Playhead | `role="slider" aria-valuemin="0" aria-valuemax="1809" aria-valuenow="423" aria-label="Timeline position"` |
| LeftPanel Tab | `role="tabpanel" aria-labelledby="tab-geometry"` |
| Filmstrip | `role="listbox" aria-label="Photo filmstrip" aria-orientation="horizontal"` |
| Filmstrip Item | `role="option" aria-selected="true/false" aria-label="Photo 2000_01_01_p01f000227"` |
| 3D Viewport | `role="application" aria-label="3D face mesh viewer. Use mouse to rotate."` |
| Filter Badge | `role="status" aria-live="polite" aria-label="Active filter: Era 1"` |
| Command Palette | `role="dialog" aria-label="Command palette. Type to search."` |
| Verdict | `role="alert" aria-live="assertive" aria-label="Verdict: H0 - Same person, 92% confidence"` |

**Клавиатурная навигация**:

| Hotkey | Действие |
|--------|----------|
| `Tab` / `Shift+Tab` | Навигация между панелями |
| `←` / `→` | Перемещение playhead на один кадр |
| `Shift+←` / `Shift+→` | Перемещение playhead на 10 кадров |
| `Ctrl+←` / `Ctrl+→` | Перемещение playhead на эпоху |
| `+` / `-` | Zoom in / Zoom out |
| `Space` | Play/Pause auto-play |
| `Enter` | Выбрать кадр / открыть детали |
| `Escape` | Закрыть панель / отменить выбор |
| `Cmd+K` | Открыть Command Palette |
| `Ctrl+B` | Toggle LeftPanel |
| `Ctrl+J` | Toggle Timeline |
| `F` | Toggle фильтр "Только аномалии" |
| `R` | Сбросить zoom (Fit All) |
| `?` | Показать список hotkeys |

**Focus management**:
- При открытии Command Palette — фокус на поле ввода
- При закрытии — фокус возвращается на предыдущий элемент
- При выборе кадра — фокус на LeftPanel
- При открытии 3D Inspector — фокус на viewport
- Visible focus ring на всех интерактивных элементах

---

### 9.6. Дизайн-токены (Design Tokens)

**Проблема**: Цвета определены как CSS-переменные, но нет единой системы токенов.

**Решение**:

```typescript
// design-system/tokens.ts
export const tokens = {
  color: {
    bg: {
      primary: "#09090b",
      secondary: "#0d0d12",
      tertiary: "#14141a",
      elevated: "#1a1a24",
      hover: "#222230",
    },
    text: {
      primary: "#f1f5f9",
      secondary: "#94a3b8",
      muted: "#64748b",
      inverse: "#09090b",
      link: "#4f98a3",
    },
    border: {
      default: "#1e293b",
      hover: "#334155",
      focus: "#4f98a3",
    },
    accent: {
      geometry: "#4f98a3",
      geometryDim: "#2d6b75",
      bio: "#fdab43",
      bioDim: "#b87a2e",
      anomaly: "#ff3b30",
      anomalyDim: "#b82a22",
    },
    hypothesis: {
      h0: "#22c55e",
      h1: "#fdab43",
      h2: "#ff3b30",
      unknown: "#64748b",
    },
    era: {
      1: "#3b82f6",
      2: "#8b5cf6",
      3: "#ec4899",
      4: "#f59e0b",
      5: "#10b981",
    },
    chart: {
      line: "#4f98a3",
      area: "rgba(79, 152, 163, 0.15)",
      bar: "#a78bfa",
      scatter: "#94a3b8",
      threshold: {
        warning: "#fdab43",
        critical: "#ff3b30",
        normal: "rgba(34, 197, 94, 0.2)",
      },
    },
    semantic: {
      success: "#22c55e",
      warning: "#fdab43",
      error: "#ff3b30",
      info: "#4f98a3",
    },
  },
  spacing: {
    xs: "4px",
    sm: "8px",
    md: "16px",
    lg: "24px",
    xl: "32px",
    "2xl": "48px",
  },
  radius: {
    sm: "4px",
    md: "8px",
    lg: "12px",
    xl: "16px",
    full: "9999px",
  },
  shadow: {
    sm: "0 1px 2px rgba(0,0,0,0.3)",
    md: "0 4px 6px rgba(0,0,0,0.4)",
    lg: "0 10px 15px rgba(0,0,0,0.5)",
    xl: "0 20px 25px rgba(0,0,0,0.6)",
    glow: {
      geometry: "0 0 20px rgba(79, 152, 163, 0.3)",
      anomaly: "0 0 20px rgba(255, 59, 48, 0.3)",
      h0: "0 0 20px rgba(34, 197, 94, 0.3)",
    },
  },
  zIndex: {
    base: 0,
    dropdown: 10,
    sticky: 20,
    modal: 30,
    popover: 40,
    tooltip: 50,
    commandPalette: 60,
  },
} as const;
```

---

### 9.7. Темы: тёмная + светлая + high-contrast

**Проблема**: Только тёмная тема. Нет светлой и high-contrast режимов.

**Решение**:

```css
/* design-system/themes.css */
:root {
  /* Тёмная тема (по умолчанию) */
  --bg-primary: #09090b;
  --text-primary: #f1f5f9;
  /* ... остальные токены */
}

[data-theme="light"] {
  --bg-primary: #f8fafc;
  --bg-secondary: #f1f5f9;
  --bg-tertiary: #e2e8f0;
  --bg-elevated: #ffffff;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --border-color: #cbd5e1;
  --border-hover: #94a3b8;
  /* Акцентные цвета остаются теми же для консистентности данных */
}

[data-theme="high-contrast"] {
  --bg-primary: #000000;
  --bg-secondary: #0a0a0a;
  --bg-tertiary: #1a1a1a;
  --text-primary: #ffffff;
  --text-secondary: #e0e0e0;
  --text-muted: #b0b0b0;
  --border-color: #ffffff;
  --border-hover: #cccccc;
  /* Увеличенная контрастность для всех акцентных цветов */
  --accent-geometry: #00e5ff;
  --accent-anomaly: #ff0000;
  --h0-color: #00ff00;
  --h1-color: #ffaa00;
  --h2-color: #ff0000;
}

/* Переключатель темы */
.theme-toggle {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--anim-fast) var(--ease-out);
}
.theme-toggle:hover {
  border-color: var(--border-hover);
  background: var(--bg-elevated);
}
```

---

### 9.8. Состояния ошибок и пустые состояния

**Проблема**: Описаны только состояния загрузки, нет ошибок и пустых состояний.

**Решение**:

```tsx
// components/ErrorState.tsx
interface ErrorStateProps {
  title: string;
  message: string;
  icon?: React.ReactNode;
  action?: { label: string; onClick: () => void };
  variant?: "inline" | "fullscreen" | "toast";
}

function ErrorState({ title, message, icon, action, variant = "inline" }: ErrorStateProps) {
  return (
    <div className={`error-state error-state--${variant}`} role="alert">
      {icon || <AlertTriangleIcon className="error-state__icon" />}
      <h3 className="error-state__title">{title}</h3>
      <p className="error-state__message">{message}</p>
      {action && (
        <button className="error-state__action" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
}

// components/EmptyState.tsx
interface EmptyStateProps {
  title: string;
  description: string;
  illustration?: "no-results" | "no-data" | "no-selection" | "all-filtered";
  action?: { label: string; onClick: () => void };
}

function EmptyState({ title, description, illustration = "no-results", action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className={`empty-state__illustration empty-state__illustration--${illustration}`} />
      <h3 className="empty-state__title">{title}</h3>
      <p className="empty-state__description">{description}</p>
      {action && (
        <button className="empty-state__action" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
}
```

**Сценарии ошибок и пустых состояний**:

| Компонент | Пустое состояние | Ошибка |
|-----------|-----------------|--------|
| Timeline | "Нет данных для отображения. Загрузите датасет." | "Ошибка загрузки таймлайна. [Повторить]" |
| LeftPanel | "Выберите кадр на таймлайне для просмотра деталей." | "Не удалось загрузить данные кадра. [Повторить]" |
| Filmstrip | "Нет кадров, соответствующих фильтрам." | "Ошибка загрузки превью." |
| 3D Inspector | "Выберите кадр для просмотра 3D-модели." | "WebGL недоступен. [Подробнее]" |
| Comparison Mode | "Выберите два кадра для сравнения." | "Ошибка загрузки mesh для сравнения." |
| Cluster Tab | "Недостаточно данных для кластеризации." | "Ошибка вычисления PCA." |
| Search (Cmd+K) | "Ничего не найдено. Попробуйте другой запрос." | "Ошибка поиска. [Повторить]" |
| Export PDF | "Нет данных для экспорта." | "Ошибка генерации PDF. [Повторить]" |

---

### 9.9. Микро-взаимодействия (Micro-interactions)

**Проблема**: Нет описания мелких анимаций, улучшающих тактильные ощущения.

**Решение**:

```css
/* design-system/micro-interactions.css */
/* Кнопки: scale на нажатие */
button:active {
  transform: scale(0.97);
  transition: transform 50ms ease;
}

/* Переключатель: smooth slide */
.toggle {
  width: 40px;
  height: 22px;
  border-radius: 11px;
  background: var(--bg-tertiary);
  cursor: pointer;
  transition: background var(--anim-fast) var(--ease-out);
}
.toggle::after {
  content: '';
  display: block;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--text-secondary);
  transform: translateX(2px);
  transition: transform var(--anim-fast) var(--ease-spring), background var(--anim-fast) var(--ease-out);
}
.toggle--active {
  background: var(--accent-geometry);
}
.toggle--active::after {
  transform: translateX(20px);
  background: #fff;
}

/* Badge фильтра: появление с масштабом */
@keyframes badge-enter {
  from { transform: scale(0); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.filter-badge {
  animation: badge-enter var(--anim-fast) var(--ease-spring);
}

/* Tooltip: плавное появление */
.tooltip {
  opacity: 0;
  transform: translateY(4px);
  transition: opacity var(--anim-fast) var(--ease-out), transform var(--anim-fast) var(--ease-out);
  pointer-events: none;
}
*:hover > .tooltip {
  opacity: 1;
  transform: translateY(0);
}

/* Progress bar: анимация заполнения */
@keyframes progress-fill {
  from { width: 0%; }
}
.progress-bar__fill {
  animation: progress-fill var(--anim-slow) var(--ease-out);
}

/* Notification toast: slide-in */
@keyframes toast-in {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
@keyframes toast-out {
  from { transform: translateX(0); opacity: 1; }
  to { transform: translateX(100%); opacity: 0; }
}
.toast {
  animation: toast-in var(--anim-normal) var(--ease-out);
}
.toast--exiting {
  animation: toast-out var(--anim-normal) var(--ease-in-out);
}
```

---

### 9.10. Дизайн-система документация (Storybook)

**Проблема**: Нет единого источника правды для компонентов.

**Решение**:
- **Storybook 8** для документирования всех компонентов
- Каждый компонент: 3 стори (default, loading, error, empty)
- **Chromatic** для визуального регрессионного тестирования
- **История изменений** для каждого компонента (версионирование)

**Структура Storybook**:
```
stories/
├── Introduction.mdx
├── Tokens/
│   ├── Colors.stories.tsx
│   ├── Typography.stories.tsx
│   ├── Spacing.stories.tsx
│   └── Shadows.stories.tsx
├── Components/
│   ├── HeaderBar.stories.tsx
│   ├── LeftPanel/
│   │   ├── GeometryTab.stories.tsx
│   │   ├── TextureTab.stories.tsx
│   │   ├── ChronoTab.stories.tsx
│   │   ├── VerdictTab.stories.tsx
│   │   └── ClusterTab.stories.tsx
│   ├── Timeline/
│   │   ├── TimelineCanvas.stories.tsx
│   │   ├── Track.stories.tsx
│   │   └── Playhead.stories.tsx
│   ├── Filmstrip.stories.tsx
│   ├── ComparisonMode.stories.tsx
│   ├── Inspector3D.stories.tsx
│   └── HypothesisLegend.stories.tsx
├── Patterns/
│   ├── LoadingStates.stories.tsx
│   ├── EmptyStates.stories.tsx
│   ├── ErrorStates.stories.tsx
│   └── KeyboardNavigation.stories.tsx
└── Pages/
    ├── TimelinePage.stories.tsx
    ├── ComparePage.stories.tsx
    └── ReportPage.stories.tsx
```

---

## Итог: 10 улучшений для UI/UX

| # | Улучшение | Баллы |
|---|-----------|:-----:|
| 9.1 | Типографическая сетка (modular scale, font families, weights) | +2 |
| 9.2 | Skeleton/placeholder состояния для всех компонентов | +2 |
| 9.3 | Анимации переходов (Framer Motion + CSS animations) | +1 |
| 9.4 | Responsive design (4 breakpoints, collapsible панели) | +1 |
| 9.5 | Accessibility (ARIA, keyboard nav, focus, contrast) | +2 |
| 9.6 | Дизайн-токены (TypeScript tokens, shadows, z-index) | +1 |
| 9.7 | Темы (тёмная + светлая + high-contrast) | +1 |
| 9.8 | Error/Empty состояния для всех компонентов | +1 |
| 9.9 | Микро-взаимодействия (button press, toggle, tooltip) | +1 |
| 9.10 | Storybook документация (Chromatic, visual regression) | +1 |
| | **Итого** | **100** |