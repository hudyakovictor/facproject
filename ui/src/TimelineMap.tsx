import { useMemo } from 'react'
import type { Frame, PairConnection, PoseBin } from './types'
import { classifyPair } from './timeline-data-contract'
import { POSE_CONFIGS } from './types'

/* TIMELINE MAP (V10) — «Стратегическая карта» архива (уровень L0 редизайна).
 * Весь архив на одном экране: 9 ракурсов × годы. Ячейка = пары ракурса в году:
 * яркость = max robust-z, ◆ = есть candidate, рамка года = сигнал в ≥2 ракурсах
 * (независимая корроборация). Клик по ячейке → таймлайн ракурса в этом году.
 * Это MatrixView, ставший уровнем таймлайна, а не отдельным разделом. */
const CAND = new Set(['candidate', 'persistent'])

export function TimelineMap({ frames, pairs, activePose, onPick }: {
  frames: Frame[]
  pairs: PairConnection[]
  activePose: PoseBin
  onPick: (bin: PoseBin, year: number) => void
}) {
  const years = useMemo(() => [...new Set(frames.map(f => f.year))].sort(), [frames])
  const grid = useMemo(() => {
    const g: Record<string, Record<number, { n: number; cands: number; maxZ: number; fdr: number }>> = {}
    for (const p of pairs) {
      const y = Number(p.dateB.slice(0, 4))
      if (!Number.isFinite(y)) continue
      const cell = (g[p.poseBin] ??= {})[y] ??= { n: 0, cands: 0, maxZ: 0, fdr: 0 }
      cell.n++
      if (CAND.has(classifyPair(p).kind)) cell.cands++
      if (p.mtSignificantFdr10) cell.fdr++
      cell.maxZ = Math.max(cell.maxZ, p.meshMaxRobustZ ?? 0)
    }
    return g
  }, [pairs])
  const corroborated = useMemo(() => {
    const set = new Set<number>()
    for (const y of years) {
      const binsWithCand = POSE_CONFIGS.filter(pc => (grid[pc.bin]?.[y]?.cands ?? 0) > 0).length
      if (binsWithCand >= 2) set.add(y)
    }
    return set
  }, [grid, years])
  const maxZ = Math.max(1, ...pairs.map(p => p.meshMaxRobustZ ?? 0))

  return (
    <div className="tlmap" role="region" aria-label="Стратегическая карта архива: годы × ракурсы">
      <div className="tlmap-note">
        <strong>Стратегическая карта</strong> — весь архив 1999–2026 × 9 ракурсов.
        Ячейка: пары ракурса в году · яркость = max robust z · ◆ = кандидат ·
        <span className="tlmap-corro"> рамка года = сигнал в ≥2 ракурсах</span> ·
        приглушено = меньше 3 пар. Клик по ячейке — переход в таймлайн ракурса.
      </div>
      <div className="tlmap-scroll">
        <div className="tlmap-grid" style={{ gridTemplateColumns: `110px repeat(${years.length}, minmax(22px, 1fr))` }}>
          <div className="tlmap-corner" />
          {years.map(y => (
            <div key={y} className={`tlmap-col ${corroborated.has(y) ? 'corro' : ''}`}
              title={corroborated.has(y) ? 'Сигнал в ≥2 ракурсах' : undefined}>
              {String(y).slice(2)}
            </div>
          ))}
          {POSE_CONFIGS.map(pc => {
            const row = grid[pc.bin] ?? {}
            return (
              <div key={pc.bin} className="tlmap-row">
                <div className={`tlmap-row-label ${pc.bin === activePose ? 'active' : ''}`} style={{ color: pc.bin === activePose ? pc.color : undefined }}>
                  {pc.label}
                </div>
                {years.map(y => {
                  const cell = row[y]
                  if (!cell) return <div key={y} className="tlmap-cell empty" />
                  const sparse = cell.n < 3
                  const intensity = Math.min(1, cell.maxZ / maxZ)
                  return (
                    <button key={y} data-hit className={`tlmap-cell ${sparse ? 'sparse' : ''}`}
                      style={{ background: `rgba(94,159,232,${0.10 + intensity * 0.75})`, opacity: sparse ? 0.45 : 1 }}
                      onClick={() => onPick(pc.bin, y)}
                      title={`${pc.label} ${y}: ${cell.n} пар, ◆ ${cell.cands}, FDR ${cell.fdr}/${cell.n}, max z ${cell.maxZ.toFixed(1)}${sparse ? ' · мало данных' : ''}`}>
                      {cell.cands > 0 && <span className="tlmap-cand">◆</span>}
                      <span className="tlmap-n">{cell.n}</span>
                    </button>
                  )
                })}
              </div>
            )
          })}
        </div>
      </div>
      <div className="tlmap-hint">Клик по ячейке — таймлайн ракурса в этом году · Esc или кнопка «Карта» — вернуться к ленте</div>
    </div>
  )
}
