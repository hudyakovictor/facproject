import { useMemo, useState } from 'react'
import type { PairConnection, PoseBin } from './types'
import { classifyPair } from './timeline-data-contract'
import { SectionShell, Chip } from './SectionShell'
import type { SectionKey } from './section-meta'

/* V12: PERSISTENCE 2.0.
 * Что нового против V10:
 * 1. ВИЗУАЛИЗАЦИЯ ЦЕПОЧЕК: SVG-шкала годы × цепочки — каждая цепочка линией
 *    от dateA до dateB, цвет = длина; одиночные кандидаты — точками.
 * 2. Фильтры: минимальная длина цепочки, ракурс.
 * 3. Статистика: цепочек, FDR-пар, средняя длина, самый длинный период.
 * 4. Исправлено: backward-поиск берёт БЛИЖАЙШЕГО по дате предшественника
 *    (в V10 брался произвольный первый) и start цепочки = dateA (было dateB).
 * 5. Раздел добавлен в панель «Разделы» (в V10 рендер был, но пункта меню
 *    не было — раздел был недоступен). */
type PoseFilter = 'all' | PoseBin

export function PersistenceAnalysis({ pairs, onClose, onNavigate }: {
  pairs: PairConnection[]; onClose: () => void
  onNavigate?: (k: SectionKey) => void
}) {
  const [minLen, setMinLen] = useState(1)
  const [pose, setPose] = useState<PoseFilter>('all')

  const chains = useMemo(() => {
    const cands = pairs.filter(p => p.mtSignificantFdr10 && (pose === 'all' || p.poseBin === pose))
      .sort((a, b) => a.dateB.localeCompare(b.dateB))
    const links = new Map<string, PairConnection[]>()
    for (const p of cands) {
      const arr = links.get(p.photoB) ?? []
      arr.push(p)
      links.set(p.photoB, arr)
    }
    const chains: { pairs: PairConnection[]; linkCount: number; families: string[]; start: string; end: string; poseBins: string[] }[] = []
    const used = new Set<string>()
    for (const p of cands) {
      if (used.has(p.pairId)) continue
      const chain = [p]
      used.add(p.pairId)
      let prev = p
      while (true) {
        const next = links.get(prev.photoB)?.find(x => x.photoA === prev.photoB && !used.has(x.pairId))
        if (!next || next.pairId === prev.pairId) break
        chain.push(next)
        used.add(next.pairId)
        prev = next
      }
      /* V12-fix: ближайший по дате предшественник — хронологическая непрерывность */
      let back = p
      while (true) {
        const prevs = cands.filter(x => x.photoB === back.photoA && !used.has(x.pairId))
          .sort((a, b) => b.dateB.localeCompare(a.dateB))
        if (!prevs.length) break
        chain.unshift(prevs[0])
        used.add(prevs[0].pairId)
        back = prevs[0]
      }
      chains.push({
        pairs: chain,
        linkCount: chain.length,
        families: [...new Set(chain.map(x => x.pairType))],
        start: chain[0].dateA,
        end: chain[chain.length - 1].dateB,
        poseBins: [...new Set(chain.map(x => x.poseBin))],
      })
    }
    return chains.sort((a, b) => b.linkCount - a.linkCount)
  }, [pairs, pose])

  const filtered = useMemo(() => chains.filter(c => c.linkCount >= minLen), [chains, minLen])
  const stats = useMemo(() => ({
    chains: chains.length,
    fdr: pairs.filter(p => p.mtSignificantFdr10).length,
    avgLen: chains.length ? chains.reduce((s, c) => s + c.linkCount, 0) / chains.length : 0,
    max: chains.length ? Math.max(...chains.map(c => c.linkCount)) : 0,
  }), [chains, pairs])

  /* SVG-шкала: годы по X, цепочки линиями */
  const scale = useMemo(() => {
    const years = [...new Set(pairs.flatMap(p => [p.dateA.slice(0, 4), p.dateB.slice(0, 4)]))].map(Number).sort((a, b) => a - b)
    if (!years.length) return null
    const y0 = years[0], y1 = years[years.length - 1]
    const W = Math.max(600, (y1 - y0 + 1) * 34)
    const x = (date: string) => 40 + ((Number(date.slice(0, 4)) - y0) / Math.max(1, y1 - y0)) * (W - 60)
    const rowH = 22
    const rows = filtered.slice(0, 30)
    const H = rows.length * rowH + 36
    return { W, H, y0, y1, x, rows, rowH }
  }, [filtered, pairs])

  const posFilter: { v: PoseFilter; label: string }[] = [{ v: 'all', label: 'Все ракурсы' }, ...['frontal', 'left_profile', 'right_profile', 'left_light', 'right_light', 'left_mid', 'right_mid', 'left_deep', 'right_deep'].map(b => ({ v: b as PoseBin, label: b }))]

  return (
    <SectionShell title="Persistence" current="persistence" onNavigate={onNavigate} onClose={onClose}
      scope={`${stats.chains} цепочек · ${stats.fdr} FDR-пар · средняя длина ${stats.avgLen.toFixed(1)} · максимум ${stats.max}`}
      help={<>Persistence — цепочки подряд идущих FDR-кандидатов (фотоB одной пары = фотоA следующей). <b>Устойчивый сдвиг</b>, удержавшийся годами, — главный довод ТЗ; одиночный скачок без цепочки — слабый сигнал. Шкала: линия = цепочка (длина → цвет), точки = одиночные кандидаты.</>}
      filters={<div className="sec-filters-row">
        <Chip active={minLen === 1} onClick={() => setMinLen(1)} title="Показывать и одиночные кандидаты">≥1</Chip>
        <Chip active={minLen === 2} onClick={() => setMinLen(2)} title="Только цепочки из 2+ пар">≥2</Chip>
        <Chip active={minLen === 3} onClick={() => setMinLen(3)} title="Только длинные цепочки">≥3</Chip>
        <select value={pose} onChange={e => setPose(e.target.value as PoseFilter)} aria-label="Ракурс">
          {posFilter.map(p => <option key={p.v} value={p.v}>{p.label}</option>)}
        </select>
      </div>}
      footer={<span className="sec-foot-note">Показаны первые 30 цепочек шкалы; полный список ниже. Клик по паре в списке не меняет выделение таймлайна — навигация из очереди.</span>}>
      <div className="ps2">
        {scale && (
          <div className="sec-card">
            <h3>Шкала цепочек <small>{scale.y0}–{scale.y1} · цвет = длина</small></h3>
            <svg width="100%" viewBox={`0 0 ${scale.W} ${scale.H}`} className="ps-svg" role="img" aria-label="Цепочки кандидатов на шкале времени">
              {Array.from({ length: scale.y1 - scale.y0 + 1 }, (_, i) => scale.y0 + i).map(y => (
                <g key={y}>
                  <line x1={scale.x(String(y) + '-01-01')} y1={0} x2={scale.x(String(y) + '-01-01')} y2={scale.H - 20} className="ps-grid" />
                  <text x={scale.x(String(y) + '-01-01') + 2} y={scale.H - 6} className="ps-year">{y}</text>
                </g>
              ))}
              {scale.rows.map((c, i) => {
                const y = 8 + i * scale.rowH
                const len = c.linkCount
                const color = len >= 5 ? '#ef4444' : len >= 3 ? '#f97316' : len >= 2 ? '#eab308' : '#5e9fe8'
                const x1 = scale.x(c.start), x2 = scale.x(c.end)
                const single = len === 1
                return single
                  ? <circle key={i} cx={x1} cy={y} r={3} fill={color} className="ps-pt">
                      <title>{`${c.start} → ${c.end} · одиночный кандидат`}</title>
                    </circle>
                  : <g key={i}>
                      <line x1={x1} y1={y} x2={x2} y2={y} stroke={color} strokeWidth={4} strokeLinecap="round" className="ps-line">
                        <title>{`${c.start} → ${c.end} · ${len} звена · ${c.families.join(', ')}`}</title>
                      </line>
                      <circle cx={x1} cy={y} r={3} fill={color} />
                      <circle cx={x2} cy={y} r={3} fill={color} />
                      <text x={x2 + 4} y={y + 3} className="ps-len">{len}</text>
                    </g>
              })}
            </svg>
          </div>
        )}

        <div className="sec-card">
          <h3>Цепочки ({filtered.length})</h3>
          {filtered.length === 0 && <p className="sec-note">Нет цепочек под фильтрами.</p>}
          {filtered.map((c, ci) => (
            <div key={ci} className="ps-chain">
              <div className="ps-chain-header">
                <strong>Цепочка {ci + 1}</strong>
                <span>{c.start} → {c.end}</span>
                <span className={`ps-len-badge ${c.linkCount >= 5 ? 'long' : c.linkCount >= 3 ? 'mid' : ''}`}>{c.linkCount} зв.{c.linkCount > 1 ? 'а' : 'о'}</span>
                <span className="ps-families">{c.families.join(', ')}</span>
                <span className="ps-poses">{c.poseBins.join(', ')}</span>
              </div>
              <div className="ps-links">
                {c.pairs.map((p, pi) => {
                  const cl = classifyPair(p)
                  return (
                    <div key={p.pairId} className="ps-link">
                      <span className="ps-idx">{pi + 1}</span>
                      <span className={`ps-status ${cl.kind}`}>{cl.symbol}</span>
                      <span>{p.dateA} → {p.dateB}</span>
                      <span className="ps-z">z={p.meshMaxRobustZ?.toFixed(1) ?? '—'}</span>
                      <span className="ps-q">q={p.mtQValue?.toFixed(4) ?? '—'}</span>
                      <span className="ps-type">{p.pairType}</span>
                      <span className="ps-pose">{p.poseBin}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </SectionShell>
  )
}
