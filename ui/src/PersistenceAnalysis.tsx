import { useMemo } from 'react'
import type { PairConnection } from './types'
import { classifyPair } from './timeline-data-contract'

export function PersistenceAnalysis({ pairs, onClose }: { pairs: PairConnection[]; onClose: () => void }) {
  const chains = useMemo(() => {
    const cands = pairs.filter(p => p.mtSignificantFdr10).sort((a, b) => (a.dateB || '').localeCompare(b.dateB || ''))

    // Build adjacency: pairs sharing a date via photoB → photoA link
    const links = new Map<string, typeof cands>()
    for (const p of cands) {
      const key = p.photoB
      if (!links.has(key)) links.set(key, [])
      links.get(key)!.push(p)
    }

    // Detect chains: consecutive pairs where photoB of one = photoA of another
    const chains: { pairs: typeof cands; duration: string; linkCount: number; families: string[]; start: string; end: string }[] = []
    const used = new Set<string>()

    for (const p of cands) {
      if (used.has(p.pairId)) continue
      const chain = [p]
      used.add(p.pairId)

      let prev = p
      while (true) {
        const nextPairs = links.get(prev.photoB)
        const next = nextPairs?.find(x => x.photoA === prev.photoB && !used.has(x.pairId))
        if (!next || next.pairId === prev.pairId) break
        chain.push(next)
        used.add(next.pairId)
        prev = next
      }

      // Backwards
      let back = p
      while (true) {
        const prevPairs = [...cands].filter(x => x.photoB === back.photoA && !used.has(x.pairId))
        if (!prevPairs.length) break
        chain.unshift(prevPairs[0])
        used.add(prevPairs[0].pairId)
        back = prevPairs[0]
      }

      if (chain.length > 0) {
        const start = chain[0].dateB || '?'
        const end = chain[chain.length - 1].dateB || '?'
        const families = [...new Set(chain.map(x => x.pairType))]
        chains.push({
          pairs: chain,
          duration: chain.length > 1 ? `${chain[0].dateB} → ${chain[chain.length - 1].dateB}` : start,
          linkCount: chain.length,
          families,
          start, end,
        })
      }
    }

    return chains.sort((a, b) => b.linkCount - a.linkCount)
  }, [pairs])

  return (
    <div className="ps">
      <header className="ps-header"><h2>Persistence-анализ</h2><button onClick={onClose}>×</button></header>
      <div className="ps-body">
        <div className="ps-summary">
          <span>Всего цепочек: {chains.length}</span>
          <span>FDR-пар: {pairs.filter(p => p.mtSignificantFdr10).length}</span>
        </div>
        {chains.filter(c => c.linkCount > 1).map((chain, ci) => (
          <div key={ci} className="ps-chain">
            <div className="ps-chain-header">
              <strong>Цепочка {ci + 1}</strong>
              <span>{chain.duration}</span>
              <span>{chain.linkCount} звена(ьев)</span>
              <span className="ps-families">{chain.families.join(', ')}</span>
            </div>
            <div className="ps-links">
              {chain.pairs.map((p, pi) => {
                const cl = classifyPair(p)
                return (
                  <div key={p.pairId} className="ps-link">
                    <span className="ps-idx">{pi + 1}</span>
                    <span className={`ps-status ${cl.kind}`}>{cl.symbol}</span>
                    <span>{p.dateA} → {p.dateB}</span>
                    <span className="ps-z">z={p.meshMaxRobustZ?.toFixed(1) ?? '—'}</span>
                    <span className="ps-type">{p.pairType}</span>
                    <span className="ps-pose">{p.poseBin}</span>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
        {chains.filter(c => c.linkCount <= 1).length > 0 && (
          <div className="ps-card">
            <h4>Одиночные кандидаты ({chains.filter(c => c.linkCount <= 1).length})</h4>
            <p className="ps-note">Эти пары не образуют цепочек — единичные сигналы, требующие проверки на confounders.</p>
          </div>
        )}
      </div>
    </div>
  )
}