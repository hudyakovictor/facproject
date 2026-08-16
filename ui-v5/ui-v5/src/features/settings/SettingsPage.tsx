import { useEffect, useState } from "react";
import { Monitor, Moon, RotateCcw, Sun } from "lucide-react";
import { Button, Panel, SectionHeader, Badge } from "../../shared/ui/primitives";
import {
  useAppearanceStore,
  type Density,
  type Theme,
} from "../../shared/state/appearanceStore";
import {
  DEFAULT_VISIBLE_METRICS,
  useAnalysisStore,
} from "../../shared/state/analysisStore";
import { POSE_BINS, poseFullLabel } from "../../shared/poseBins";
import { getApiBase } from "../../shared/api/client";
import styles from "./settings.module.css";

/**
 * Глобальные настройки (§25 ТЗ).
 *
 * Страница сознательно содержит только параметры рабочего места. §25.6 прямо
 * запрещает выносить сюда пороги таймлайна, параметры кластеризации и релиз
 * калибровки: это параметры анализа, они принадлежат своим экранам и должны
 * попадать в провенанс результата, а не в настройки приложения.
 *
 * Показывается только то, чем интерфейс действительно управляет. Пункты §25,
 * требующие backend (роль, сессия, аудит-идентичность, авто-блокировка),
 * перечислены как недоступные, а не имитируются мёртвыми переключателями.
 */

const THEMES: Array<[Theme, string, typeof Sun]> = [
  ["dark", "Тёмная", Moon],
  ["light", "Светлая", Sun],
  ["system", "Системная", Monitor],
];

const DENSITIES: Array<[Density, string, string]> = [
  ["comfortable", "Обычная", "органы управления 34 px"],
  ["compact", "Плотная", "органы управления 30 px, больше строк на экране"],
];

export function SettingsPage() {
  const { theme, setTheme, density, setDensity } = useAppearanceStore();
  const analysis = useAnalysisStore();

  /** Уважение к `prefers-reduced-motion` уже реализовано в global.css. */
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  const resetPreferences = () => {
    setTheme("dark");
    setDensity("comfortable");
    analysis.hydrate({
      activePose: "frontal",
      multiPose: false,
      qualityThreshold: 0,
      mouthThreshold: 0.35,
      poseAngleThreshold: 6,
      findingsMode: false,
      search: "",
      pairA: null,
      pairB: null,
      selectedPhoto: null,
      visibleMetrics: DEFAULT_VISIBLE_METRICS,
      blindMode: false,
    });
  };

  return (
    <div className={styles.page}>
      <SectionHeader
        eyebrow="§25 · Global settings"
        title="Настройки рабочего места"
        description="Только общие параметры интерфейса. Пороги анализа, параметры кластеризации и релиз калибровки остаются на своих экранах: они влияют на результат и должны попадать в его провенанс."
        action={
          <Button variant="secondary" size="sm" onClick={resetPreferences}>
            <RotateCcw className={styles.btnIcon} aria-hidden="true" />
            Сбросить настройки
          </Button>
        }
      />

      <Panel className={styles.panel}>
        <h3 className={styles.heading}>Внешний вид</h3>

        <div className={styles.row}>
          <div className={styles.rowLabel}>
            <span>Тема</span>
            <small>Светлая тема и плотность объявлены в токенах дизайн-системы.</small>
          </div>
          <div className={styles.choices} role="group" aria-label="Тема оформления">
            {THEMES.map(([value, label, Icon]) => (
              <button
                key={value}
                type="button"
                onClick={() => setTheme(value)}
                aria-pressed={theme === value}
                className={theme === value ? styles.choiceOn : styles.choice}
              >
                <Icon className={styles.btnIcon} aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.rowLabel}>
            <span>Плотность</span>
            <small>Влияет на высоту органов управления и вертикальные отступы.</small>
          </div>
          <div className={styles.choices} role="group" aria-label="Плотность интерфейса">
            {DENSITIES.map(([value, label, hint]) => (
              <button
                key={value}
                type="button"
                onClick={() => setDensity(value)}
                aria-pressed={density === value}
                title={hint}
                className={density === value ? styles.choiceOn : styles.choice}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.rowLabel}>
            <span>Уменьшенная анимация</span>
            <small>
              Значение берётся из системной настройки и не переопределяется интерфейсом.
            </small>
          </div>
          <Badge tone={reducedMotion ? "info" : "neutral"}>
            {reducedMotion ? "включена системой" : "выключена"}
          </Badge>
        </div>
      </Panel>

      <Panel className={styles.panel}>
        <h3 className={styles.heading}>Рабочее пространство</h3>

        <div className={styles.row}>
          <div className={styles.rowLabel}>
            <span>Ракурс по умолчанию</span>
            <small>Применяется при открытии экранов анализа.</small>
          </div>
          <label className={styles.selectWrap}>
            <span className={styles.srOnly}>Ракурс по умолчанию</span>
            <select
              className={styles.select}
              value={analysis.activePose}
              onChange={(event) => analysis.setActivePose(event.target.value)}
            >
              {POSE_BINS.map((bin) => (
                <option key={bin.id} value={bin.id}>
                  {poseFullLabel(bin.id)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className={styles.row}>
          <div className={styles.rowLabel}>
            <span>Слепой режим</span>
            <small>Скрывает даты и идентификаторы кадров для независимой оценки (§18.3).</small>
          </div>
          <button
            type="button"
            onClick={() => analysis.setBlindMode(!analysis.blindMode)}
            aria-pressed={analysis.blindMode}
            className={analysis.blindMode ? styles.choiceOn : styles.choice}
          >
            {analysis.blindMode ? "Включён" : "Выключен"}
          </button>
        </div>
      </Panel>

      <Panel className={styles.panel}>
        <h3 className={styles.heading}>API и хранилище</h3>
        <dl className={styles.facts}>
          <div>
            <dt>Базовый адрес API</dt>
            <dd className={styles.mono}>{getApiBase()}</dd>
          </div>
          <div>
            <dt>Таймаут запроса</dt>
            <dd className={styles.mono}>30 с</dd>
          </div>
          <div>
            <dt>Политика кеша</dt>
            <dd className={styles.mono}>staleTime 30 с · без повтора на 4xx</dd>
          </div>
        </dl>
        <p className={styles.note}>
          Адрес задаётся переменной окружения при сборке и не меняется из интерфейса: подмена
          источника данных на лету сделала бы провенанс результата недоказуемым.
        </p>
      </Panel>

      <Panel className={styles.panel}>
        <h3 className={styles.heading}>Недоступно в текущем контракте API</h3>
        <ul className={styles.missing}>
          <li>Роль и права доступа — требуется endpoint capabilities (B-01 плана).</li>
          <li>Сессия, авто-блокировка и идентичность для аудита — не отдаются backend.</li>
          <li>Переключение языка RU/EN — интерфейс пока не интернационализирован.</li>
          <li>Ограничения буфера обмена и экспорта — задаются политикой на сервере.</li>
        </ul>
        <p className={styles.note}>
          Эти пункты §25 показаны списком, а не выключенными переключателями: неработающий
          переключатель безопасности выглядит как действующая защита.
        </p>
      </Panel>
    </div>
  );
}

export default SettingsPage;
