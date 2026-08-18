import { useMemo, useState } from 'react'
import type { Frame, PairConnection, PoseBin } from './types'
import { classifyPair } from './timeline-data-contract'
import { POSE_CONFIGS } from './types'
import { SectionShell, Chip } from './SectionShell'
import type { SectionKey } from './section-meta'

/* V12: КОРРОБОРАЦИЯ 2.0.
 * Что нового против V9:
 * 1. Детальная панель ячейки: клик по ячейке → список пар года+ракурса
 *    (даты, z, q, FDR, статус, решение) + кнопка перехода на таймлайн.
 * 2. Фильтры: период, минимальное число ракурсов для «корроборированного
 *    года» (2/3), только FDR.
 * 3. Ячейка показывает n пар + ◆ кандидатов + FDR-счётчик; tooltip расширен.
 * 4. Сводка корроборированных годов списком (клик — фильтр года).
 * Ось X — годы, ось Y — pose bins; нормировка: <3 пар — приглушено; z — max. */
const CAND = new Set(['candidate', 'persistent'])

export function MatrixView({ pairs, frames, onNavigate, onClose, onNavigateSection }: {
  pairs: PairConnection[]; frames: Frame[]
  onNavigate: (pose: PoseBin, frameId?: string) => void; onClose: () => void
  onNavigateSection?: (k: SectionKey) => void
}) {
  const [fromY, setFromY] = useState(1998)
  const [toY, setToY] = useState(2027)
  const [minBins, setMinBins] = useState(2)
  const [fdrOnly, setFdrOnly] = useState(false)
  const [focus, setFocus] = useState<{ bin: string; year: number } | null>(null)

  const years = useMemo(() => [...new Set(frames.map(f => f.year))].sort(), [frames])
  const grid = useMemo(() => {
    const g: Record<string, Record<number, { n: number; cands: number; maxZ: number; fdr: number; pairs: PairConnection[] }>> = {}
    for (const p of pairs) {
      const y = Number(p.dateB.slice(0, 4))
      if (!Number.isFinite(y)) continue
      const cell = (g[p.poseBin] ??= {})[y] ??= { n: 0, cands: 0, maxZ: 0, fdr: 0, pairs: [] }
      cell.n++
      if (CAND.has(classifyPair(p).kind)) cell.cands++
      if (p.mtSignificantFdr10) cell.fdr++
      cell.maxZ = Math.max(cell.maxZ, p.meshMaxRobustZ ?? 0)
      cell.pairs.push(p)
    }
    return g
  }, [pairs])
  const corroborated = useMemo(() => {
    const set = new Set<number>()
    for (const y of years) {
      if (y < fromY || y > toY) continue
      const binsWithCand = POSE_CONFIGS.filter(pc => (grid[pc.bin]?.[y]?.cands ?? 0) > 0).length
      const binsWithFdr = POSE_CONFIGS.filter(pc => (grid[pc.bin]?.[y]?.fdr ?? 0) > 0).length
      const criterion = fdrOnly ? binsWithFdr : binsWithCand
      if (criterion >= minBins) set.add(y)
    }
    return set
  }, [grid, years, fromY, toY, minBins, fdrOnly])
  const maxZ = Math.max(1, ...pairs.map(p => p.meshMaxRobustZ ?? 0))
  const firstFrameOf = (bin: string, year: number) => frames.find(f => f.poseBin === bin && f.year === year)?.id

  const focusPairs = focus ? (grid[focus.bin]?.[focus.year]?.pairs ?? []) : []

  return (
    <SectionShell title="Корроборация по периодам" current="matrix" onNavigate={onNavigateSection} onClose={onClose}
      scope={`${pairs.length} пар · корроборированных лет: ${corroborated.size}`}
      help={<>Независимое подтверждение по ТЗ = сигнал одного периода в <b>разных ракурсах</b>. Ячейка — пары ракурса в году; ◆ = кандидат; ярче = выше max z; приглушено = меньше 3 пар. Год с рамкой = сигнал в ≥{minBins} ракурсах. Клик по ячейке — список пар. Кандидат в одном ракурсе может быть артефактом; в двух и более — закономерность.</>}
      filters={<div className="sec-filters-row">
        <label>с <input type="number" min={1998} max={2027} value={fromY} onChange={e => setFromY(Number(e.target.value))} aria-label="Год с" /></label>
        <label>по <input type="number" min={1998} max={2027} value={toY} onChange={e => setToY(Number(e.target.value))} aria-label="Год по" /></label>
        <Chip active={minBins === 2} onClick={() => setMinBins(2)} title="Корроборация при сигнале в ≥2 ракурсах">≥2 ракурса</Chip>
        <Chip active={minBins === 3} onClick={() => setMinBins(3)} title="Строже: ≥3 ракурса">≥3 ракурса</Chip>
        <Chip active={fdrOnly} onClick={() => setFdrOnly(v => !v)} title="Считать только FDR-значимые пары">◆ только FDR</Chip>
      </div>}
      footer={<span className="sec-foot-note">Клик по ячейке — список пар года и ракурса; «→ таймлайн» — переход к ракурсу в этот год.</span>}>
      <div className="mx2">
        <div className="sec-card">
          <div className="mx-grid" style={{ gridTemplateColumns: `110px repeat(${years.length}, minmax(24px, 1fr))` }}>
            <div className="mx-corner" />
            {years.map(y => (
              <div key={y} className={`mx-col-label ${corroborated.has(y) ? 'corro' : ''}`} title={corroborated.has(y) ? `Сигнал в ≥${minBins} ракурсах` : undefined}
                onClick={() => { if (corroborated.has(y)) { setFromY(y); setToY(y); setFocus(null) } }}>
                {String(y).slice(2)}
              </div>
            ))}
            {POSE_CONFIGS.map(pc => {
              const row = grid[pc.bin] ?? {}
              return (
                <div key={pc.bin} className="mx-row">
                  <div className="mx-row-label">{pc.label}</div>
                  {years.map(y => {
                    const cell = row[y]
                    if (!cell) return <div key={y} className="mx-cell empty" />
                    const sparse = cell.n < 3
                    const intensity = Math.min(1, cell.maxZ / maxZ)
                    const isFocus = focus?.bin === pc.bin && focus?.year === y
                    return (
                      <button key={y} className={`mx-cell ${sparse ? 'sparse' : ''} ${isFocus ? 'focus' : ''}`} data-hit
                        style={{ background: `rgba(94,159,232,${0.12 + intensity * 0.75})`, opacity: sparse ? 0.45 : 1 }}
                        onClick={() => setFocus({ bin: pc.bin, year: y })}
                        title={`${pc.label} ${y}: ${cell.n} пар, ◆ ${cell.cands}, FDR ${cell.fdr}, max z ${cell.maxZ.toFixed(1)}${sparse ? ' · мало данных' : ''}`}>
                        {cell.cands > 0 && <span className="mx-cand">◆</span>}
                        {cell.fdr > 0 && <span className="mx-fdr">●</span>}
                        <span className="mx-n">{cell.n}</span>
                      </button>
                    )
                  })}
                </div>
              )
            })}
          </div>
        </div>

        {corroborated.size > 0 && (
          <div className="sec-card">
            <h3>Корроборированные годы <small>клик — показать только год</small></h3>
            <div className="mx-corro-years">
              {[...corroborated].sort().map(y => (
                <Chip key={y} active={fromY === y && toY === y} onClick={() => { setFromY(y); setToY(y); setFocus(null) }}>{y}</Chip>
              ))}
            </div>
          </div>
        )}

        {focus && (
          <div className="sec-card">
            <h3>Пары: {focus.bin} · {focus.year} <small>{focusPairs.length}</small></h3>
            {focusPairs.length === 0 && <p className="sec-note">Пар нет.</p>}
            <div className="mx-pairs">
              {[...focusPairs].sort((a, b) => (b.meshMaxRobustZ ?? 0) - (a.meshMaxRobustZ ?? 0)).map(p => {
                const cl = classifyPair(p)
                return (
                  <div key={p.pairId} className="mx-pair">
                    <span className="mx-pair-d">{p.dateA} → {p.dateB}</span>
                    <span className={`mx-pair-s ${cl.kind}`}>{cl.symbol} {cl.label}</span>
                    <span className="mx-pair-z">z {p.meshMaxRobustZ?.toFixed(1) ?? '—'}</span>
                    <span className="mx-pair-q">q {p.mtQValue?.toFixed(4) ?? '—'}</span>
                    {p.mtSignificantFdr10 && <span className="mx-pair-fdr">FDR10</span>}
                    <button className="mx-pair-go" data-hit onClick={() => { const fid = firstFrameOf(p.poseBin, Number(p.dateB.slice(0, 4))); onNavigate(p.poseBin as PoseBin, fid) }}>→ таймлайн</button>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </SectionShell>
  )
}
