import { useMemo, useState } from 'react'
import type { PairConnection, PoseBin, ZoneMetric } from './types'
import { zoneLabel } from './timeline-data-contract'
import { SectionShell, Chip } from './SectionShell'
import type { SectionKey } from './section-meta'

/* V12: ЗОНАЛЬНЫЙ АТЛАС 2.0.
 * Что нового против V9:
 * 1. Фильтры: ракурс, период (год от/до), только FDR-пары.
 * 2. ХРОНОЛОГИЯ ЗОН: годы × 9 зон — средний raw rmse за год. Отвечает на
 *    вопрос «когда какая зона лица отличалась» — ключ к гипотезе накладок
 *    (зона «горит» годами = устойчивое отличие; вспыхнула на год = артефакт).
 * 3. Агрегированная карта 3×3 (средний rmse, n) с учётом фильтров.
 * 4. Детальная карта выбранной пары + список пар с зонами (клик → детали).
 * 5. Явное покрытие: зоны есть у N из M пар — до анализа, не после.
 * robustZ зон НЕ показываем (некалиброван) — только raw rmse. */
const ZONE_ORDER = ['x_high_low', 'x_high_center', 'x_high_high', 'x_center_low', 'x_center_center', 'x_center_high', 'x_low_low', 'x_low_center', 'x_low_high']
const POSES: (PoseBin | 'all')[] = ['all', 'frontal', 'left_light', 'right_light', 'left_mid', 'right_mid', 'left_deep', 'right_deep', 'left_profile', 'right_profile']

