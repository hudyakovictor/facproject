import { useMemo } from 'react'
import type { Frame, PairConnection, PoseBin } from './types'
import { classifyPair } from './timeline-data-contract'
import { POSE_CONFIGS } from './types'

/* MatrixView V9 — КОРРОБОРАЦИЯ ПО ПЕРИОДАМ вместо матрицы пар 9×9 (фаза 4).
 * Почему смена подхода: cross-bin пар в данных не существует — в V8-dev
 * матрица была заполнена только по диагонали (b = a) и ничего не показывала.
 * Независимое подтверждение по ТЗ = сигнал одного периода в РАЗНЫХ ракурсах.
 * Ось X — годы, ось Y — pose bins; ячейка — пары ракурса в этом году;
 * столбец с кандидатами в ≥2 ракурсах подсвечивается как корроборированный.
 * Клик по ячейке → переход в таймлайн (pose + первый кадр года).
 * Нормировка: ячейки с <3 пар приглушены («мало данных»); z — max, не среднее
 * (среднее по 1–2 парам вводит в заблуждение).
 */
const CAND = new Set(['candidate', 'persistent'])

export function MatrixView({ pairs, frames, onNavigate, onClose }: {
  pairs: PairConnection[]; frames: Frame[]
  onNavigate: (pose: PoseBin, frameId?: string) => void; onClose: () => void
}) {
  const years = useMemo(() => [...new Set(frames.map(f => f.year))].sort(), [frames])
  const grid = useMemo(() => {
    const g: Record<string, Record<number, { n: number; cands: number; maxZ: number; fdr: number }>> = {}
    for (const p of pairs) {
      const y = Number(p.dateB.slice(0, 4))
      if (!g[p.poseBin]) g[p.poseBin] = {}
      const cell = g[p.poseBin][y] ??= { n: 0, cands: 0, maxZ: 0, fdr: 0 }
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
  const firstFrameOf = (bin: string, year: number) => frames.find(f => f.poseBin === bin && f.year === year)?.id

  return (
    <div className="section-overlay" role="dialog" aria-modal="true" aria-label="Корроборация по периодам">
      <header className="sec-header"><h2>Корроборация по периодам</h2><span className="sec-scope">все ракурсы · {pairs.length} пар · корроборированных лет: {corroborated.size}</span><button onClick={onClose} aria-label="Закрыть">×</button></header>
      <div className="sec-body mx-body">
        <p className="sec-note">Ячейка — пары ракурса в году. ◆ = есть candidate; рамка года = сигнал в ≥2 ракурсах (независимое подтверждение). Ярче = выше max z. Приглушено = меньше 3 пар. Клик — переход в таймлайн.</p>
        <div className="mx-grid" style={{ gridTemplateColumns: `90px repeat(${years.length}, minmax(28px, 1fr))` }}>
          <div className="mx-corner" />
          {years.map(y => <div key={y} className={`mx-col-label ${corroborated.has(y) ? 'corro' : ''}`} title={corroborated.has(y) ? 'Сигнал в ≥2 ракурсах' : ''}>{String(y).slice(2)}</div>)}
          {POSE_CONFIGS.map(pc => (
            <FragmentRow key={pc.bin} label={pc.label} bin={pc.bin} years={years} grid={grid[pc.bin] ?? {}} maxZ={maxZ}
              onPick={y => { const fid = firstFrameOf(pc.bin, y); onNavigate(pc.bin, fid) }} />
          ))}
        </div>
      </div>
    </div>
  )
}

function FragmentRow({ label, bin, years, grid, maxZ, onPick }: {
  label: string; bin: string; years: number[]
  grid: Record<number, { n: number; cands: number; maxZ: number; fdr: number }>
  maxZ: number; onPick: (year: number) => void
}) {
  return (
    <>
      <div className="mx-row-label">{label}</div>
      {years.map(y => {
        const cell = grid[y]
        if (!cell) return <div key={y} className="mx-cell empty" />
        const sparse = cell.n < 3
        const intensity = Math.min(1, cell.maxZ / maxZ)
        return (
          <button key={y} className={`mx-cell ${sparse ? 'sparse' : ''}`} data-hit
            style={{ background: `rgba(94,159,232,${0.12 + intensity * 0.75})`, opacity: sparse ? 0.45 : 1 }}
            onClick={() => onPick(y)}
            title={`${bin} ${y}: ${cell.n} пар, ◆ ${cell.cands}, FDR ${cell.fdr}/${cell.n}, max z ${cell.maxZ.toFixed(1)}${sparse ? ' · мало данных' : ''}`}>
            {cell.cands > 0 && <span className="mx-cand">◆</span>}
            <span className="mx-n">{cell.n}</span>
          </button>
        )
      })}
    </>
  )
}
