import { useMemo } from 'react'
import type { PairConnection, ZoneMetric } from './types'
import { classifyPair, zoneLabel, DATA_CONTRACT_VERSION } from './timeline-data-contract'
import type { DecisionEntry } from './App'

/* Report V9 (фаза 6 плана). Исправления против V8-dev:
 * 1. escapeHtml на всех интерполируемых значениях — в V8-dev HTML собирался
 *    сырыми строками (injection в экспортируемый файл).
 * 2. Решения — из props (live state App), а не useMemo(localStorage) — отчёт
 *    всегда отражает текущие решения.
 * 3. Состав по ТЗ: gate-сводка, топ-3 зоны (RU), persistence, ограничения,
 *    provenance; шапка с датой генерации и версией контракта.
 * 4. Лексика: «Принято к отчёту» вместо «Подтверждено» (инвариант).
 */
const esc = (s: unknown) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export function Report({ pairs, zones, decisions, onClose }: {
  pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>
  decisions: Record<string, DecisionEntry>; onClose: () => void
}) {
  const accepted = useMemo(() =>
    pairs.filter(p => decisions[p.pairId]?.decision === 'accepted').sort((a, b) => (b.meshMaxRobustZ ?? 0) - (a.meshMaxRobustZ ?? 0)),
    [pairs, decisions])
  const counts = useMemo(() => ({
    fdr: pairs.filter(p => p.mtSignificantFdr10).length,
    accepted: accepted.length,
    rejected: Object.values(decisions).filter(d => d.decision === 'rejected').length,
    more: Object.values(decisions).filter(d => d.decision === 'more_data').length,
  }), [pairs, decisions, accepted])

  const topZonesOf = (pairId: string) =>
    (zones.get(pairId) ?? []).filter(z => z.status === 'measured' && z.rmse != null)
      .sort((a, b) => (b.rmse ?? 0) - (a.rmse ?? 0)).slice(0, 3)

  const limitationsOf = (p: PairConnection) => {
    const out: string[] = []
    if (p.smileDetectedA !== p.smileDetectedB || p.jawOpenDetectedA !== p.jawOpenDetectedB) out.push('мимика различается')
    if ((p.meshVisibleFraction ?? 1) < 0.5) out.push(`низкая видимость ${(100 * (p.meshVisibleFraction ?? 0)).toFixed(0)}%`)
    if (p.meshCalibratedStatus !== 'mesh_elevated' && p.meshCalibratedStatus) out.push(`калибровка: ${p.meshCalibratedStatus}`)
    if (p.dateProvenanceLimited) out.push('датировка ограничена')
    if (p.nearDuplicatePair) out.push('near-duplicate')
    if (!out.length) out.push('явных ограничений не отмечено')
    return out
  }

  const generateHTML = () => {
    const rows = accepted.map(p => {
      const zrows = topZonesOf(p.pairId).map(z => `<li>${esc(zoneLabel(z.zone))}: rmse ${esc(z.rmse?.toFixed(4))}, p95 ${esc(z.p95?.toFixed(4))}, n=${esc(z.pointCount)}</li>`).join('') || '<li>зональных измерений нет</li>'
      return `<section class="cand">
        <h3>${esc(p.dateA)} → ${esc(p.dateB)} · ${esc(p.poseBin)} · ${esc(p.pairType)}</h3>
        <p>Статус: ${esc(classifyPair(p).label)} · max z ${esc(p.meshMaxRobustZ?.toFixed(2))} · FDR q ${esc(p.mtQValue?.toFixed(6))} · файлы: ${esc(p.photoA)}, ${esc(p.photoB)}</p>
        <p>Ограничения и альтернативы: ${esc(limitationsOf(p).join('; '))}</p>
        <p>Топ-зоны (raw rmse; zone z некалиброван):</p><ul>${zrows}</ul>
      </section>`
    }).join('\n')

    const html = `<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>DEEPUTIN — отчёт по кандидатам</title>
<style>body{font:12px/1.5 sans-serif;color:#222;max-width:900px;margin:20px auto;padding:20px}h1{font-size:18px;border-bottom:2px solid #333;padding-bottom:8px}.cand{border:1px solid #ccc;border-radius:8px;padding:10px 14px;margin:10px 0}.cand h3{font-size:13px;margin:0 0 6px}.disclaimer{background:#fff3cd;border:1px solid #ffc107;padding:10px;border-radius:6px;margin:16px 0}.meta{color:#777;font-size:10px;margin-top:24px;border-top:1px solid #ddd;padding-top:8px}</style></head><body>
<h1>DEEPUTIN — отчёт по кандидатам</h1>
<div class="disclaimer"><strong>Не является выводом о личности.</strong> Отчёт содержит измерения и кандидатов к проверке. Каждый случай требует независимой корроборации (другие ракурсы, периоды, экспертный просмотр). Кандидат — не вердикт.</div>
<p>Принято к отчёту: ${counts.accepted} · отклонено: ${counts.rejected} · требуют данных: ${counts.more} · всего FDR-значимых: ${counts.fdr}</p>
${rows || '<p>Нет принятых к отчёту кандидатов.</p>'}
<div class="meta">Сгенерировано ${esc(new Date().toISOString())} · контракт ${esc(DATA_CONTRACT_VERSION)} · пар в данных: ${pairs.length} · все метрики — измерения, не выводы.</div>
</body></html>`
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
    a.download = 'deeputin_report.html'
    a.click()
  }

  const generateCSV = () => {
    const header = 'dateA,dateB,poseBin,pairType,robustZ,FDRq,limitations,status\n'
    const rows = accepted.map(p =>
      `${esc(p.dateA)},${esc(p.dateB)},${esc(p.poseBin)},${esc(p.pairType)},${p.meshMaxRobustZ?.toFixed(2) ?? ''},${p.mtQValue?.toFixed(6) ?? ''},${esc(limitationsOf(p).join('; '))},${esc(classifyPair(p).label)}`
    ).join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob(['\ufeff' + header + rows], { type: 'text/csv;charset=utf-8' }))
    a.download = 'deeputin_summary.csv'
    a.click()
  }

  const printPDF = () => window.print()

  return (
    <div className="section-overlay" role="dialog" aria-modal="true" aria-label="Отчёт">
      <header className="sec-header"><h2>Отчёт</h2><span className="sec-scope">все ракурсы · решения синхронизированы с очередью</span>
        <div className="cw-nav"><button onClick={generateHTML}>Скачать HTML</button><button onClick={generateCSV}>CSV</button><button onClick={printPDF}>PDF</button><button onClick={onClose} aria-label="Закрыть">×</button></div>
      </header>
      <div className="sec-body rpt-body">
        <div className="sec-card rpt-stats">
          <span>FDR-значимых: {counts.fdr}</span><span>принято к отчёту: {counts.accepted}</span><span>отклонено: {counts.rejected}</span><span>нужны данные: {counts.more}</span><span>не рассмотрено: {counts.fdr - Object.keys(decisions).length}</span>
        </div>
        {accepted.length === 0 && <div className="sec-empty">Нет принятых к отчёту кандидатов — отметьте их в разделе «Проверка кандидатов».</div>}
        {accepted.map(p => (
          <div key={p.pairId} className="sec-card rpt-row">
            <strong>{p.dateA} → {p.dateB}</strong>
            <span>{p.poseBin} · {p.pairType} · z {p.meshMaxRobustZ?.toFixed(2) ?? '—'} · q {p.mtQValue?.toFixed(6) ?? '—'}</span>
            <span>{classifyPair(p).label}</span>
            <span className="rpt-lim">{limitationsOf(p).join('; ')}</span>
            <span className="rpt-zones">Топ-зоны: {topZonesOf(p.pairId).map(z => `${zoneLabel(z.zone)} ${z.rmse?.toFixed(4)}`).join(' · ') || 'нет'}</span>
          </div>
        ))}
        <div className="sec-card rpt-disclaimer"><strong>Дисклеймер.</strong> Кандидат — не вердикт. Для вывода нужны: применимость → калибровка → FDR → persistence → независимая корроборация.</div>
      </div>
    </div>
  )
}
