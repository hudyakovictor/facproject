import { useMemo } from 'react'
import type { PairConnection, ZoneMetric } from './types'
import { SectionShell } from './SectionShell'
import type { SectionKey } from './section-meta'

/* V12: КАЛИБРОВКА 2.0.
 * Что нового против V9:
 * 1. ЗДОРОВЬЕ РАКУРСОВ: таблица 9 ракурсов (пары, кадры, медиана/p90/max z,
 *    elevated, FDR, уверенность корзины по ТЗ). Уверенность вычисляется из
 *    фактической плотности данных как прокси калибровочной базы:
 *    <10 пар — low, 10–30 — medium, >30 — high (с явной пометкой «прокси»).
 * 2. РЕКОМЕНДАЦИИ: автоматически генерируются (слабые ракурсы, зоны
 *    некалиброваны, семейства с высокой медианой) — в V9 их не было.
 * 3. Гистограммы семейств: добавлены reference-линии q90 и бейджи n/elevated/FDR.
 * 4. Зоны: статус-таблица сохранена + вывод о некалиброванности robustZ. */
function quantile(sorted: number[], q: number): number | null {
  if (!sorted.length) return null
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * q))]
}
const POSES: { bin: string; label: string }[] = [
  { bin: 'frontal', label: 'Анфас' }, { bin: 'left_light', label: 'Левый 3/4 light' },
  { bin: 'right_light', label: 'Правый 3/4 light' }, { bin: 'left_mid', label: 'Левый 3/4 mid' },
  { bin: 'right_mid', label: 'Правый 3/4 mid' }, { bin: 'left_deep', label: 'Левый 3/4 deep' },
  { bin: 'right_deep', label: 'Правый 3/4 deep' }, { bin: 'left_profile', label: 'Левый профиль' },
  { bin: 'right_profile', label: 'Правый профиль' },
]
function confidence(pairs: number): { label: string; cls: string; note: string } {
  if (pairs < 10) return { label: 'низкая', cls: 'conf-low', note: 'прокси: <10 пар' }
  if (pairs < 30) return { label: 'средняя', cls: 'conf-med', note: 'прокси: 10–30 пар' }
  return { label: 'высокая', cls: 'conf-high', note: 'прокси: >30 пар' }
}

