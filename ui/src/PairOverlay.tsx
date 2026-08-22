import type { SyntheticEvent } from 'react'
import type { Frame, PairConnection, PhotoMetrics, ZoneMetric } from './types'
import { zoneLabel, classifyPair } from './timeline-data-contract'

interface PairNav { pos: number; total: number; onPrev: () => void; onNext: () => void }
interface PairPopupProps { pair: PairConnection | null; visible: boolean; nav?: PairNav; onClose: () => void; frames?: Frame[]; photoMetrics?: Map<string, PhotoMetrics>; zones?: ZoneMetric[]; onOpenSection?: (s: 'atlas' | 'casework' | 'abcompare' | 'morph') => void; onAnnotate?: (date: string, text: string) => void }

// Gate 1: evidence state is NOT derived here — classifyPair is the single source.
const isCandidate = (p: PairConnection) => { const k = classifyPair(p).kind; return k === 'candidate' || k === 'persistent' }
const label = (p: PairConnection) => classifyPair(p).label

const v = (x: number | null | undefined, d = 4) => x != null ? x.toFixed(d) : '—'
const pct = (x: number | null | undefined) => x != null ? `${(x * 100).toFixed(1)}%` : '—'
const zColor = (z: number | null | undefined) => {
  if (z == null) return '#5a6573'
  if (z > 20) return '#ef4444'
  if (z > 10) return '#f97316'
  if (z > 5) return '#eab308'
  if (z > 3) return '#38bdf8'
  return '#22c55e'
}
const imgErr = (e: SyntheticEvent<HTMLImageElement>) => {
  // V11: каскад fallback — face_crop → thumb → скрыть (раньше вторая ошибка оставляла битую иконку)
  const t = e.currentTarget
  if (t.src.includes('face_crop')) t.src = t.src.replace('face_crop', 'thumb')
  else t.style.display = 'none'
}

/* V11: ПОПАП ПАРЫ — ландшафтный (шире, чем выше, в пропорциях монитора).
 * Вёрстка полностью изменена: фото A|Δ|B в ряд, карточки метрик, зоны + гейты.
 * Таймлайн под попапом остаётся живым (не блокируется затемнением). */
