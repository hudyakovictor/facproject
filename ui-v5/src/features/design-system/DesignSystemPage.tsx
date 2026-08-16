import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import * as Checkbox from "@radix-ui/react-checkbox";
import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import * as Popover from "@radix-ui/react-popover";
import * as Slider from "@radix-ui/react-slider";
import * as Switch from "@radix-ui/react-switch";
import * as Tabs from "@radix-ui/react-tabs";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  BookOpen,
  Boxes,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  Copy,
  Database,
  Download,
  Eye,
  FileWarning,
  Filter,
  Flag,
  Gauge,
  Grid3X3,
  Info,
  Layers3,
  Maximize2,
  Moon,
  MoreHorizontal,
  Play,
  RotateCcw,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sun,
  TriangleAlert,
  Upload,
  X,
} from "lucide-react";
import { Badge, Button, Field, IconButton, Kbd, MetricValue, Panel, SectionHeader, SelectField, StatusBadge } from "../../shared/ui/primitives";
import styles from "./DesignSystemPage.module.css";

const sections = [
  ["foundations", "Основы"],
  ["actions", "Действия"],
  ["forms", "Формы"],
  ["status", "Статусы"],
  ["navigation", "Навигация"],
  ["data", "Данные"],
  ["timeline", "Timeline"],
  ["evidence", "Evidence"],
  ["overlays", "Overlays"],
  ["states", "Состояния"],
  ["publication", "Публикации"],
  ["accessibility", "A11y"],
] as const;

const colors = [
  ["Canvas", "--surface-canvas", "#080d12"],
  ["Base", "--surface-base", "#0b1117"],
  ["Raised", "--surface-raised", "#101820"],
  ["Overlay", "--surface-overlay", "#141e27"],
  ["Cyan", "--cyan-400", "#69cce0"],
  ["Green", "--green-400", "#66bc7e"],
  ["Amber", "--amber-400", "#f2b94b"],
  ["Red", "--red-400", "#ef625d"],
  ["Violet", "--violet-400", "#a97bd4"],
] as const;

const fixturePhotos = [
  { id: "P-001", year: "1999", tone: "ok", quality: 0.89 },
  { id: "P-014", year: "2003", tone: "ok", quality: 0.83 },
  { id: "P-027", year: "2007", tone: "warn", quality: 0.54 },
  { id: "P-041", year: "2011", tone: "a", quality: 0.91 },
  { id: "P-055", year: "2015", tone: "event", quality: 0.78 },
  { id: "P-069", year: "2019", tone: "b", quality: 0.86 },
  { id: "P-083", year: "2023", tone: "ok", quality: 0.81 },
] as const;

function DemoBlock({ title, description, children, wide = false }: { title: string; description?: string; children: ReactNode; wide?: boolean }) {
  return (
    <article className={wide ? styles.demoWide : styles.demoBlock}>
      <header className={styles.demoHeader}>
        <strong>{title}</strong>
        {description && <span>{description}</span>}
      </header>
      <div className={styles.demoBody}>{children}</div>
    </article>
  );
}

function NativeCheckbox({ label, defaultChecked = false }: { label: string; defaultChecked?: boolean }) {
  const [checked, setChecked] = useState(defaultChecked);
  return (
    <label className={styles.checkRow}>
      <Checkbox.Root className={styles.checkbox} checked={checked} onCheckedChange={(value) => setChecked(value === true)}>
        <Checkbox.Indicator><Check size={13} strokeWidth={3} /></Checkbox.Indicator>
      </Checkbox.Root>
      <span>{label}</span>
    </label>
  );
}

function Toggle({ label, defaultChecked = false }: { label: string; defaultChecked?: boolean }) {
  const [checked, setChecked] = useState(defaultChecked);
  return (
    <label className={styles.switchRow}>
      <Switch.Root className={styles.switchRoot} checked={checked} onCheckedChange={setChecked}>
        <Switch.Thumb className={styles.switchThumb} />
      </Switch.Root>
      <span>{label}</span>
    </label>
  );
}