export function Calibration({ pairs, zones, onClose, onNavigate }: {
  pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>; onClose: () => void
  onNavigate?: (k: SectionKey) => void
}) {
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

  const perPose = useMemo(() => {
    const m: Record<string, { pairs: number; frames: number; zs: number[]; elevated: number; fdr: number }> = {}
    for (const bin of POSES) m[bin.bin] = { pairs: 0, frames: 0, zs: [], elevated: 0, fdr: 0 }
    for (const p of pairs) {
      const c = m[p.poseBin]
      if (!c) continue
      c.pairs++
      if (p.meshMaxRobustZ != null) c.zs.push(p.meshMaxRobustZ)
      if (p.meshCalibratedStatus === 'mesh_elevated') c.elevated++
      if (p.mtSignificantFdr10) c.fdr++
    }
    for (const c of Object.values(m)) c.zs.sort((a, b) => a - b)
    return m
  }, [pairs])

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

  /* Авто-рекомендации */
  const recommendations = useMemo(() => {
    const out: { level: 'warn' | 'info'; text: string }[] = []
    for (const p of POSES) {
      const c = perPose[p.bin]
      if (c.pairs === 0) out.push({ level: 'warn', text: `${p.label}: нет пар — ракурс не участвует в сравнениях` })
      else if (c.pairs < 10) out.push({ level: 'warn', text: `${p.label}: только ${c.pairs} пар — доказательная база слабая, выводы ограничены` })
    }
    const zoneUncal = [...zones.values()].flat().filter(z => z.status === 'measured' && z.calibrationStatus === 'insufficient_calibration').length
    if (zoneUncal > 0) out.push({ level: 'info', text: `Зональный robustZ некалиброван (${zoneUncal} measured-строк) — пайплайну нужен расширенный калибровочный набор; UI показывает raw rmse` })
    if (computed) out.push({ level: 'info', text: `Наибольшая медиана z у семейства «${computed.fam}» (${computed.med.toFixed(2)}) — длинные интервалы дают встроенный эффект, читайте в контексте интервалов` })
    if (out.length === 0) out.push({ level: 'info', text: 'Явных проблем не обнаружено' })
    return out
  }, [perPose, zones, computed])

  const globalMax = Math.max(1, ...pairs.map(p => p.meshMaxRobustZ ?? 0))

  return (
    <SectionShell title="Калибровка" current="calibration" onNavigate={onNavigate} onClose={onClose}
      scope={`${pairs.length} пар · ${zoneRows} зональных строк`}
      help={<>Калибровка = оценка шума метода. <b>robust-z</b> — насколько измерение пары отклоняется от калибровочной нормы. «Уверенность ракурса» здесь — прокси по плотности пар (реальная калибровочная база живёт в backend `/api/v1/calibration/health`). Гистограммы — распределение z по семействам пар (adjacent/baseline/rolling).</>}>
      <div className="cal2">
        <div className="sec-card">
          <h3>Здоровье ракурсов <small>прокси уверенности по плотности пар; медианы/p90 — по robust-z</small></h3>
          <table className="sec-table">
            <thead><tr><th>Ракурс</th><th>Пар</th><th>Медиана z</th><th>p90</th><th>max</th><th>elevated</th><th>FDR10</th><th>Уверенность</th></tr></thead>
            <tbody>
              {POSES.map(p => {
                const c = perPose[p.bin]
                const conf = confidence(c.pairs)
                return (
                  <tr key={p.bin}>
                    <td>{p.label}</td>
                    <td>{c.pairs}</td>
                    <td>{quantile(c.zs, 0.5)?.toFixed(2) ?? '—'}</td>
                    <td>{quantile(c.zs, 0.9)?.toFixed(2) ?? '—'}</td>
                    <td>{c.zs.length ? Math.max(...c.zs).toFixed(1) : '—'}</td>
                    <td>{c.elevated}</td>
                    <td>{c.fdr}</td>
                    <td><span className={`conf-badge ${conf.cls}`}>{conf.label}</span> <small className="sec-note">{conf.note}</small></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="sec-note">Уверенность — прокси по числу пар в ракурсе, не реальная калибровочная база (backend: `/api/v1/calibration/health`, 943 записи, 7 персон × 9 ракурсов).</p>
        </div>

        <div className="sec-card">
          <h3>Распределение robust-z по семействам пар</h3>
          {Object.entries(families).sort().map(([fam, d]) => (
            <div key={fam} className="cal-fam">
              <div className="cal-fam-head">
                <strong>{fam}</strong>
                <span>n={d.zs.length} · elevated {d.elevated} · FDR {d.fdr} · медиана {quantile(d.zs, 0.5)?.toFixed(2) ?? '—'} · p90 {quantile(d.zs, 0.9)?.toFixed(2) ?? '—'}</span>
              </div>
              <Histogram values={d.zs} max={globalMax} bins={24} q90={quantile(d.zs, 0.9)} />
            </div>
          ))}
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
          <p className="sec-note">zone robustZ некалиброван: UI везде показывает raw rmse, не z. Для калибровки зон пайплайну нужен расширенный референсный набор.</p>
        </div>

        <div className="sec-card">
          <h3>Рекомендации</h3>
          <div className="cal-rec">
            {recommendations.map((r, i) => <p key={i} className={`cal-rec-item ${r.level}`}>{r.level === 'warn' ? '⚠' : 'ℹ'} {r.text}</p>)}
          </div>
        </div>
      </div>
    </SectionShell>
  )
}

function Histogram({ values, max, bins, q90 }: { values: number[]; max: number; bins: number; q90: number | null }) {
  const counts = useMemo(() => {
    const c = new Array(bins).fill(0)
    for (const v of values) c[Math.min(bins - 1, Math.floor(v / max * bins))]++
    return c
  }, [values, max, bins])
  const peak = Math.max(1, ...counts)
  const q90X = q90 != null ? (q90 / max) * bins * 10 : null
  return (
    <svg className="cal-hist" viewBox={`0 0 ${bins * 10} 40`} preserveAspectRatio="none" aria-label="Гистограмма robust-z">
      {counts.map((n, i) => <rect key={i} x={i * 10 + 1} y={40 - (n / peak) * 38} width={8} height={(n / peak) * 38} rx={1} />)}
      {q90X != null && <line x1={q90X} y1={0} x2={q90X} y2={40} stroke="#eac26b" strokeWidth={1.5} strokeDasharray="2 2" />}
    </svg>
  )
}
