import type { Frame, PairConnection, PhotoMetrics, ZoneMetric } from './types'
import { zoneLabel, classifyPair } from './timeline-data-contract'

interface PairNav { pos: number; total: number; onPrev: () => void; onNext: () => void }
interface PairPopupProps { pair: PairConnection | null; visible: boolean; nav?: PairNav; onClose: () => void; frames?: Frame[]; photoMetrics?: Map<string, PhotoMetrics>; zones?: ZoneMetric[]; onOpenSection?: (s: 'atlas' | 'casework' | 'abcompare') => void }

// Gate 1: evidence state is NOT derived here — classifyPair is the single source.
// Label тоже берётся из контракта, чтобы терминология не расходилась с таймлайном.
const isCandidate = (p: PairConnection) => { const k = classifyPair(p).kind; return k === 'candidate' || k === 'persistent' }
const label = (p: PairConnection) => classifyPair(p).label

const v = (x: number | null | undefined, d = 4) => x != null ? x.toFixed(d) : '—'
const pct = (x: number | null | undefined) => x != null ? `${(x * 100).toFixed(1)}%` : '—'

export function PairPopup({ pair, visible, nav, onClose, frames, photoMetrics, zones, onOpenSection }: PairPopupProps) {
  if (!pair || !visible) return null
  const expressionMismatch = pair.smileDetectedA !== pair.smileDetectedB || pair.jawOpenDetectedA !== pair.jawOpenDetectedB
  const isCand = isCandidate(pair)
  const isFdrSig = pair.mtSignificantFdr10
  const frameA = frames?.find(f => f.id === pair.photoA)
  const frameB = frames?.find(f => f.id === pair.photoB)
  const mA = pair.photoA ? photoMetrics?.get(pair.photoA) : undefined
  const mB = pair.photoB ? photoMetrics?.get(pair.photoB) : undefined

  // V8: frameA/frameB используются для pose-контекста в A/B (раньше были мёртвым кодом — ошибка TS6133).
  // poseConfidence из блока УБРАН: метрика квантована (5 уникальных значений) и исключена каталогом треков.
  const zonesMeasured = (zones ?? []).filter(z => z.status === 'measured' && z.rmse != null)
  // V8: зоны сортируются по raw rmse, НЕ по robustZ — в текущем export zone robustZ
  // некалиброван (calibrationStatus=insufficient_calibration, медиана ~2.8e6).
  // Показ его как z-score был бы фабрикацией значимости.
  const topZones = [...zonesMeasured].sort((a, b) => (b.rmse ?? 0) - (a.rmse ?? 0)).slice(0, 5)
  const zoneGrid = ['x_low_low', 'x_low_center', 'x_low_high', 'x_center_low', 'x_center_center', 'x_center_high', 'x_high_low', 'x_high_center', 'x_high_high']
  const maxZoneRmse = Math.max(0.0001, ...zonesMeasured.map(z => z.rmse ?? 0))
  const dAlign = mA?.alignmentQuality != null && mB?.alignmentQuality != null ? mB.alignmentQuality - mA.alignmentQuality : null
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <article className="pair-popover" role="dialog" aria-modal="true" aria-label="Детали пары" onClick={e => e.stopPropagation()}>
        <header>
          <div><h3>{label(pair)}</h3><p>{pair.dateA} → {pair.dateB} · {pair.poseBin} · {pair.pairType}</p></div>
          <div className="pair-nav">
            {nav && <><button onClick={nav.onPrev} title="Предыдущая пара [">←</button><span>{nav.pos} / {nav.total}</span><button onClick={nav.onNext} title="Следующая пара ]">→</button></>}
            {/* V9: deep-links в разделы с контекстом этой пары */}
            {onOpenSection && <><button onClick={() => onOpenSection('atlas')} title="Открыть зоны этой пары в атласе">Атлас</button><button onClick={() => onOpenSection('casework')} title="Открыть в очереди проверки">Очередь</button><button onClick={() => onOpenSection('abcompare')} title="Сравнить A/B полноэкранно">Сравнить</button></>}
            <button onClick={onClose}>Закрыть</button>
          </div>
        </header>
        <div className="notice">Измерение пары — кандидат или ограничение, но не вывод о личности.</div>

        {/* A/B сравнение */}
        <section className="ab-compare">
          <div className="ab-side">
            <strong>A</strong>
            <img src={`/storage/stage1/${pair.photoA}/thumb.jpg`} alt="Кадр A" loading="lazy" onError={e => { (e.target as HTMLImageElement).style.visibility = 'hidden' }} />
            <span>{pair.dateA}</span>
            <span>align {v(mA?.alignmentQuality, 2)} · резкость {v(mA?.laplacianVariance, 0)}</span>
            {frameA && <span>yaw {frameA.yaw.toFixed(1)}° · pitch {frameA.pitch.toFixed(1)}°</span>}
            <span>улыбка {pair.smileDetectedA ? '✓' : '—'} · челюсть {pair.jawOpenDetectedA ? '✓' : '—'}</span>
          </div>
          <div className="ab-vs">→</div>
          <div className="ab-side">
            <strong>B</strong>
            <img src={`/storage/stage1/${pair.photoB}/thumb.jpg`} alt="Кадр B" loading="lazy" onError={e => { (e.target as HTMLImageElement).style.visibility = 'hidden' }} />
            <span>{pair.dateB}</span>
            <span>align {v(mB?.alignmentQuality, 2)} · резкость {v(mB?.laplacianVariance, 0)}</span>
            {frameB && <span>yaw {frameB.yaw.toFixed(1)}° · pitch {frameB.pitch.toFixed(1)}°</span>}
            <span>улыбка {pair.smileDetectedB ? '✓' : '—'} · челюсть {pair.jawOpenDetectedB ? '✓' : '—'}</span>
          </div>
        </section>
        {/* V8: дельта A→B — отвечает «чем отличается B» без возврата на таймлайн */}
        <section className="ab-delta">
          <span>Δalign {dAlign != null ? (dAlign >= 0 ? '+' : '') + dAlign.toFixed(3) : '—'}</span>
          <span>Δz max {v(pair.meshMaxRobustZ, 1)}</span>
          <span>мимика {expressionMismatch ? '⚠ различается' : 'совпадает'}</span>
        </section>
        {/* V8: зональная локализация эффекта (zone_metrics, 63 пары × 9 зон) */}
        {zones && zones.length > 0 && (
          <section className="zone-block">
            <h4>Зоны эффекта <small>raw rmse; z зон не калиброван в текущем export и не показывается</small></h4>
            <div className="zone-heat">
              {zoneGrid.map(zn => {
                const zm = zones.find(z => z.zone === zn)
                const hot = zm?.status === 'measured' && zm.rmse != null ? (zm.rmse / maxZoneRmse) : null
                // V8: подсказку собираем строкой, без вложенных template literal (парсер tsx)
                const tip = zoneLabel(zn) + ': ' + (zm?.status === 'measured' ? 'rmse ' + v(zm.rmse) + ' · точек ' + String(zm.pointCount ?? '—') : 'недостаточная видимость')
                return <div key={zn} className="zone-heat-cell" style={{ opacity: hot == null ? 0.25 : 0.25 + hot * 0.75, background: hot == null ? '#3a424e' : '#e97366' }} title={tip} />
              })}
            </div>
            {topZones.map(z => (
              <div key={z.zone} className="detail-row">
                <span>{zoneLabel(z.zone)}</span>
                <strong>rmse {v(z.rmse)} · p95 {v(z.p95)} · n={z.pointCount ?? '—'} · Δ[{v(z.signedX, 3)}, {v(z.signedY, 3)}, {v(z.signedZ, 3)}]</strong>
              </div>
            ))}
          </section>
        )}

        {/* GATE STACK */}
        <section className="gate-stack">
          <Gate label="Поза" gate="pose">
            <Row label="Pose bin" value={pair.poseBin} />
            <Row label="Analysis space" value={pair.analysisSpace} />
          </Gate>
          <Gate label="Видимость" gate={pair.meshVisibleFraction != null && pair.meshVisibleFraction < 0.5 ? 'caution' : 'ok'}>
            <Row label="Visible fraction" value={pct(pair.meshVisibleFraction)} />
            <Row label="Common vertices" value={v(pair.meshCommonVertexCount, 0)} />
            <Row label="Fit vertices" value={v(pair.meshFitVertexCount, 0)} />
            <Row label="Anchor fraction" value={v(pair.meshAnchorFraction, 3)} />
          </Gate>
          <Gate label="Выравнивание" gate={pair.meshAlignResidualAfterMedian != null && pair.meshAlignResidualAfterMedian > 0.03 ? 'caution' : 'ok'}>
            <Row label="Trimmed count" value={v(pair.meshAlignmentTrimmedCount, 0)} />
            <Row label="Residual before median" value={v(pair.meshAlignResidualBeforeMedian)} />
            <Row label="Residual after median" value={v(pair.meshAlignResidualAfterMedian)} />
            <Row label="Aligned zones" value={v(pair.meshAnatomicalZoneCount, 0)} />
          </Gate>
          <Gate label="Мимика" gate={expressionMismatch ? 'caution' : 'ok'}>
            <Row label="Улыбка A/B" value={`${pair.smileDetectedA ? '✓' : '—'} / ${pair.smileDetectedB ? '✓' : '—'}`} />
            <Row label="Челюсть A/B" value={`${pair.jawOpenDetectedA ? '✓' : '—'} / ${pair.jawOpenDetectedB ? '✓' : '—'}`} />
            <Row label="Jaw ratio A/B" value={`${v(pair.jawOpenRatioA, 3)} / ${v(pair.jawOpenRatioB, 3)}`} />
            <Row label="Corner lift A/B" value={`${v(pair.cornerLiftIocA, 3)} / ${v(pair.cornerLiftIocB, 3)}`} />
            {expressionMismatch && <p className="gate-note">Мимика различается; мягкотканные зоны требуют исключения.</p>}
          </Gate>
          <Gate label="Качество" gate="info">
            <Row label="Alignment quality A/B" value={`${v(pair.alignmentQualityA, 3)} / ${v(pair.alignmentQualityB, 3)}`} />
            <Row label="Evidence level" value={pair.meshEvidenceLevel} />
            <Row label="Date limited" value={pair.dateProvenanceLimited ? '⚠ да' : 'нет'} />
            <Row label="Near duplicate pair" value={pair.nearDuplicatePair ? '⚠ да' : 'нет'} />
          </Gate>
          <Gate label="Калибровка" gate={pair.meshCalibratedStatus === 'mesh_elevated' ? 'caution' : 'ok'}>
            <Row label="Calibration status" value={pair.meshCalibratedStatus} />
            <Row label="Elevated metrics" value={`${v(pair.meshCalibratedElevatedCount, 0)} / ${v(pair.meshCalibratedMetricCount, 0)}`} />
            <Row label="RMSE cal median/p95" value={`${v(pair.meshRmseCalMedian)} / ${v(pair.meshRmseCalP95)}`} />
            <Row label="Median cal median/p95" value={`${v(pair.meshMedianCalMedian)} / ${v(pair.meshMedianCalP95)}`} />
            {pair.meshCalibratedStatus !== 'mesh_elevated' && <p className="gate-note">Калибровка не подтверждает избыточное отклонение — z не считается сигналом.</p>}
          </Gate>
          <Gate label="FDR (множественное тестирование)" gate={isFdrSig ? 'caution' : 'ok'}>
            <Row label="p-аппроксимация" value={v(pair.mtPApprox, 6)} />
            <Row label="q-value (FDR10)" value={v(pair.mtQValue, 6)} />
            <Row label="FDR10 значимый" value={isFdrSig ? '⚠ да' : 'нет'} />
            <Row label="Diagnostic flag" value={pair.mtFdr10DiagnosticFlag || '—'} />
            <Row label="MT роль" value={pair.mtRole} />
            <Row label="Point support" value={v(pair.mtPointSupport, 0)} />
            {pair.mtRole === 'diagnostic_only' && <p className="gate-note">Роль — диагностическая: пара не участвует в reportable-выводе.</p>}
            {isFdrSig && <p className="gate-note">Проходит порог FDR10 — сигнал не объясняется множественным тестированием.</p>}
            {!isFdrSig && pair.mtQValue != null && <p className="gate-note">Не проходит FDR10; может быть шумом множественного тестирования.</p>}
          </Gate>
          <Gate label="Геометрическое изменение (raw)" gate={isCand ? 'candidate' : 'info'}>
            <Row label="RMSE" value={v(pair.meshRmse)} />
            <Row label="Median" value={v(pair.meshMedian)} />
            <Row label="P95" value={v(pair.meshP95)} />
            <Row label="Point-to-plane RMSE" value={v(pair.meshPtPlaneRmse)} />
            <Row label="Point-to-plane median" value={v(pair.meshPtPlaneMedian)} />
            <Row label="Robust z (max)" value={v(pair.meshMaxRobustZ, 2)} />
            <Row label="QC skip" value={pair.qcSkipReason || '—'} />
            {pair.status.includes('pose') && <p className="gate-note">Остаточный pose mismatch может объяснять часть residual.</p>}
            {isCand && (
              <p className="gate-note">
                <strong>Что может опровергнуть кандидатуру:</strong> (1) калибровка не подтверждает elevated
                ({pair.meshCalibratedStatus || '—'}); (2) FDR10 не значим; (3) низкая видимость/alignment;
                (4) различие мимики A/B (confounder); (5) одиночный скачок без persistence;
                (6) отсутствие независимой корроборации.
              </p>
            )}
          </Gate>
        </section>
        <footer>
          Для журналистского вывода нужны: применимость → калибровка → FDR → persistence → независимая корроборация.
          {pair.mtRole === 'diagnostic_only' && ' Эта пара — диагностическая, не reportable.'}
        </footer>
      </article>
    </div>
  )
}

function Gate({ label, gate, children }: { label: string; gate: 'ok' | 'caution' | 'candidate' | 'info' | 'pose'; children: React.ReactNode }) {
  const colors: Record<string, string> = { ok: '#72bc8f', caution: '#de9255', candidate: '#e97366', info: '#5e9fe8', pose: '#bf8eda' }
  return (
    <details open>
      <summary style={{ color: colors[gate] || '#9aa4b2', fontWeight: 700, fontSize: 12, cursor: 'pointer' }}>
        <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: colors[gate], marginRight: 6 }} />
        {label}
      </summary>
      <div style={{ padding: '4px 0 4px 14px' }}>{children}</div>
    </details>
  )
}

function Row({label,value}:{label:string;value:string}){return <div className="detail-row"><span>{label}</span><strong>{value}</strong></div>}