function MiniSparkline({ color = "cyan" }: { color?: "cyan" | "green" | "amber" | "red" | "violet" }) {
  const stroke = {
    cyan: "var(--cyan-400)",
    green: "var(--green-400)",
    amber: "var(--amber-400)",
    red: "var(--red-400)",
    violet: "var(--violet-400)",
  }[color];
  return (
    <svg viewBox="0 0 220 52" className={styles.sparkline} aria-label="Демонстрационный график">
      <path d="M2 40 L22 35 L43 37 L65 28 L86 31 L108 17 L130 22 L151 14 L174 26 L198 19 L218 9" fill="none" stroke={stroke} strokeWidth="2" />
      {[2, 43, 86, 130, 174, 218].map((x, index) => <circle key={x} cx={x} cy={[40, 37, 31, 22, 26, 9][index]} r="2.5" fill={stroke} />)}
    </svg>
  );
}

function TimelineGrammar() {
  return (
    <div className={styles.timelineFixture} aria-label="Демонстрация грамматики таймлайна">
      <div className={styles.fixtureLabel}><Badge tone="private">UI fixture</Badge><span>Не исследовательские данные</span></div>
      <div className={styles.metricTracks}>
        <div className={styles.trackLabel}>pose</div>
        <svg viewBox="0 0 1000 42" preserveAspectRatio="none">
          <path d="M0 28 C100 12 150 31 250 20 S420 12 500 23 S670 32 750 14 S910 27 1000 11" fill="none" stroke="var(--cyan-400)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
        </svg>
        <div className={styles.trackLabel}>quality</div>
        <svg viewBox="0 0 1000 42" preserveAspectRatio="none">
          <path d="M0 12 C110 18 190 9 270 16 S450 33 525 26 S710 8 810 15 S930 10 1000 18" fill="none" stroke="var(--green-400)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <div className={styles.pairBridge}><span>A</span><i /><span>B</span><em>pair bridge</em></div>
      <div className={styles.photoRow}>
        {fixturePhotos.map((photo) => (
          <div className={styles.photoColumn} key={photo.id}>
            <div className={`${styles.fixturePhoto} ${styles[`fixture-${photo.tone}`]}`}>
              <div className={styles.faceGlyph}><i /><b /><span /></div>
              {photo.tone === "a" && <mark className={styles.pinA}>A</mark>}
              {photo.tone === "b" && <mark className={styles.pinB}>B</mark>}
            </div>
            <small>{photo.id}</small>
          </div>
        ))}
      </div>
      <div className={styles.markerRow}>
        {fixturePhotos.map((photo) => (
          <div key={photo.id} className={styles.markerCell}>
            {photo.tone === "event" ? <Flag size={18} className={styles.red} fill="currentColor" /> : photo.tone === "warn" ? <AlertTriangle size={17} className={styles.amber} /> : <span className={styles.okHex}>⬡</span>}
          </div>
        ))}
      </div>
      <div className={styles.intervalBand}><i>1999–2007</i><i>2008–2013</i><i>2014–2019</i><i>2020–2026</i></div>
      <div className={styles.yearRuler}>
        {fixturePhotos.map((photo) => <span key={photo.year}>{photo.year}</span>)}
      </div>
    </div>
  );
}

