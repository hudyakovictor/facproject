import { useMemo } from 'react'
import type { PairConnection, ZoneMetric } from './types'

/* Calibration V9 (фаза 5 плана). Исправления против V8-dev:
 * 1. НИКАКИХ констант-выводов: «семейство с макс. медианой z» вычисляется из
 *    данных на каждый рендер (в V8-dev «13.17» была зашита в текст — при смене
 *    данных текст бы врал).
 * 2. Добавлены SVG-гистограммы распределения robust-z по семействам (ТЗ просило
 *    распределения, а не только таблицу медиан).
 * 3. Типизация PairConnection/ZoneMetric вместо any[].
 * 4. Данные — из props (единый источник App), без повторных fetch.
 */
function quantile(sorted: number[], q: number): number | null {
  if (!sorted.length) return null
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * q))]
}

export function Calibration({ pairs, zones, onClose }: { pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>; onClose: () => void }) {
  const families = useMemo(() => {
    const f: Record<string, { zs: number[]; elevated: number; fdr: number }> = {}
    for (const p of pairs) {
      const fam = p.pairType || 'unknown'
      const cell = f[fam] ??= { zs: [], elevated: 0, fdr: 0 }
      if (p.meshMaxRobustZ != null) cell.zs.push(p.meshMaxRobustZ)
      if (p.meshCalibratedStatus === 'mesh_elevated') cell.elevated++
      if (p.mtSignificantFdr10) cell.fdr++
    }
    for (const d of Object.values(f)) d.zs.sort((a, b) => a - b)
    return f
  }, [pairs])

  // Вычисляемый вывод вместо хардкода: какое семейство сейчас имеет макс. медиану.
  const computed = useMemo(() => {
    let best: { fam: string; med: number } | null = null
    for (const [fam, d] of Object.entries(families)) {
      const med = quantile(d.zs, 0.5)
      if (med != null && (!best || med > best.med)) best = { fam, med }
    }
    return best
  }, [families])

  const zoneStats = useMemo(() => {
    const s: Record<string, number> = {}
    for (const list of zones.values()) for (const z of list) {
      const k = z.calibrationStatus || '(не измерено)'
      s[k] = (s[k] ?? 0) + 1
    }
    return s
  }, [zones])
  const zoneRows = useMemo(() => [...zones.values()].reduce((n, l) => n + l.length, 0), [zones])

  const globalMax = Math.max(1, ...pairs.map(p => p.meshMaxRobustZ ?? 0))

  return (
    <div className="section-overlay" role="dialog" aria-modal="true" aria-label="Калибровка">
      <header className="sec-header"><h2>Калибровка</h2><span className="sec-scope">все ракурсы · {pairs.length} пар · {zoneRows} зональных строк</span><button onClick={onClose} aria-label="Закрыть">×</button></header>
      <div className="sec-body cal-body">
        <div className="sec-card">
          <h3>Распределение robust-z по семействам пар</h3>
          {Object.entries(families).sort().map(([fam, d]) => (
            <div key={fam} className="cal-fam">
              <div className="cal-fam-head">
                <strong>{fam}</strong>
                <span>n={d.zs.length} · elevated {d.elevated} · FDR {d.fdr} · медиана {quantile(d.zs, 0.5)?.toFixed(2) ?? '—'} · p90 {quantile(d.zs, 0.9)?.toFixed(2) ?? '—'}</span>
              </div>
              <Histogram values={d.zs} max={globalMax} bins={24} />
            </div>
          ))}
          {computed && <p className="sec-note">Наибольшая медиана z сейчас у «{computed.fam}» ({computed.med.toFixed(2)}) — вычислено из текущих данных; длинные интервалы дают встроенный эффект, читайте семейство в контексте его интервалов.</p>}
        </div>

        <div className="sec-card">
          <h3>Калибровка зон</h3>
          <table className="sec-table">
            <thead><tr><th>Статус</th><th>Строк</th><th>Доля</th></tr></thead>
            <tbody>
              {Object.entries(zoneStats).sort().map(([s, n]) => (
                <tr key={s}><td>{s}</td><td>{n}</td><td>{zoneRows ? (n / zoneRows * 100).toFixed(0) + '%' : '—'}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="sec-note">zone robustZ некалиброван: UI везде показывает raw rmse, не z. Для калибровки зон пайплайну нужен расширенный референсный набор — это этап backend, не интерфейса.</p>
        </div>

        <div className="sec-card">
          <h3>Диагностика текстур (UV / skin) — diagnostic only</h3>
          <p className="sec-note">skinAuthenticityScore, uvMeanConfidence, noiseResidualMean, gradientAnisotropy — не identity evidence; указывают на confounders (освещение, сжатие, ретушь), но не участвуют в определении candidate.</p>
        </div>
      </div>
    </div>
  )
}

function Histogram({ values, max, bins }: { values: number[]; max: number; bins: number }) {
  const counts = useMemo(() => {
    const c = new Array(bins).fill(0)
    for (const v of values) c[Math.min(bins - 1, Math.floor(v / max * bins))]++
    return c
  }, [values, max, bins])
  const peak = Math.max(1, ...counts)
  return (
    <svg className="cal-hist" viewBox={`0 0 ${bins * 10} 40`} preserveAspectRatio="none" aria-label="Гистограмма robust-z">
      {counts.map((n, i) => <rect key={i} x={i * 10 + 1} y={40 - (n / peak) * 38} width={8} height={(n / peak) * 38} rx={1} />)}
    </svg>
  )
}
