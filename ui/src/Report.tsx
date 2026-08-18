import { useMemo } from 'react'
import type { PairConnection, TimelineAnnotation, ZoneMetric } from './types'
import { classifyPair, zoneLabel, DATA_CONTRACT_VERSION } from './timeline-data-contract'
import { SectionShell, MiniBars } from './SectionShell'
import type { SectionKey } from './section-meta'
import type { DecisionEntry } from './App'

/* V12: ОТЧЁТ 2.0.
 * Что нового против V9:
 * 1. ЖИВОЙ ПРЕДПРОСМОТР: сводка-карточки, мини-гистограммы (принятые по
 *    годам и по z), список принятых с полным контекстом — всё в UI,
 *    а не только в экспортируемом файле.
 * 2. Заметки журналиста включены в отчёт (из App).
 * 3. Экспорт JSON: решения + заметки + метаданные (в V9 был только HTML/CSV).
 * 4. escapeHtml на всех интерполируемых значениях (injection-защита).
 * 5. «Не рассмотрено» = Math.max(0, …) (фикс отрицательного счётчика). */
const esc = (s: unknown) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export function Report({ pairs, zones, decisions, annotations, onClose, onNavigate }: {
  pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>
  decisions: Record<string, DecisionEntry>; annotations?: TimelineAnnotation[]
  onClose: () => void; onNavigate?: (k: SectionKey) => void
}) {
  const accepted = useMemo(() =>
    pairs.filter(p => decisions[p.pairId]?.decision === 'accepted').sort((a, b) => (b.meshMaxRobustZ ?? 0) - (a.meshMaxRobustZ ?? 0)),
    [pairs, decisions])
  const counts = useMemo(() => ({
    fdr: pairs.filter(p => p.mtSignificantFdr10).length,
    accepted: accepted.length,
    rejected: Object.values(decisions).filter(d => d.decision === 'rejected').length,
    more: Object.values(decisions).filter(d => d.decision === 'more_data').length,
  }), [pairs, decisions, accepted.length])

  const byYear = useMemo(() => {
    const m = new Map<number, number>()
    for (const p of accepted) {
      const y = Number(p.dateB.slice(0, 4))
      m.set(y, (m.get(y) ?? 0) + 1)
    }
    return [...m.keys()].sort((a, b) => a - b).map(y => ({ label: String(y).slice(2), value: m.get(y) ?? 0 }))
  }, [accepted])
  const zBars = useMemo(() => {
    const buckets = [0, 0, 0, 0]
    for (const p of accepted) {
      const z = p.meshMaxRobustZ ?? 0
      if (z < 5) buckets[0]++
      else if (z < 10) buckets[1]++
      else if (z < 20) buckets[2]++
      else buckets[3]++
    }
    return [{ label: '<5', value: buckets[0] }, { label: '5–10', value: buckets[1] }, { label: '10–20', value: buckets[2] }, { label: '>20', value: buckets[3] }]
  }, [accepted])

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
    const anno = (annotations ?? []).map(a => `<li>${esc(a.date)}: ${esc(a.text)}</li>`).join('')
    const years = byYear.map(b => `<span class="yr">${b.label}:${b.value}</span>`).join(' ')
    const html = `<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>DEEPUTIN — отчёт по кандидатам</title>
<style>body{font:12px/1.5 sans-serif;color:#222;max-width:900px;margin:20px auto;padding:20px}h1{font-size:18px;border-bottom:2px solid #333;padding-bottom:8px}.cand{border:1px solid #ccc;border-radius:8px;padding:10px 14px;margin:10px 0}.cand h3{font-size:13px;margin:0 0 6px}.disclaimer{background:#fff3cd;border:1px solid #ffc107;padding:10px;border-radius:6px;margin:16px 0}.meta{color:#777;font-size:10px;margin-top:24px;border-top:1px solid #ddd;padding-top:8px}.yr{display:inline-block;background:#eee;border-radius:4px;padding:2px 8px;margin:2px}</style></head><body>
<h1>DEEPUTIN — отчёт по кандидатам</h1>
<div class="disclaimer"><strong>Не является выводом о личности.</strong> Отчёт содержит измерения и кандидатов к проверке. Каждый случай требует независимой корроборации (другие ракурсы, периоды, экспертный просмотр). Кандидат — не вердикт.</div>
<p>Принято к отчёту: ${counts.accepted} · отклонено: ${counts.rejected} · требуют данных: ${counts.more} · всего FDR-значимых: ${counts.fdr} · не рассмотрено: ${Math.max(0, counts.fdr - Object.keys(decisions).length)}</p>
<p>Распределение по годам: ${years || '—'}</p>
${annotations && annotations.length > 0 ? `<h2>Заметки журналиста</h2><ul>${anno}</ul>` : ''}
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

  const generateJSON = () => {
    const payload = {
      schema: 'deeputin-report-v1',
      exportedAt: new Date().toISOString(),
      contractVersion: DATA_CONTRACT_VERSION,
      counts,
      annotations: annotations ?? [],
      decisions,
      accepted: accepted.map(p => ({
        pairId: p.pairId, dateA: p.dateA, dateB: p.dateB, poseBin: p.poseBin, pairType: p.pairType,
        robustZ: p.meshMaxRobustZ, fdrQ: p.mtQValue, fdrSignificant: p.mtSignificantFdr10,
        status: classifyPair(p).label, limitations: limitationsOf(p),
        topZones: topZonesOf(p.pairId).map(z => ({ zone: zoneLabel(z.zone), rmse: z.rmse, p95: z.p95, n: z.pointCount })),
      })),
    }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }))
    a.download = 'deeputin_report.json'
    a.click()
  }

  const printPDF = () => window.print()

  return (
    <SectionShell title="Отчёт" current="report" onNavigate={onNavigate} onClose={onClose}
      scope={`${counts.fdr} FDR-значимых · ${counts.accepted} принято к отчёту · решения синхронизированы с очередью`}
      help={<>Отчёт собирает <b>принятые к отчёту</b> кандидаты (решения из «Проверки кандидатов») + заметки. Экспорт: HTML с дисклеймером, CSV-таблица, JSON (машинночитаемый, с решениями и заметками), печать PDF. Кандидат — не вердикт: каждый пункт содержит ограничения и альтернативные объяснения.</>}
      footer={<div className="rpt-actions">
        <button onClick={generateHTML}>Скачать HTML</button>
        <button onClick={generateCSV}>CSV</button>
        <button onClick={generateJSON}>JSON</button>
        <button onClick={printPDF}>PDF (печать)</button>
      </div>}>
      <div className="rpt2">
        <div className="rpt2-cards">
          <div className="rpt2-card"><span className="k">FDR-значимых</span><span className="v">{counts.fdr}</span></div>
          <div className="rpt2-card ok"><span className="k">К отчёту</span><span className="v">{counts.accepted}</span></div>
          <div className="rpt2-card no"><span className="k">Артефакт</span><span className="v">{counts.rejected}</span></div>
          <div className="rpt2-card more"><span className="k">Нужны данные</span><span className="v">{counts.more}</span></div>
          <div className="rpt2-card"><span className="k">Не рассмотрено</span><span className="v">{Math.max(0, counts.fdr - Object.keys(decisions).length)}</span></div>
        </div>

        <div className="rpt2-cols">
          <div className="sec-card">
            <h3>Принятые по годам</h3>
            {byYear.length === 0 ? <p className="sec-note">Нет принятых.</p> : <MiniBars data={byYear} />}
          </div>
          <div className="sec-card">
            <h3>Принятые по robust-z</h3>
            {zBars.every(b => b.value === 0) ? <p className="sec-note">Нет принятых.</p> : <MiniBars data={zBars} />}
          </div>
          <div className="sec-card">
            <h3>Заметки журналиста ({annotations?.length ?? 0})</h3>
            {(annotations ?? []).length === 0 && <p className="sec-note">Заметок нет — добавьте через 📌 в панели пары.</p>}
            {(annotations ?? []).map(a => <div key={a.id} className="rpt2-anno"><span>{a.date}</span><span>{a.text}</span></div>)}
          </div>
        </div>

        <div className="sec-card">
          <h3>Принятые к отчёту ({accepted.length})</h3>
          {accepted.length === 0 && <p className="sec-note">Нет принятых к отчёту кандидатов — отметьте их в разделе «Проверка кандидатов» (клавиша 1).</p>}
          {accepted.map(p => (
            <div key={p.pairId} className="rpt2-row">
              <div className="rpt2-row-h">
                <strong>{p.dateA} → {p.dateB}</strong>
                <span>{p.poseBin} · {p.pairType}</span>
                <span className="rpt2-z">z {p.meshMaxRobustZ?.toFixed(2) ?? '—'}</span>
                <span className="rpt2-q">q {p.mtQValue?.toFixed(6) ?? '—'}</span>
                {p.mtSignificantFdr10 && <span className="rpt2-fdr">FDR10</span>}
              </div>
              <div className="rpt2-row-body">
                <span className="rpt2-status">{classifyPair(p).label}</span>
                <span className="rpt2-lim">Ограничения: {limitationsOf(p).join('; ')}</span>
                <span className="rpt2-zones">Топ-зоны: {topZonesOf(p.pairId).map(z => `${zoneLabel(z.zone)} ${z.rmse?.toFixed(4)}`).join(' · ') || 'нет'}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="sec-card rpt2-disclaimer"><strong>Дисклеймер.</strong> Кандидат — не вердикт. Для вывода нужны: применимость → калибровка → FDR → persistence → независимая корроборация. Отчёт — черновик для журналистской проверки, не заключение.</div>
      </div>
    </SectionShell>
  )
}