export default function DesignSystemPage() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [density, setDensity] = useState<"comfortable" | "compact">("comfortable");
  const [threshold, setThreshold] = useState([52]);
  const [toast, setToast] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.density = density;
  }, [theme, density]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(false), 3600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const generatedAt = useMemo(() => new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "short", year: "numeric" }).format(new Date("2026-08-05")), []);

  return (
    <Tooltip.Provider delayDuration={250}>
      <div className={styles.page}>
        <header className={styles.appHeader}>
          <div className={styles.brand}>
            <span className={styles.brandMark}>D</span>
            <div><strong>DEEPUTIN V5</strong><small>Design System · DS 0.1</small></div>
          </div>
          <div className={styles.headerCenter}>
            <Badge tone="private">Internal</Badge>
            <span className={styles.headerRule} />
            <span>Компоненты · состояния · forensic grammar</span>
          </div>
          <div className={styles.headerActions}>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <IconButton label={theme === "dark" ? "Светлая тема" : "Тёмная тема"} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
                  {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
                </IconButton>
              </Tooltip.Trigger>
              <Tooltip.Portal><Tooltip.Content className={styles.tooltip} sideOffset={8}>{theme === "dark" ? "Светлая тема" : "Тёмная тема"}<Tooltip.Arrow className={styles.tooltipArrow} /></Tooltip.Content></Tooltip.Portal>
            </Tooltip.Root>
            <Button size="sm" variant="ghost" onClick={() => setDensity(density === "comfortable" ? "compact" : "comfortable")}><Grid3X3 size={14} /> {density === "comfortable" ? "Compact" : "Comfort"}</Button>
            <Button size="sm" variant="secondary" onClick={() => setToast(true)}><Copy size={14} /> Copy tokens</Button>
          </div>
        </header>

        <nav className={styles.anchorNav} aria-label="Разделы дизайн-системы">
          {sections.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
        </nav>

        <main className={styles.main}>
          <section className={styles.hero}>
            <div className={styles.heroMeta}><span>VERSION 0.1</span><span>{generatedAt}</span><span>WCAG target AA</span></div>
            <h1>Один визуальный язык<br /><em>для измерений, ограничений и проверки.</em></h1>
            <p>Каноническая библиотека UI v5. Здесь фиксируются не только цвета и кнопки, но и семантика: чем фотография отличается от пары, candidate — от verdict, а missing — от нуля.</p>
            <div className={styles.heroActions}>
              <Button variant="primary" size="lg"><BookOpen size={16} /> Правила применения</Button>
              <Button variant="secondary" size="lg"><Download size={16} /> Экспорт tokens</Button>
            </div>
          </section>

          <section id="foundations" className={styles.systemSection}>
            <SectionHeader eyebrow="01 · Foundations" title="Основы" description="Цвет, типографика, интервалы и поверхности. Семантические цвета всегда дублируются формой и текстом." />
            <div className={styles.demoGrid}>
              <DemoBlock wide title="Цветовые tokens" description="Surface + semantic palette">
                <div className={styles.swatchGrid}>
                  {colors.map(([name, token, fallback]) => (
                    <div className={styles.swatch} key={token}>
                      <i style={{ background: `var(${token}, ${fallback})` }} />
                      <strong>{name}</strong>
                      <code>{token}</code>
                    </div>
                  ))}
                </div>
              </DemoBlock>
              <DemoBlock title="Типографика" description="Sans для текста · Mono для данных">
                <div className={styles.typeSpecimens}>
                  <div><span>Display</span><strong className={styles.displaySample}>Хронология</strong><code>clamp(32–60)</code></div>
                  <div><span>Heading</span><strong className={styles.headingSample}>Pair Analysis</strong><code>18 px / 600</code></div>
                  <div><span>Body</span><p>Измерение отображается вместе с применимостью и ограничениями.</p><code>13 px / 1.45</code></div>
                  <div><span>Data</span><strong className={styles.dataSample}>RMS 0.0184</strong><code>IBM Plex Mono</code></div>
                </div>
              </DemoBlock>
              <DemoBlock title="Spacing & radius" description="4 px base grid">
                <div className={styles.spacingDemo}>
                  {[4, 8, 12, 16, 24, 32].map((value) => <div key={value}><i style={{ width: value }} /><span>{value}</span></div>)}
                </div>
                <div className={styles.radiusDemo}><i>2</i><i>4</i><i>7</i><i>10</i><i>∞</i></div>
              </DemoBlock>
            </div>
          </section>

          <section id="actions" className={styles.systemSection}>
            <SectionHeader eyebrow="02 · Actions" title="Кнопки и действия" description="Primary — одно главное действие на контекст. Destructive всегда требует preview/confirm." />
            <div className={styles.demoGrid}>
              <DemoBlock title="Button variants">
                <div className={styles.flexWrap}>
                  <Button variant="primary"><Play size={14} /> Запустить</Button>
                  <Button variant="secondary"><Filter size={14} /> Фильтры</Button>
                  <Button variant="ghost"><RotateCcw size={14} /> Сбросить</Button>
                  <Button variant="danger"><TriangleAlert size={14} /> Удалить</Button>
                  <Button disabled>Недоступно</Button>
                </div>
              </DemoBlock>
              <DemoBlock title="Sizes & icon actions">
                <div className={styles.flexWrap}>
                  <Button size="sm">Small</Button><Button size="md">Medium</Button><Button size="lg">Large</Button>
                  <IconButton label="Настройки"><Settings2 size={16} /></IconButton>
                  <IconButton label="Ещё"><MoreHorizontal size={17} /></IconButton>
                </div>
              </DemoBlock>
              <DemoBlock title="Keyboard pairing">
                <div className={styles.shortcutList}>
                  <span><Kbd>⌘</Kbd><Kbd>K</Kbd> Команды</span>
                  <span><Kbd>A</Kbd> Назначить A</span>
                  <span><Kbd>B</Kbd> Назначить B</span>
                  <span><Kbd>Esc</Kbd> Закрыть слой</span>
                </div>
              </DemoBlock>
            </div>
          </section>

          <section id="forms" className={styles.systemSection}>
            <SectionHeader eyebrow="03 · Forms" title="Поля и live controls" description="Каждый threshold сообщает scope: view-only, profile или versioned scientific configuration." />
            <div className={styles.demoGrid}>
              <DemoBlock wide title="Input controls">
                <div className={styles.formGrid}>
                  <Field label="Поиск" placeholder="Фото, дата, пара…" hint="⌘K для глобального поиска" />
                  <Field label="Authoritative date" defaultValue="2015-06-16" type="date" />
                  <SelectField label="Pose bin" defaultValue="frontal"><option value="frontal">frontal</option><option value="left_light">left_light</option><option value="right_light">right_light</option></SelectField>
                  <Field label="Source URL" defaultValue="https://example.org/source" error="Показан пример error state" />
                </div>
              </DemoBlock>
              <DemoBlock title="Selection controls">
                <div className={styles.controlStack}>
                  <NativeCheckbox label="Показывать geometry" defaultChecked />
                  <NativeCheckbox label="Показывать texture diagnostics" />
                  <Toggle label="Blind mode" />
                  <Toggle label="Vectors" defaultChecked />
                </div>
              </DemoBlock>
              <DemoBlock title="Live threshold" description="Display only">
                <div className={styles.sliderHeader}><span>Quality ≥</span><strong>{threshold[0]}%</strong></div>
                <Slider.Root className={styles.sliderRoot} value={threshold} onValueChange={setThreshold} max={100} step={1}>
                  <Slider.Track className={styles.sliderTrack}><Slider.Range className={styles.sliderRange} /></Slider.Track>
                  <Slider.Thumb className={styles.sliderThumb} aria-label="Quality threshold" />
                </Slider.Root>
                <div className={styles.sliderScale}><span>0</span><span>view-only · 14 скрыто</span><span>100</span></div>
              </DemoBlock>
            </div>
          </section>

          <section id="status" className={styles.systemSection}>
            <SectionHeader eyebrow="04 · Semantic states" title="Статусы" description="Статус всегда содержит label и icon. Цвет — вспомогательный канал." />
            <div className={styles.demoGrid}>
              <DemoBlock wide title="Evidence vocabulary">
                <div className={styles.flexWrap}>
                  <StatusBadge tone="success" icon={<Check size={12} />}>Accepted</StatusBadge>
                  <StatusBadge tone="info" icon={<Info size={12} />}>Within noise</StatusBadge>
                  <StatusBadge tone="warning" icon={<AlertTriangle size={12} />}>Limited</StatusBadge>
                  <StatusBadge tone="candidate" icon={<Flag size={12} />}>Candidate</StatusBadge>
                  <StatusBadge tone="private" icon={<Eye size={12} />}>Private</StatusBadge>
                  <StatusBadge tone="missing" icon={<X size={12} />}>No data</StatusBadge>
                </div>
              </DemoBlock>
              <DemoBlock title="Pipeline chips">
                <div className={styles.pipelineChips}>
                  <Badge tone="success">Stage 1 ✓</Badge><span>›</span><Badge tone="success">Profile ✓</Badge><span>›</span><Badge tone="warning">Stage 2 limited</Badge><span>›</span><Badge tone="missing">Report —</Badge>
                </div>
              </DemoBlock>
              <DemoBlock title="Quality ring">
                <div className={styles.qualityExamples}>
                  <div className={styles.qualityRing} style={{ "--quality": "88%" } as CSSProperties}><span>88</span></div>
                  <div className={`${styles.qualityRing} ${styles.qualityWarn}`} style={{ "--quality": "54%" } as CSSProperties}><span>54</span></div>
                  <div className={`${styles.qualityRing} ${styles.qualityBad}`} style={{ "--quality": "23%" } as CSSProperties}><span>23</span></div>
                </div>
              </DemoBlock>
            </div>
          </section>

          <section id="navigation" className={styles.systemSection}>
            <SectionHeader eyebrow="05 · Navigation" title="Навигация и контекстные меню" description="Основные разделы сверху. На timeline нет постоянного sidebar." />
            <div className={styles.demoGrid}>
              <DemoBlock wide title="Context toolbar">
                <div className={styles.contextToolbar}>
                  <DropdownMenu.Root>
                    <DropdownMenu.Trigger asChild><Button size="sm" variant="secondary">Ракурс: frontal <ChevronDown size={13} /></Button></DropdownMenu.Trigger>
                    <DropdownMenu.Portal><DropdownMenu.Content className={styles.menuContent} sideOffset={6} align="start">
                      <DropdownMenu.Label>9 POSE BINS</DropdownMenu.Label>
                      {['left_profile','left_deep','left_mid','left_light','frontal','right_light','right_mid','right_deep','right_profile'].map((pose) => <DropdownMenu.Item className={styles.menuItem} key={pose}><span>{pose}</span><small>{pose === 'frontal' ? '126' : '84'}</small></DropdownMenu.Item>)}
                    </DropdownMenu.Content></DropdownMenu.Portal>
                  </DropdownMenu.Root>
                  <Button size="sm" variant="secondary"><Activity size={13} /> Метрики 6/24</Button>
                  <Popover.Root>
                    <Popover.Trigger asChild><Button size="sm" variant="secondary"><SlidersHorizontal size={13} /> Фильтры <Badge tone="info">3</Badge></Button></Popover.Trigger>
                    <Popover.Portal><Popover.Content className={styles.popoverContent} align="start" sideOffset={6}>
                      <div className={styles.popoverHeader}><div><small>LIVE · VIEW ONLY</small><strong>Пороги отображения</strong></div><Popover.Close asChild><IconButton label="Закрыть"><X size={15} /></IconButton></Popover.Close></div>
                      <div className={styles.controlStack}><NativeCheckbox label="Quality gate" defaultChecked /><NativeCheckbox label="Exclude near-duplicates" /><Toggle label="Only findings" /></div>
                      <Popover.Arrow className={styles.popoverArrow} />
                    </Popover.Content></Popover.Portal>
                  </Popover.Root>
                  <Button size="sm" variant="secondary"><Flag size={13} /> Находки 7</Button>
                  <Button size="sm" variant="secondary"><ArrowLeftRight size={13} /> Сравнение A→B</Button>
                  <Button size="sm" variant="secondary"><Layers3 size={13} /> Вид</Button>
                  <span className={styles.toolbarSpacer} />
                  <IconButton label="Поиск"><Search size={15} /></IconButton>
                  <IconButton label="Во весь экран"><Maximize2 size={15} /></IconButton>
                </div>
              </DemoBlock>
              <DemoBlock title="Tabs">
                <Tabs.Root defaultValue="summary">
                  <Tabs.List className={styles.tabsList}><Tabs.Trigger value="summary">Сводка</Tabs.Trigger><Tabs.Trigger value="geometry">Geometry</Tabs.Trigger><Tabs.Trigger value="provenance">Provenance</Tabs.Trigger></Tabs.List>
                  <Tabs.Content value="summary" className={styles.tabContent}>Главные факты и ограничения.</Tabs.Content>
                  <Tabs.Content value="geometry" className={styles.tabContent}>LDM · mesh · coordinate space.</Tabs.Content>
                  <Tabs.Content value="provenance" className={styles.tabContent}>Источник · дата · hash.</Tabs.Content>
                </Tabs.Root>
              </DemoBlock>
              <DemoBlock title="Breadcrumb & pagination">
                <div className={styles.breadcrumb}><span>Timeline</span><i>/</i><span>frontal</span><i>/</i><strong>2014–2019</strong></div>
                <div className={styles.pagination}><Button size="sm" variant="ghost">←</Button><Button size="sm" variant="secondary">1</Button><Button size="sm" variant="ghost">2</Button><Button size="sm" variant="ghost">3</Button><span>…</span><Button size="sm" variant="ghost">12</Button><Button size="sm" variant="ghost">→</Button></div>
              </DemoBlock>
            </div>
          </section>

          <section id="data" className={styles.systemSection}>
            <SectionHeader eyebrow="06 · Data display" title="Метрики, графики и таблицы" description="Число всегда сопровождается unit, source state и null semantics." />
            <div className={styles.metricGrid}>
              <MetricValue label="RMS · LDM134" value="0.0184" trend="p95 0.021 · calibrated" tone="success" />
              <MetricValue label="Common points" value="91" unit="/134" trend="visibility intersection" tone="info" />
              <MetricValue label="Pose gap · yaw" value="4.2" unit="°" trend="limit 6.0°" tone="warning" />
              <MetricValue label="Evidence state" value="—" trend="not measurable" tone="missing" />
            </div>
            <div className={styles.demoGrid}>
              <DemoBlock title="Sparkline families"><div className={styles.sparkStack}><MiniSparkline color="cyan" /><MiniSparkline color="violet" /><MiniSparkline color="green" /></div></DemoBlock>
              <DemoBlock title="Histogram">
                <div className={styles.histogram}>{[18,26,42,62,88,73,54,33,22,16,9,5].map((height, index) => <i key={index} style={{ height: `${height}%` }} className={index > 8 ? styles.histAlert : undefined} />)}</div>
                <div className={styles.histAxis}><span>within noise</span><span>threshold</span><span>elevated</span></div>
              </DemoBlock>
              <DemoBlock wide title="Evidence table">
                <div className={styles.tableWrap}><table className={styles.dataTable}><thead><tr><th>Pair</th><th>Pose</th><th>Quality</th><th>Common</th><th>State</th><th>Review</th><th /></tr></thead><tbody>
                  <tr><td className="mono">A-014 → B-055</td><td>frontal</td><td><Badge tone="success">0.88</Badge></td><td>91/134</td><td><StatusBadge tone="candidate" icon={<Flag size={11} />}>Candidate</StatusBadge></td><td>Pending</td><td><IconButton label="Открыть"><MoreHorizontal size={15} /></IconButton></td></tr>
                  <tr><td className="mono">A-027 → B-041</td><td>frontal</td><td><Badge tone="warning">0.54</Badge></td><td>72/134</td><td><StatusBadge tone="warning" icon={<AlertTriangle size={11} />}>Quality limited</StatusBadge></td><td>—</td><td><IconButton label="Открыть"><MoreHorizontal size={15} /></IconButton></td></tr>
                </tbody></table></div>
              </DemoBlock>
            </div>
          </section>

          <section id="timeline" className={styles.systemSection}>
            <SectionHeader eyebrow="07 · Temporal grammar" title="Грамматика таймлайна" description="Photo point, pair bridge, event marker и interval band — разные типы, но одна временная трансформация." action={<Badge tone="private">Fixture only</Badge>} />
            <Panel className={styles.timelinePanel} raised><TimelineGrammar /></Panel>
            <div className={styles.grammarLegend}>
              <div><span className={styles.legendPhoto} /><strong>Photo point</strong><small>одна дата · одна X</small></div>
              <div><span className={styles.legendPair} /><strong>Pair bridge</strong><small>x(A) → x(B)</small></div>
              <div><Flag size={15} className={styles.red} /><strong>Event</strong><small>граница или review marker</small></div>
              <div><span className={styles.legendInterval} /><strong>Interval</strong><small>from → to</small></div>
            </div>
          </section>

          <section id="evidence" className={styles.systemSection}>
            <SectionHeader eyebrow="08 · Forensic components" title="Evidence и применимость" description="Сначала применимость, затем число. Карточка не может скрывать ограничения." />
            <div className={styles.demoGrid}>
              <DemoBlock title="Applicability card" wide>
                <div className={styles.applicabilityCard}>
                  <div className={styles.applicabilityHead}><StatusBadge tone="warning" icon={<AlertTriangle size={12} />}>Limited</StatusBadge><span>PAIR-2015-0616</span><Button size="sm" variant="ghost">Почему?</Button></div>
                  <div className={styles.gateGrid}>
                    <div><Check size={14} /><span>Same pose bin</span><strong>frontal</strong></div>
                    <div><Check size={14} /><span>Yaw gap</span><strong>4.2° / 6°</strong></div>
                    <div className={styles.gateWarn}><AlertTriangle size={14} /><span>Quality B</span><strong>0.54</strong></div>
                    <div><Check size={14} /><span>Common LDM</span><strong>91 / 134</strong></div>
                    <div><Check size={14} /><span>Calibration</span><strong>7 sets</strong></div>
                    <div className={styles.gateWarn}><FileWarning size={14} /><span>Source chain</span><strong>partial</strong></div>
                  </div>
                </div>
              </DemoBlock>
              <DemoBlock title="Claim card">
                <div className={styles.claimCard}><div><Badge tone="info">RESULT-002</Badge><Badge tone="warning">candidate only</Badge></div><p>Система выделила участок хронологии для ручной проверки.</p><dl><div><dt>Evidence</dt><dd>3 artifacts</dd></div><div><dt>Coverage</dt><dd>91 / 134</dd></div><div><dt>Review</dt><dd>unreviewed</dd></div></dl><Button size="sm" variant="secondary">Открыть claim</Button></div>
              </DemoBlock>
              <DemoBlock title="A/B identity">
                <div className={styles.abDemo}><div className={styles.abTileA}><mark>A</mark><span>2009-03-14</span><small>q 0.91</small></div><ArrowLeftRight size={20} /><div className={styles.abTileB}><mark>B</mark><span>2015-06-16</span><small>q 0.86</small></div></div>
              </DemoBlock>
            </div>
          </section>

          <section id="overlays" className={styles.systemSection}>
            <SectionHeader eyebrow="09 · Overlays" title="Диалоги, popover и feedback" description="Overlays сохраняют контекст страницы и возвращают focus после закрытия." />
            <div className={styles.demoGrid}>
              <DemoBlock title="Dialog">
                <Dialog.Root>
                  <Dialog.Trigger asChild><Button variant="secondary"><Maximize2 size={14} /> Открыть dialog</Button></Dialog.Trigger>
                  <Dialog.Portal>
                    <Dialog.Overlay className={styles.dialogOverlay} />
                    <Dialog.Content className={styles.dialogContent}>
                      <div className={styles.dialogTitleRow}><div><Dialog.Title>Предпросмотр действия</Dialog.Title><Dialog.Description>Scientific profile будет сохранён как новая версия.</Dialog.Description></div><Dialog.Close asChild><IconButton label="Закрыть"><X size={16} /></IconButton></Dialog.Close></div>
                      <div className={styles.dialogSummary}><StatusBadge tone="info" icon={<Info size={12} />}>Preview only</StatusBadge><p>126 фото → 112 включено · 14 исключено. Stage 1 не изменяется.</p></div>
                      <div className={styles.dialogActions}><Dialog.Close asChild><Button variant="ghost">Отмена</Button></Dialog.Close><Button variant="primary">Создать версию</Button></div>
                    </Dialog.Content>
                  </Dialog.Portal>
                </Dialog.Root>
              </DemoBlock>
              <DemoBlock title="Toast & progress">
                <Button variant="secondary" onClick={() => setToast(true)}><Sparkles size={14} /> Показать toast</Button>
                <div className={styles.progressCard}><div><Activity size={15} /><span>Pair metrics</span><strong>72 / 126</strong></div><i><span style={{ width: "57%" }} /></i><small>Осталось примерно 38 сек.</small></div>
              </DemoBlock>
              <DemoBlock title="Tooltip">
                <Tooltip.Root><Tooltip.Trigger asChild><Button variant="ghost"><CircleHelp size={15} /> Наведите</Button></Tooltip.Trigger><Tooltip.Portal><Tooltip.Content className={styles.tooltip} sideOffset={8}>Показывает источник, unit и calibration state.<Tooltip.Arrow className={styles.tooltipArrow} /></Tooltip.Content></Tooltip.Portal></Tooltip.Root>
              </DemoBlock>
            </div>
          </section>

          <section id="states" className={styles.systemSection}>
            <SectionHeader eyebrow="10 · System states" title="Loading, empty, error, blocked" description="Каждое состояние объясняет причину и предлагает безопасный следующий шаг." />
            <div className={styles.stateGrid}>
              <div className={styles.stateCard}><div className={styles.spinner} /><strong>Загрузка timeline</strong><p>Читаем versioned Stage 2 artifacts…</p></div>
              <div className={styles.stateCard}><Database size={24} /><strong>Нет данных в периоде</strong><p>Измените диапазон или снимите view filter.</p><Button size="sm" variant="secondary">Сбросить фильтр</Button></div>
              <div className={`${styles.stateCard} ${styles.errorState}`}><AlertTriangle size={24} /><strong>API недоступен</strong><p>Соединение прервано. Исследовательские данные не заменены fixture.</p><Button size="sm" variant="secondary">Повторить</Button></div>
              <div className={`${styles.stateCard} ${styles.blockedState}`}><ShieldCheck size={24} /><strong>Действие заблокировано</strong><p>Calibration release не прошёл LOPO gate.</p><Button size="sm" variant="ghost">Открыть проверку</Button></div>
            </div>
          </section>

          <section id="publication" className={styles.systemSection}>
            <SectionHeader eyebrow="11 · Editorial" title="Публикации и review" description="Plain text, technical claim и machine evidence связаны одним claim ID." />
            <div className={styles.demoGrid}>
              <DemoBlock wide title="Publication readiness">
                <div className={styles.readinessBar}><div><StatusBadge tone="success" icon={<Check size={12} />}>Stage 3 valid</StatusBadge><StatusBadge tone="warning" icon={<Clock3 size={12} />}>2 claims pending</StatusBadge><StatusBadge tone="candidate" icon={<FileWarning size={12} />}>Rights blocked</StatusBadge></div><strong>68%</strong></div>
                <div className={styles.readinessTrack}><span style={{ width: "68%" }} /></div>
              </DemoBlock>
              <DemoBlock title="Reviewer decision">
                <div className={styles.reviewCard}><span className={styles.reviewerAvatar}>R1</span><div><strong>Needs source check</strong><p>Геометрический сигнал сохраняется, но source chain неполна.</p><small>reviewer-01 · blind session #12</small></div></div>
              </DemoBlock>
              <DemoBlock title="Layer controls">
                <div className={styles.layerGrid}><NativeCheckbox label="Mesh" defaultChecked /><NativeCheckbox label="Texture" defaultChecked /><NativeCheckbox label="Heatmap" /><NativeCheckbox label="LDM134" /><NativeCheckbox label="Vectors" /><NativeCheckbox label="Visible only" defaultChecked /></div>
              </DemoBlock>
              <DemoBlock title="Icon language">
                <div className={styles.iconLanguage}><span><Flag size={17} />Change</span><span><RotateCcw size={17} />Return</span><span><Boxes size={17} />Cluster</span><span><Gauge size={17} />Quality</span><span><Eye size={17} />Review</span><span><Upload size={17} />Ingest</span></div>
              </DemoBlock>
            </div>
          </section>

          <section id="accessibility" className={styles.systemSection}>
            <SectionHeader eyebrow="12 · Accessibility" title="Обязательные правила" description="Дизайн-система считается готовой только после keyboard, contrast и screen-reader проверки." />
            <div className={styles.a11yGrid}>
              <div><Check size={16} /><span><strong>Не только цвет</strong>Icon, shape и text дублируют статус.</span></div>
              <div><Check size={16} /><span><strong>Focus visible</strong>Все controls доступны с клавиатуры.</span></div>
              <div><Check size={16} /><span><strong>Canvas alternative</strong>Графики имеют summary/table view.</span></div>
              <div><Check size={16} /><span><strong>Reduced motion</strong>Морфинг и transitions можно отключить.</span></div>
              <div><Check size={16} /><span><strong>200% zoom</strong>Controls не перекрывают данные.</span></div>
              <div><Check size={16} /><span><strong>Language</strong>RU/EN сохраняют claim semantics.</span></div>
            </div>
          </section>
        </main>

        <footer className={styles.statusBar}>
          <span><ShieldCheck size={13} /> Design source of truth</span>
          <span>Theme: {theme}</span>
          <span>Density: {density}</span>
          <span className={styles.statusSpacer} />
          <strong>ДАННЫЕ · НЕ ВЕРДИКТ</strong>
          <span>build 5.0.0-ds.1</span>
        </footer>

        {toast && <div role="status" className={styles.toast}><Check size={16} /><div><strong>Tokens скопированы</strong><span>Fixture action · clipboard не изменён</span></div><button aria-label="Закрыть" onClick={() => setToast(false)}><X size={15} /></button></div>}
      </div>
    </Tooltip.Provider>
  );
}
