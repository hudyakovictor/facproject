import { useState } from "react";
import { PhotoImage } from "../../shared/ui/PhotoImage";
import styles from "./pair.module.css";

/**
 * Главный холст A/B (§11.4).
 *
 * Режимы: рядом, наложение, мигание, шторка. Каждый отвечает на свой вопрос:
 * «рядом» — общий вид, «наложение» — совпадение контуров, «мигание» — что
 * сдвинулось, «шторка» — граница между кадрами под контролем пользователя.
 *
 * 🚨 WARNING: «разностное изображение» из спеки здесь **не реализовано**.
 * Честная разность требует совмещения кадров по геометрии; вычитание двух
 * произвольных JPEG в браузере даст картинку, которая выглядит как измерение,
 * но измеряет разницу кадрирования и освещения. Такая картинка опаснее её
 * отсутствия, поэтому режим отключён с объяснением, а не сымитирован.
 *
 * Мигание переключается пользователем, а не таймером: автоматическое мигание —
 * это анимация, которую нельзя остановить на нужном кадре, и она провоцирует
 * приступы у светочувствительных пользователей.
 */

export type CanvasMode = "side-by-side" | "overlay" | "blink" | "split";

const MODES: ReadonlyArray<{ id: CanvasMode; label: string; hint: string }> = [
  { id: "side-by-side", label: "Рядом", hint: "Оба кадра целиком, без совмещения." },
  {
    id: "overlay",
    label: "Наложение",
    hint: "B поверх A с регулируемой непрозрачностью. Кадры не совмещены по геометрии — это визуальное сопоставление, а не измерение.",
  },
  {
    id: "blink",
    label: "Мигание",
    hint: "Переключение A/B вручную: глаз замечает смещение лучше, чем при одновременном показе.",
  },
  { id: "split", label: "Шторка", hint: "Вертикальная граница между A и B, положение задаётся ползунком." },
];

export function ABCanvas({
  photoA,
  photoB,
  labelA,
  labelB,
}: {
  photoA: string;
  photoB: string;
  labelA: string;
  labelB: string;
}) {
  const [mode, setMode] = useState<CanvasMode>("side-by-side");
  const [opacity, setOpacity] = useState(50);
  const [split, setSplit] = useState(50);
  const [blinkB, setBlinkB] = useState(false);

  const active = MODES.find((item) => item.id === mode) ?? MODES[0];

  return (
    <section className={styles.panel} aria-label="Сопоставление кадров A и B">
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>ХОЛСТ A/B</span>
        <div className={styles.modeBar} role="group" aria-label="Режим сопоставления">
          {MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={mode === item.id}
              onClick={() => setMode(item.id)}
              title={item.hint}
              className={styles.modeButton}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {mode === "side-by-side" && (
        <div className={styles.sideBySide}>
          <figure className={styles.figure}>
            <PhotoImage photoId={photoA} alt={`Кадр A: ${labelA}`} variant="contain" className={styles.canvasImage} />
            <figcaption className={styles.figureCaption}>A · {labelA}</figcaption>
          </figure>
          <figure className={styles.figure}>
            <PhotoImage photoId={photoB} alt={`Кадр B: ${labelB}`} variant="contain" className={styles.canvasImage} />
            <figcaption className={styles.figureCaption}>B · {labelB}</figcaption>
          </figure>
        </div>
      )}

      {mode === "overlay" && (
        <>
          <div className={styles.stack}>
            <PhotoImage photoId={photoA} alt={`Кадр A: ${labelA}`} variant="contain" className={styles.canvasImage} />
            <div className={styles.stackTop} style={{ opacity: opacity / 100 }}>
              <PhotoImage
                photoId={photoB}
                alt={`Кадр B поверх A: ${labelB}`}
                variant="contain"
                className={styles.canvasImage}
              />
            </div>
          </div>
          <label className={styles.sliderRow}>
            Непрозрачность B
            <input
              type="range"
              min={0}
              max={100}
              value={opacity}
              onChange={(event) => setOpacity(Number(event.target.value))}
              aria-label="Непрозрачность кадра B"
            />
            <span className={styles.sliderValue}>{opacity}%</span>
          </label>
        </>
      )}

      {mode === "blink" && (
        <>
          <div className={styles.stack}>
            <PhotoImage
              photoId={blinkB ? photoB : photoA}
              alt={blinkB ? `Показан кадр B: ${labelB}` : `Показан кадр A: ${labelA}`}
              variant="contain"
              className={styles.canvasImage}
            />
          </div>
          <div className={styles.sliderRow}>
            <button
              type="button"
              className={styles.modeButton}
              onClick={() => setBlinkB((current) => !current)}
              aria-pressed={blinkB}
            >
              Показан {blinkB ? "B" : "A"} — переключить
            </button>
            <span className={styles.hint}>
              Переключение вручную: автоматическое мигание нельзя остановить на нужном кадре.
            </span>
          </div>
        </>
      )}

      {mode === "split" && (
        <>
          <div className={styles.stack}>
            <PhotoImage photoId={photoA} alt={`Кадр A: ${labelA}`} variant="contain" className={styles.canvasImage} />
            <div className={styles.stackTop} style={{ clipPath: `inset(0 0 0 ${split}%)` }}>
              <PhotoImage photoId={photoB} alt={`Кадр B: ${labelB}`} variant="contain" className={styles.canvasImage} />
            </div>
            <div className={styles.splitLine} style={{ left: `${split}%` }} aria-hidden="true" />
          </div>
          <label className={styles.sliderRow}>
            Положение шторки
            <input
              type="range"
              min={0}
              max={100}
              value={split}
              onChange={(event) => setSplit(Number(event.target.value))}
              aria-label="Положение шторки между кадрами"
            />
            <span className={styles.sliderValue}>{split}%</span>
          </label>
        </>
      )}

      <p className={styles.note}>{active.hint}</p>
      <p className={styles.note}>
        Разностное изображение, векторы смещения и тепловая карта зон на кадрах не
        строятся: для этого кадры нужно совместить по геометрии на стороне
        backend. Вычитание двух неcовмещённых снимков показало бы разницу
        кадрирования и освещения, а выглядело бы как измерение лица.
      </p>
    </section>
  );
}
