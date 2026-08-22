import { useMemo } from 'react'
import type { PairConnection, ZoneMetric } from './types'
import { SectionShell, MiniBars } from './SectionShell'
import type { SectionKey } from './section-meta'

/* V14: МЕТРИКИ ПАР — полный каталог извлечённых метрик и их отображения.
 *
 * Отвечает на вопрос «какие данные извлечены, где они показываются и что
 * они означают». Это систематический дом для полей, ранее не отображаемых:
 * - 6 пер-метричных статусов (семантика каждого z: шум/повышен/неуверенно)
 * - калибровочные референсы P95 (meshP95CalMedian/P95)
 * - PtPlane-P95 (метрика и её z)
 * - mtRoleDetail (caveat: 253 пары — p95_order_statistic_unreliable_below_20_points)
 * - expressionSource, evidenceLevel, analysisSpace (константы)
 * Плюс матрица «поле → где отображается» и распределения значений. */
const METRIC_ROWS: { id: string; label: string; get: (p: PairConnection) => number | null; statusOf: (p: PairConnection) => string }[] = [
  { id: 'RMSE', label: 'RMSE', get: p => p.meshRmse, statusOf: p => p.meshRmseStatus },
  { id: 'Median', label: 'Median', get: p => p.meshMedian, statusOf: p => p.meshMedianStatus },
  { id: 'P95', label: 'P95', get: p => p.meshP95, statusOf: p => p.meshP95Status },
  { id: 'PtPlane-RMSE', label: 'PtPlane-RMSE', get: p => p.meshPtPlaneRmse, statusOf: p => p.meshPtPlaneRmseStatus },
  { id: 'PtPlane-Median', label: 'PtPlane-Median', get: p => p.meshPtPlaneMedian, statusOf: p => p.meshPtPlaneMedianStatus },
  { id: 'PtPlane-P95', label: 'PtPlane-P95', get: p => p.meshPtPlaneP95, statusOf: p => p.meshPtPlaneP95Status },
]
const STATUS_LABEL: Record<string, string> = {
  mesh_elevated: 'повышен (выше калибровочной нормы)',
  within_mesh_noise: 'в пределах шума',
  mesh_elevated_but_uncertain: 'повышен, но неуверенно',
  '': 'без калибровочного статуса',
}
const STATUS_COLOR: Record<string, string> = {
  mesh_elevated: '#de9255', within_mesh_noise: '#72bc8f', mesh_elevated_but_uncertain: '#e97366', '': '#5a6573',
}