export function ZoneAtlas({ pairs, zones, selectedPairId, onSelectPair, onClose, onNavigate }: {
  pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>; selectedPairId: string | null
  onSelectPair: (id: string) => void; onClose: () => void; onNavigate?: (k: SectionKey) => void
}) {
  const [pose, setPose] = useState<'all' | PoseBin>('all')
  const [fromY, setFromY] = useState(1998)
  const [toY, setToY] = useState(2027)
  const [fdrOnly, setFdrOnly] = useState(false)
  const [query, setQuery] = useState('')

  /* Пары, попадающие под фильтры и имеющие зоны */
  const zonePairIds = useMemo(() => new Set(zones.keys()), [zones])
  const filtered = useMemo(() => pairs.filter(p => {
    if (!zonePairIds.has(p.pairId)) return false
    if (pose !== 'all' && p.poseBin !== pose) return false
    const y = Number(p.dateB.slice(0, 4))
    if (y < fromY || y > toY) return false
    if (fdrOnly && !p.mtSignificantFdr10) return false
    if (query && !(p.dateA + p.dateB + p.poseBin).includes(query)) return false
    return true
  }).sort((a, b) => Number(b.mtSignificantFdr10) - Number(a.mtSignificantFdr10) || b.dateB.localeCompare(a.dateB)), [pairs, zones, zonePairIds, pose, fromY, toY, fdrOnly, query]) // eslint-disable-line react-hooks/exhaustive-deps

  /* Агрегаты по зонам (только measured) */
  const aggregates = useMemo(() => {
    const agg: Record<string, { sum: number; n: number; total: number }> = {}
    for (const z of ZONE_ORDER) agg[z] = { sum: 0, n: 0, total: 0 }
    for (const id of new Set(filtered.map(p => p.pairId))) {
      for (const z of zones.get(id) ?? []) {
        const cell = agg[z.zone]
        if (!cell) continue
        cell.total++
        if (z.status === 'measured' && z.rmse != null) { cell.sum += z.rmse; cell.n++ }
      }
    }
    return agg
  }, [filtered, zones])
  const maxAvg = Math.max(0.001, ...ZONE_ORDER.map(z => { const a = aggregates[z]; return a.n ? a.sum / a.n : 0 }))

  /* Хронология зон: годы × 9 зон (средний rmse по измеренным) */
  const zoneTimeline = useMemo(() => {
    const years = new Set<number>()
    const data = new Map<number, Record<string, { sum: number; n: number }>>()
    for (const p of filtered) {
      const y = Number(p.dateB.slice(0, 4))
      years.add(y)
      for (const z of zones.get(p.pairId) ?? []) {
        if (z.status !== 'measured' || z.rmse == null) continue
        let cell = data.get(y)
        if (!cell) { cell = {}; data.set(y, cell) }
        const rec = (cell[z.zone] ??= { sum: 0, n: 0 })
        rec.sum += z.rmse; rec.n++
      }
    }
    const ys = [...years].sort((a, b) => a - b)
    const grid = ys.map(y => {
      const cell = data.get(y) ?? {}
      return {
        year: y,
        cells: ZONE_ORDER.map(zn => {
          const r = cell[zn]
          return r && r.n ? { avg: r.sum / r.n, n: r.n } : null
        }),
      }
    })
    const maxAvgAll = Math.max(0.001, ...grid.flatMap(g => g.cells).map(c => c?.avg ?? 0))
    return { grid, maxAvgAll }
  }, [filtered, zones])

  const currentId = useMemo(() => {
    if (selectedPairId && filtered.some(p => p.pairId === selectedPairId)) return selectedPairId
    return filtered[0]?.pairId ?? null
  }, [selectedPairId, filtered])
  const currentPair = pairs.find(p => p.pairId === currentId) ?? null
  const pairZones = currentId ? zones.get(currentId) ?? [] : []
  const maxR = Math.max(0.001, ...pairZones.filter(z => z.status === 'measured' && z.rmse != null).map(z => z.rmse!))
  const topZones = [...pairZones].filter(z => z.status === 'measured' && z.rmse != null).sort((a, b) => b.rmse! - a.rmse!).slice(0, 5)

  const resetFilters = () => { setPose('all'); setFromY(1998); setToY(2027); setFdrOnly(false); setQuery('') }

  return (
    <SectionShell title="Зональный атлас" current="atlas" onNavigate={onNavigate} onClose={onClose}
      scope={`${filtered.length} пар с зонами из ${zonePairIds.size} · измерено ${ZONE_ORDER.reduce((s, z) => s + aggregates[z].n, 0)} ячеек`}
      help={<>3×3 сетка: <b>x_{'{верх|центр|низ}'}_{'{лево|центр|право}'}</b>. Показывается <b>raw rmse</b> — robustZ зон в текущем экспорте некалиброван и не показывается. «Хронология зон» — средний rmse за год: устойчиво «горящая» зона годами = устойчивое отличие; вспышка на 1–2 года = возможный артефакт. Клик по ячейке хронологии — фильтр по году.</>}
      filters={<div className="sec-filters-row">
        <select value={pose} onChange={e => setPose(e.target.value as PoseBin | 'all')} aria-label="Ракурс">
          {POSES.map(ps => <option key={ps} value={ps}>{ps === 'all' ? 'Все ракурсы' : ps}</option>)}
        </select>
        <label>с <input type="number" min={1998} max={2027} value={fromY} onChange={e => setFromY(Number(e.target.value))} aria-label="Год с" /></label>
        <label>по <input type="number" min={1998} max={2027} value={toY} onChange={e => setToY(Number(e.target.value))} aria-label="Год по" /></label>
        <Chip active={fdrOnly} onClick={() => setFdrOnly(v => !v)} title="Только FDR-значимые пары">◆ FDR10</Chip>
        <input className="sec-query" placeholder="Поиск по датам…" value={query} onChange={e => setQuery(e.target.value)} aria-label="Поиск пары" />
        <Chip active={false} onClick={resetFilters} title="Сбросить фильтры">Сброс</Chip>
      </div>}
      footer={<span className="sec-foot-note">Зоны есть у {zonePairIds.size} из {pairs.length} пар ({pairs.length ? Math.round(zonePairIds.size / pairs.length * 100) : 0}%) — вне этих пар зональная локализация недоступна. Клик по паре в списке — детальная карта.</span>}>
      <div className="za2">
        {/* Хронология зон */}
        <div className="sec-card">
          <h3>Хронология зон <small>средний raw rmse за год (только measured); клик по ячейке — фильтр года</small></h3>
          {zoneTimeline.grid.length === 0 && <p className="sec-note">Нет данных под фильтрами.</p>}
          <div className="zt-grid" style={{ gridTemplateColumns: `70px repeat(${zoneTimeline.grid.length}, minmax(12px, 1fr))` }}>
            <div className="zt-corner" />
            {zoneTimeline.grid.map(g => <div key={g.year} className={`zt-year ${g.year >= fromY && g.year <= toY ? '' : 'dim'}`} onClick={() => { setFromY(g.year); setToY(g.year) }} title={`${g.year} — клик: показать только этот год`}>{String(g.year).slice(2)}</div>)}
            {ZONE_ORDER.map((zn, zi) => (
              <div key={zn} className="zt-row">
                <div className="zt-label">{zoneLabel(zn)}</div>
                {zoneTimeline.grid.map(g => {
                  const c = g.cells[zi]
                  return <div key={g.year} className={`zt-cell ${c ? '' : 'na'}`}
                    style={c ? { background: `rgba(233,115,102,${0.12 + (c.avg / zoneTimeline.maxAvgAll) * 0.88})` } : undefined}
                    title={c ? `${zoneLabel(zn)} ${g.year}: rmse ${c.avg.toFixed(4)} (n=${c.n})` : `${zoneLabel(zn)} ${g.year}: нет измерений`} />
                })}
              </div>
            ))}
          </div>
        </div>

        <div className="za2-cols">
          {/* Агрегированная карта */}
          <div className="sec-card">
            <h3>Средняя RMSE по зонам <small>по всем парам под фильтрами</small></h3>
            <div className="za-3x3">
              {ZONE_ORDER.map(zn => {
                const a = aggregates[zn]
                const avg = a.n ? a.sum / a.n : null
                return <div key={zn} className="za-cell" style={{ background: `rgba(94,159,232,${avg == null ? 0 : avg / maxAvg})` }}>
                  <div className="za-cell-label">{zoneLabel(zn)}</div>
                  <div className="za-cell-val">RMSE {avg == null ? '—' : avg.toFixed(4)}</div>
                  <div className="za-cell-val">n={a.n}/{a.total}</div>
                </div>
              })}
            </div>
          </div>

          {/* Детальная карта пары */}
          <div className="sec-card">
            <h3>Детали пары</h3>
            {!currentPair && <p className="sec-note">Нет пар под фильтрами.</p>}
            {currentPair && <>
              <p className="za-pair-h">{currentPair.dateA} → {currentPair.dateB} · {currentPair.poseBin} · {currentPair.pairType} · z {currentPair.meshMaxRobustZ?.toFixed(1) ?? '—'} {currentPair.mtSignificantFdr10 && '· ◆ FDR10'}</p>
              <div className="za-3x3">
                {ZONE_ORDER.map(zn => {
                  const z = pairZones.find(x => x.zone === zn)
                  const measured = z?.status === 'measured' && z.rmse != null
                  const intensity = measured ? z.rmse! / maxR : 0
                  return <div key={zn} className={`za-cell ${measured ? '' : 'na'}`}
                    style={{ background: `rgba(94,159,232,${intensity})`, borderColor: z?.mtSignificantFdr10 ? '#de9255' : '#2a3340' }}
                    title={`${zoneLabel(zn)}: ${measured ? 'rmse ' + z!.rmse!.toFixed(4) + ' · p95 ' + (z!.p95?.toFixed(4) ?? '—') + ' · n=' + (z!.pointCount ?? '—') : 'не измерено'}`}>
                    <div className="za-cell-label">{zoneLabel(zn)}</div>
                    {measured ? <>
                      <div className="za-cell-val">RMSE {z!.rmse!.toFixed(4)}</div>
                      <div className="za-cell-val">P95 {z!.p95?.toFixed(4) ?? '—'}</div>
                      <div className="za-cell-val">Δ ({z!.signedX?.toFixed(3)}, {z!.signedY?.toFixed(3)}, {z!.signedZ?.toFixed(3)})</div>
                      {z!.mtSignificantFdr10 && <div className="za-fdr">FDR10</div>}
                    </> : <div className="za-cell-na">не измерено</div>}
                  </div>
                })}
              </div>
              <h4 className="za-top-h">Топ-зоны по rmse</h4>
              <div className="za-top">
                {topZones.length === 0 && <span className="sec-note">нет измерений</span>}
                {topZones.map(z => <span key={z.zone} className="za-top-chip">{zoneLabel(z.zone)} {z.rmse!.toFixed(4)}</span>)}
              </div>
            </>}
          </div>

          {/* Список пар */}
          <div className="sec-card">
            <h3>Пары с зонами <small>{filtered.length} под фильтрами</small></h3>
            <div className="za-list">
              {filtered.map(p => (
                <button key={p.pairId} data-hit className={`za-item ${p.pairId === currentId ? 'active' : ''}`} onClick={() => onSelectPair(p.pairId)}>
                  <span className="za-item-d">{p.dateA} → {p.dateB}</span>
                  <span className="za-item-p">{p.poseBin}</span>
                  <span className="za-item-z">z {p.meshMaxRobustZ?.toFixed(1) ?? '—'}</span>
                  {p.mtSignificantFdr10 && <span className="za-fdr">FDR10</span>}
                </button>
              ))}
              {filtered.length === 0 && <p className="sec-note">Ничего не найдено — измените фильтры.</p>}
            </div>
          </div>
        </div>
      </div>
    </SectionShell>
  )
}
