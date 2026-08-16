import { useMemo, useState } from "react";
import { useLandmarks } from "../../shared/api/queries";

/**
 * Оверлей ландмарков A→B (§11.5).
 *
 * Почему не поверх фотографии: точки в пространстве `original` заданы в
 * пикселях исходного снимка, а размер снимка API не сообщает. Наложить
 * их на `object-fit: contain` можно только угадав масштаб — получится
 * картинка, которая выглядит как измерение, но показывает ошибку масштаба.
 *
 * Поэтому сравнение идёт в пространстве `aligned`: оба облака уже приведены
 * Stage 2 в общую систему координат, и разность между точками с одинаковым
 * индексом — реальное смещение, а не разница кадрирования.
 *
 * Обе выборки нормируются одним и тем же bbox: отдельная нормировка
 * каждого облака совместила бы их и стёрла измеряемый сдвиг.
 */

const LANDMARK_COUNT = 134;
const SPACE = "aligned";
const VIEW = 100;

type Point = readonly number[];

function bbox(clouds: Point[][]) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const cloud of clouds) {
    for (const point of cloud) {
      const x = point[0] ?? 0;
      const y = point[1] ?? 0;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null;
  const span = Math.max(maxX - minX, maxY - minY, 1e-6);
  return { minX, minY, maxX, maxY, span };
}

export function LandmarkOverlay({
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
  const a = useLandmarks(photoA, LANDMARK_COUNT, SPACE);
  const b = useLandmarks(photoB, LANDMARK_COUNT, SPACE);
  const [showVectors, setShowVectors] = useState(true);
  const [gain, setGain] = useState(1);

  const geometry = useMemo(() => {
    const pointsA = (a.data?.points ?? []) as Point[];
    const pointsB = (b.data?.points ?? []) as Point[];
    if (pointsA.length === 0 || pointsA.length !== pointsB.length) return null;
    const box = bbox([pointsA, pointsB]);
    if (!box) return null;
    const project = (point: Point) => ({
      x: (((point[0] ?? 0) - box.minX) / box.span) * VIEW,
      // Экранная ось Y растёт вниз, геометрическая — вверх.
      y: VIEW - (((point[1] ?? 0) - box.minY) / box.span) * VIEW,
    });
    const pairs = pointsA.map((point, index) => {
      const other = pointsB[index] ?? point;
      const dx = (other[0] ?? 0) - (point[0] ?? 0);
      const dy = (other[1] ?? 0) - (point[1] ?? 0);
      const dz = (other[2] ?? 0) - (point[2] ?? 0);
      return {
        index,
        a: project(point),
        b: project(other),
        distance: Math.sqrt(dx * dx + dy * dy + dz * dz),
      };
    });
    const distances = pairs.map((pair) => pair.distance).sort((x, y) => x - y);
    const median = distances[Math.floor(distances.length / 2)] ?? 0;
    const max = distances.at(-1) ?? 0;
    const top = [...pairs].sort((x, y) => y.distance - x.distance).slice(0, 5);
    return { pairs, median, max, top, unit: box.span };
  }, [a.data, b.data]);

  const pending = a.isLoading || b.isLoading;
  const failure = a.error ?? b.error;

  return (
    <section
      className="rounded-lg border border-line-default bg-surface-base p-4 space-y-3"
      aria-label="Смещение ландмарков между A и B"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="font-mono text-xs font-bold uppercase text-cyan-300">
            СМЕЩЕНИЕ ЛАНДМАРКОВ A→B
          </div>
          <div className="text-2xs text-ink-muted">
            {LANDMARK_COUNT} точек · пространство {SPACE} · A: {labelA} → B: {labelB}
          </div>
        </div>
        <div className="flex items-center gap-3 text-2xs font-mono">
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="checkbox"
              checked={showVectors}
              onChange={(event) => setShowVectors(event.target.checked)}
              className="h-3.5 w-3.5 accent-cyan-500"
            />
            векторы
          </label>
          <label className="flex items-center gap-1.5">
            усиление ×{gain}
            <input
              type="range"
              min={1}
              max={10}
              step={1}
              value={gain}
              onChange={(event) => setGain(Number(event.target.value))}
              aria-label="Усиление векторов смещения"
            />
          </label>
        </div>
      </div>

      {pending && <p className="text-xs text-ink-muted">Загрузка ландмарок…</p>}

      {!pending && failure ? (
        <p className="text-xs text-amber-300">
          Ландмарки недоступны для одного из кадров:{" "}
          {String((failure as { message?: string }).message ?? failure)}. Сопоставление точек
          не строится.
        </p>
      ) : null}

      {!pending && !failure && !geometry && (
        <p className="text-xs text-amber-300">
          Число точек в кадрах не совпадает — поточечное сравнение невозможно.
        </p>
      )}

      {geometry && (
        <>
          <div className="rounded border border-line-default bg-surface-canvas p-2">
            <svg
              viewBox={`-4 -4 ${VIEW + 8} ${VIEW + 8}`}
              className="h-[320px] w-full"
              role="img"
              aria-label={`Облака точек A и B, максимальное смещение ${geometry.max.toFixed(4)}`}
            >
              {showVectors &&
                geometry.pairs.map((pair) => (
                  <line
                    key={`v${pair.index}`}
                    x1={pair.a.x}
                    y1={pair.a.y}
                    x2={pair.a.x + (pair.b.x - pair.a.x) * gain}
                    y2={pair.a.y + (pair.b.y - pair.a.y) * gain}
                    stroke="var(--amber-400, #f59e0b)"
                    strokeWidth={0.35}
                    opacity={0.85}
                  />
                ))}
              {geometry.pairs.map((pair) => (
                <circle
                  key={`a${pair.index}`}
                  cx={pair.a.x}
                  cy={pair.a.y}
                  r={0.6}
                  fill="var(--cyan-400, #22d3ee)"
                />
              ))}
              {geometry.pairs.map((pair) => (
                <circle
                  key={`b${pair.index}`}
                  cx={pair.b.x}
                  cy={pair.b.y}
                  r={0.6}
                  fill="var(--violet-400, #a78bfa)"
                  opacity={0.9}
                />
              ))}
            </svg>
          </div>

          <div className="flex flex-wrap gap-4 text-2xs font-mono text-ink-muted">
            <span>
              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-cyan-400" />A
            </span>
            <span>
              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-violet-400" />B
            </span>
            <span>медиана смещения: {geometry.median.toFixed(4)}</span>
            <span>максимум: {geometry.max.toFixed(4)}</span>
            <span>единицы пространства {SPACE}, не миллиметры</span>
          </div>

          <table className="w-full text-2xs font-mono">
            <caption className="pb-1 text-left text-ink-muted">
              Точки с наибольшим смещением
            </caption>
            <thead className="text-ink-muted">
              <tr>
                <th className="py-1 text-left">индекс</th>
                <th className="py-1 text-right">смещение</th>
                <th className="py-1 text-right">относительно медианы</th>
              </tr>
            </thead>
            <tbody>
              {geometry.top.map((pair) => (
                <tr key={pair.index} className="border-t border-line-default">
                  <td className="py-1 text-left text-cyan-300">#{pair.index}</td>
                  <td className="py-1 text-right">{pair.distance.toFixed(4)}</td>
                  <td className="py-1 text-right">
                    {geometry.median > 0 ? `×${(pair.distance / geometry.median).toFixed(1)}` : "н/д"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="text-2xs text-ink-muted">
            Усиление растягивает только длину векторов на экране и не меняет числа в
            таблице. Смещение показано в выровненном пространстве Stage 2 и не является
            анатомической величиной без калибровки масштаба.
          </p>
        </>
      )}
    </section>
  );
}