export function MetricProfiles({ pairs, zones, onClose, onNavigate }: {
  pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>; onClose: () => void
  onNavigate?: (k: SectionKey) => void
}) {
  const byMetric = useMemo(() => METRIC_ROWS.map(m => {
    const statuses: Record<string, number> = {}
    const cal: { median: number | null; p95: number | null }[] = []
    for (const p of pairs) {
      const st = m.statusOf(p) || ''
      statuses[st] = (statuses[st] ?? 0) + 1
      if (m.id === 'RMSE') cal.push({ median: p.meshRmseCalMedian, p95: p.meshRmseCalP95 })
      if (m.id === 'Median') cal.push({ median: p.meshMedianCalMedian, p95: p.meshMedianCalP95 })
      if (m.id === 'P95') cal.push({ median: p.meshP95CalMedian, p95: p.meshP95CalP95 })
    }
    const withCal = cal.filter(c => c.median != null && c.p95 != null)
    const calMedian = withCal.length ? withCal.reduce((s, c) => s + c.median!, 0) / withCal.length : null
    const calP95 = withCal.length ? withCal.reduce((s, c) => s + c.p95!, 0) / withCal.length : null
    return { ...m, statuses, calN: withCal.length, calMedian, calP95 }
  }), [pairs])

  const roleDetail = useMemo(() => {
    const c: Record<string, number> = {}
    for (const p of pairs) { const k = p.mtRoleDetail || '(пусто)'; c[k] = (c[k] ?? 0) + 1 }
    return Object.entries(c).sort((a, b) => b[1] - a[1])
  }, [pairs])

  const constants = useMemo(() => ({
    expressionSource: new Set(pairs.map(p => p.expressionSource)),
    evidenceLevel: new Set(pairs.map(p => p.meshEvidenceLevel)),
    analysisSpace: new Set(pairs.map(p => p.analysisSpace)),
    calibrated: pairs.filter(p => p.meshCalibratedMetricCount != null).length,
  }), [pairs])

  const zoneCals = useMemo(() => {
    const c: Record<string, number> = {}
    for (const list of zones.values()) for (const z of list) {
      const k = z.calibrationStatus || '(не измерено)'
      c[k] = (c[k] ?? 0) + 1
    }
    return c
  }, [zones])

  const mixedStatusPairs = useMemo(() => {
    const out: PairConnection[] = []
    for (const p of pairs) {
      const sts = new Set(METRIC_ROWS.map(m => m.statusOf(p) || '—'))
      if (sts.size > 1) out.push(p)
    }
    return out.sort((a, b) => (b.meshMaxRobustZ ?? 0) - (a.meshMaxRobustZ ?? 0))
  }, [pairs])

  const statusCount = useMemo(() => {
    const c: Record<string, number> = {}
    for (const p of pairs) { const k = p.meshRmseStatus || ''; c[k] = (c[k] ?? 0) + 1 }
    return c
  }, [pairs])

  const zDist = useMemo(() => {
    const buckets = [0, 0, 0, 0]
    for (const p of pairs) {
      const z = p.meshMaxRobustZ ?? 0
      if (z < 5) buckets[0]++
      else if (z < 10) buckets[1]++
      else if (z < 20) buckets[2]++
      else buckets[3]++
    }
    return [{ label: '<5', value: buckets[0] }, { label: '5–10', value: buckets[1] }, { label: '10–20', value: buckets[2] }, { label: '>20', value: buckets[3] }]
  }, [pairs])

  return (
    <SectionShell title="Метрики и поля" current="metrics" onNavigate={onNavigate} onClose={onClose}
      scope={`${pairs.length} пар · 68 полей пары · ${METRIC_ROWS.length} геометрических метрик`}
      help={<>Каталог извлечённых метрик пар и их отображения. <b>Пер-метричные статусы</b> — семантика каждого z (повышен/в пределах шума/неуверенно): z сам по себе не сигнал, статус решает. <b>Калибровочные референсы</b> — медиана и p95 калибровочного распределения для каждой метрики. <b>Роли FDR</b> — почему пара получила роль (внимание: 253 пары — «p95_order_statistic_unreliable_below_20_points»).</>}
      footer={<span className="sec-foot-note">Согласовано с таймлайном: 6 линий raw-геометрии + калибровочный коридор + статус-точки; z-suite дополнен 6-й метрикой PtPlane-P95; «S» в QC-событиях = неуверенный статус метрики.</span>}>
      <div className="mp2">
        <div className="sec-card mp-summary">
          <h3>Что здесь действительно важно</h3>
          <div className="mp-const">
            <span>Пар в анализе: <b>{pairs.length}</b></span>
            <span>Калиброваны: <b>{constants.calibrated}</b></span>
            <span>Повышенный RMSE: <b>{statusCount.mesh_elevated ?? 0}</b></span>
            <span>Смешанные статусы: <b>{mixedStatusPairs.length}</b></span>
          </div>
          <p className="sec-note">Для решения на первом экране достаточно статуса RMSE, robust-z и FDR10. Остальные поля нужны для проверки методики и аудита экспорта.</p>
        </div>
        <details className="sec-disclosure">
          <summary>Полный технический каталог: 6 метрик, статусы, FDR и калибровка</summary>
          <div className="sec-disclosure-body">
        <div className="sec-card">
          <h3>Шесть геометрических метрик: статусы и калибровка</h3>
          <table className="sec-table">
            <thead><tr><th>Метрика</th><th>Статусы (n пар)</th><th>Калибровка median/p95 (средние, n)</th><th>Где отображается</th></tr></thead>
            <tbody>
              {byMetric.map(m => (
                <tr key={m.id}>
                  <td><b>{m.id}</b></td>
                  <td>
                    {Object.entries(m.statuses).map(([st, n]) => (
                      <span key={st} className="mp-status" style={{ color: STATUS_COLOR[st] || '#9aa8b8' }} title={STATUS_LABEL[st] || st}>
                        {STATUS_LABEL[st] || st}: {n}
                      </span>
                    ))}
                  </td>
                  <td>{m.calN ? `${m.calMedian?.toFixed(4)} / ${m.calP95?.toFixed(4)} (n=${m.calN})` : '—'}</td>
                  <td className="mp-where">
                    {m.id === 'PtPlane-P95' ? 'таймлайн (raw-полоса + z-suite, V14)' : 'таймлайн (raw-полоса, V14) · попап'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="sec-note">Статусы читаются так: <span style={{ color: '#de9255' }}>повышен</span> — z выше калибровочной нормы; <span style={{ color: '#72bc8f' }}>в пределах шума</span> — норма; <span style={{ color: '#e97366' }}>неуверенно</span> — статус сомнителен (мало точек), на таймлайне такие пары помечаются «S». Пустой статус (104 пары) — калибровка метрики не применялась.</p>
        </div>

        <div className="mp2-cols">
          <div className="sec-card">
            <h3>Распределение max robust-z</h3>
            <MiniBars data={zDist} />
          </div>
          <div className="sec-card">
            <h3>Статус RMSE (все пары)</h3>
            <MiniBars data={Object.entries(statusCount).map(([k, n]) => ({ label: STATUS_LABEL[k] ? STATUS_LABEL[k].slice(0, 12) : (k || 'без статуса'), value: n }))} />
          </div>
          <div className="sec-card">
            <h3>Пары со смешанными статусами метрик ({mixedStatusPairs.length})</h3>
            <p className="sec-note">Разные метрики пары получили разные статусы — важно для интерпретации: часть сигнала в шуме, часть — выше.</p>
            <div className="mp-mixed">
              {mixedStatusPairs.slice(0, 12).map(p => (
                <div key={p.pairId} className="mp-mixed-row">
                  <span>{p.dateA} → {p.dateB}</span><span className="mp-z">z {p.meshMaxRobustZ?.toFixed(1) ?? '—'}</span>
                  <span className="mp-mixed-st">{METRIC_ROWS.map(m => m.statusOf(p) || '—').filter((v, i, a) => a.indexOf(v) === i).join(' · ')}</span>
                </div>
              ))}
              {mixedStatusPairs.length === 0 && <p className="sec-note">Нет пар со смешанными статусами.</p>}
            </div>
          </div>
        </div>

        <div className="sec-card">
          <h3>Роли FDR и их детализация (mtRole / mtRoleDetail)</h3>
          <table className="sec-table">
            <thead><tr><th>Детализация роли</th><th>Пар</th><th>Значение</th></tr></thead>
            <tbody>
              {roleDetail.map(([k, n]) => (
                <tr key={k}>
                  <td className="mp-mono">{k}</td>
                  <td>{n}</td>
                  <td className={k.includes('unreliable') ? 'mp-warn' : ''}>
                    {k.includes('unreliable') ? '⚠ p95-статистика ненадёжна при <20 точках — используется single-z fallback' : 'штатная p95-статистика порядка'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="sec-note">Все пары имеют mtRole=diagnostic_only: ни одна пара не является reportable-выводом — только кандидат к проверке. Это соответствует инварианту «кандидат ≠ вердикт».</p>
        </div>

        <div className="sec-card">
          <h3>Константы экспорта</h3>
          <div className="mp-const">
            <span>expressionSource: <b>{[...constants.expressionSource].join(', ') || '—'}</b></span>
            <span>evidenceLevel: <b>{[...constants.evidenceLevel].join(', ') || '—'}</b></span>
            <span>analysisSpace: <b>{[...constants.analysisSpace].join(', ') || '—'}</b></span>
            <span>пар с калибровочными счётчиками: <b>{constants.calibrated}</b> из {pairs.length}</span>
          </div>
        </div>

        <div className="sec-card">
          <h3>Калибровка зон (по строкам zone_metrics)</h3>
          <div className="mp-const">
            {Object.entries(zoneCals).sort().map(([k, n]) => <span key={k}>{k}: <b>{n}</b></span>)}
          </div>
          <p className="sec-note">zone robustZ некалиброван (insufficient_calibration) — разделы показывают raw rmse и магнитуды смещения, никогда не выдают их за z.</p>
        </div>
          </div>
        </details>
      </div>
    </SectionShell>
  )
}