export function PairPopup({ pair, visible, nav, onClose, frames, photoMetrics, zones, onOpenSection, onAnnotate }: PairPopupProps) {
  if (!pair || !visible) return null
  const expressionMismatch = pair.smileDetectedA !== pair.smileDetectedB || pair.jawOpenDetectedA !== pair.jawOpenDetectedB
  const isCand = isCandidate(pair)
  const isFdrSig = pair.mtSignificantFdr10
  const frameA = frames?.find(f => f.id === pair.photoA)
  const frameB = frames?.find(f => f.id === pair.photoB)
  const mA = pair.photoA ? photoMetrics?.get(pair.photoA) : undefined
  const mB = pair.photoB ? photoMetrics?.get(pair.photoB) : undefined

  const zonesMeasured = (zones ?? []).filter(z => z.status === 'measured' && z.rmse != null)
  const topZones = [...zonesMeasured].sort((a, b) => (b.rmse ?? 0) - (a.rmse ?? 0)).slice(0, 5)
  const zoneGrid = ['x_low_low', 'x_low_center', 'x_low_high', 'x_center_low', 'x_center_center', 'x_center_high', 'x_high_low', 'x_high_center', 'x_high_high']
  const maxZoneRmse = Math.max(0.0001, ...zonesMeasured.map(z => z.rmse ?? 0))
  const dAlign = mA?.alignmentQuality != null && mB?.alignmentQuality != null ? mB.alignmentQuality - mA.alignmentQuality : null

  const annotate = () => {
    const t = window.prompt(`Заметка к дате ${pair.dateB} (появится на линейке):`)
    if (t?.trim()) onAnnotate?.(pair.dateB, t.trim())
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <article className="pair-popover landscape" role="dialog" aria-modal="true" aria-label="Детали пары" onClick={e => e.stopPropagation()}>
        <header>
          <div>
            <h3>{label(pair)}</h3>
            <p>{pair.dateA} → {pair.dateB} · {pair.poseBin} · {pair.pairType} · evidence {pair.meshEvidenceLevel}</p>
          </div>
          <div className="pair-nav">
            {nav && <><button onClick={nav.onPrev} title="Предыдущая пара [">←</button><span>{nav.pos} / {nav.total}</span><button onClick={nav.onNext} title="Следующая пара ]">→</button></>}
            {onOpenSection && <><button onClick={() => onOpenSection('atlas')} title="Открыть зоны этой пары в атласе">Атлас</button><button onClick={() => onOpenSection('casework')} title="Открыть в очереди проверки">Очередь</button><button onClick={() => onOpenSection('morph')} title="Морфинг A→B: 3D/текстура/тепловая карта">Морфинг</button><button onClick={() => onOpenSection('abcompare')} title="Сравнить A/B полноэкранно">Сравнить</button></>}
            {onAnnotate && <button onClick={annotate} title="Добавить заметку на линейке (дата B)">📌</button>}
            <button onClick={onClose}>Закрыть</button>
          </div>
        </header>

        <div className="pp-body">
          {/* Фото A | Δ | B — горизонтальный ряд (главный визуальный контраст) */}
          <section className="pp-photos">
            <PhotoSide tag="A" date={pair.dateA} frame={frameA} m={mA} photoId={pair.photoA} />
            <div className="pp-delta">
              <span className="pp-dk">Δ max z</span>
              <span className="pp-dv" style={{ color: zColor(pair.meshMaxRobustZ) }}>{v(pair.meshMaxRobustZ, 1)}</span>
              <span className="pp-dk">Δ alignment</span>
              <span className="pp-ds">{dAlign != null ? (dAlign >= 0 ? '+' : '') + dAlign.toFixed(3) : '—'}</span>
              <span className="pp-dk">мимика A/B</span>
              <span className="pp-ds">{expressionMismatch ? '⚠ различается' : 'совпадает'}</span>
              {isFdrSig && <span className="pp-fdr">FDR10</span>}
              {pair.mtRole === 'diagnostic_only' && <span className="pp-dk">диагностическая</span>}
            </div>
            <PhotoSide tag="B" date={pair.dateB} frame={frameB} m={mB} photoId={pair.photoB} />
          </section>

          {/* Основной вывод — только показатели, которые влияют на решение */}
          <section className="pp-cards" aria-label="Ключевые метрики пары">
            <Card k="Отклонение геометрии" value={v(pair.meshMaxRobustZ, 1)} color={zColor(pair.meshMaxRobustZ)} s="max robust z" />
            <Card k="Статус FDR10" value={isFdrSig ? 'значимо' : 'не значимо'} s={pair.mtQValue == null ? 'q-value —' : `q ${pair.mtQValue.toFixed(3)}`} />
            <Card k="Видимость лица" value={pct(pair.meshVisibleFraction)} s="общая поддержка пары" />
            <Card k="Выравнивание" value={`${v(mA?.alignmentQuality, 2)} → ${v(mB?.alignmentQuality, 2)}`} s={dAlign == null ? 'нет Δ' : `Δ ${dAlign >= 0 ? '+' : ''}${dAlign.toFixed(3)}`} />
            <Card k="Качество кожи A / B" value={`${v(mA?.skinQualityScore, 2)} / ${v(mB?.skinQualityScore, 2)}`} />
            <Card k="Аутентичность кожи A / B" value={`${v(mA?.skinAuthenticityScore, 2)} / ${v(mB?.skinAuthenticityScore, 2)}`} />
            <Card k="Открытие рта A / B" value={`${mA?.jawOpenDegree == null ? '—' : `${mA.jawOpenDegree.toFixed(1)}°`} / ${mB?.jawOpenDegree == null ? '—' : `${mB.jawOpenDegree.toFixed(1)}°`}`} s={expressionMismatch ? 'мимика различается' : 'мимика сопоставима'} />
          </section>

          {/* Зоны + гейты (две колонки, нижний ярус) */}
          <section className="pp-bottom">
            <div className="pp-zones">
              <h4>Зоны эффекта <small>raw rmse · z зон некалиброван</small></h4>
              <div className="pp-zone-heat">
                {zoneGrid.map(zn => {
                  const zm = zones?.find(z => z.zone === zn)
                  const hot = zm?.status === 'measured' && zm.rmse != null ? zm.rmse / maxZoneRmse : null
                  const tip = zoneLabel(zn) + ': ' + (zm?.status === 'measured' ? 'rmse ' + v(zm.rmse) + ' · точек ' + String(zm.pointCount ?? '—') : 'недостаточная видимость')
                  return <div key={zn} className="pp-zone-cell" title={tip}
                    style={{ background: hot == null ? '#3a424e' : `rgba(233,115,102,${0.15 + hot * 0.85})`, opacity: hot == null ? 0.35 : 1 }}>
                    {zn === 'x_center_center' ? 'центр' : ''}
                  </div>
                })}
              </div>
              <h4>Топ-зоны по rmse</h4>
              <div className="pp-zone-list">
                {topZones.length === 0 && <span className="pp-ds">зональных измерений нет</span>}
                {topZones.map(z => (
                  <div key={z.zone} className="pp-zone-row">
                    <span>{zoneLabel(z.zone)}</span>
                    <b>rmse {v(z.rmse)} · p95 {v(z.p95)} · n={z.pointCount ?? '—'}</b>
                  </div>
                ))}
              </div>
            </div>

            <div className="pp-gates">
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
                <Row label="Источник" value={pair.expressionSource || '—'} />
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
                <Row label="P95 cal median/p95" value={`${v(pair.meshP95CalMedian)} / ${v(pair.meshP95CalP95)}`} />
                {pair.meshCalibratedStatus !== 'mesh_elevated' && <p className="gate-note">Калибровка не подтверждает избыточное отклонение — z не считается сигналом.</p>}
              </Gate>
              <Gate label="FDR (множественное тестирование)" gate={isFdrSig ? 'caution' : 'ok'}>
                <Row label="p-аппроксимация" value={v(pair.mtPApprox, 6)} />
                <Row label="q-value (FDR10)" value={v(pair.mtQValue, 6)} />
                <Row label="FDR10 значимый" value={isFdrSig ? '⚠ да' : 'нет'} />
                <Row label="Diagnostic flag" value={pair.mtFdr10DiagnosticFlag || '—'} />
                <Row label="MT роль" value={pair.mtRole} />
                <Row label="Детализация роли" value={pair.mtRoleDetail || '—'} />
                <Row label="Point support" value={v(pair.mtPointSupport, 0)} />
                {pair.mtRoleDetail?.includes('unreliable') && <p className="gate-note">⚠ p95-статистика ненадёжна при &lt;20 точках — использован single-z fallback.</p>}
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
                <Row label="Point-to-plane P95" value={v(pair.meshPtPlaneP95)} />
                <Row label="Robust z (max)" value={v(pair.meshMaxRobustZ, 2)} />
                <Row label="QC skip" value={pair.qcSkipReason || '—'} />
                {/* V14: пер-метричные статусы — семантика каждого z */}
                <Row label="Статусы 6 метрик" value={[pair.meshRmseStatus, pair.meshMedianStatus, pair.meshP95Status, pair.meshPtPlaneRmseStatus, pair.meshPtPlaneMedianStatus, pair.meshPtPlaneP95Status].map(x => x || '—').join(' · ')} />
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
            </div>
          </section>
        </div>

        <footer>
          Для журналистского вывода нужны: применимость → калибровка → FDR → persistence → независимая корроборация.
          {pair.mtRole === 'diagnostic_only' && ' Эта пара — диагностическая, не reportable.'}
          {isCand && ' Кандидат — не вердикт.'}
        </footer>
      </article>
    </div>
  )
}

function PhotoSide({ tag, date, frame, m, photoId }: {
  tag: string; date: string; frame?: Frame; m?: PhotoMetrics; photoId: string
}) {
  return (
    <div className="pp-side">
      <div className="pp-side-h"><span className="pp-tag">{tag}</span><strong>{date}</strong></div>
      <img src={`/storage/stage1/${photoId}/face_crop.jpg`} alt={`Кадр ${tag} (${date})`} loading="lazy" onError={imgErr} />
      <div className="pp-meta">
        <span>видимость <b>{frame ? pct(frame.combinedVisibleFraction) : '—'}</b></span>
        <span>выравнивание <b>{v(m?.alignmentQuality, 2)}</b></span>
        <span>кожа <b>{v(m?.skinQualityScore, 2)}</b></span>
        <span>аутентичность <b>{v(m?.skinAuthenticityScore, 2)}</b></span>
        <span>рот <b>{m?.jawOpenDegree != null ? `${m.jawOpenDegree.toFixed(1)}°` : '—'}</b></span>
      </div>
    </div>
  )
}

function Card({ k, value, s, color }: { k: string; value: string; s?: string; color?: string }) {
  return <div className="pp-card"><span className="k">{k}</span><span className="v" style={color ? { color } : undefined}>{value}</span>{s && <span className="s">{s}</span>}</div>
}

function Gate({ label, gate, children }: { label: string; gate: 'ok' | 'caution' | 'candidate' | 'info' | 'pose'; children: React.ReactNode }) {
  const colors: Record<string, string> = { ok: '#72bc8f', caution: '#de9255', candidate: '#e97366', info: '#5e9fe8', pose: '#bf8eda' }
  return (
    <details>
      <summary style={{ color: colors[gate] || '#9aa4b2', fontWeight: 700, fontSize: 11, cursor: 'pointer' }}>
        <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: colors[gate], marginRight: 6 }} />
        {label}
      </summary>
      <div style={{ padding: '4px 0 2px 14px' }}>{children}</div>
    </details>
  )
}

function Row({ label, value }: { label: string; value: string }) { return <div className="detail-row"><span>{label}</span><strong>{value}</strong></div> }
