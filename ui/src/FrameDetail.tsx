import type { Frame, PhotoMetrics } from './types'
import { getPoseLabel } from './types'

interface FrameDetailProps { frame: Frame | null; metrics?: PhotoMetrics; visible: boolean; onClose: () => void }
const value = (v: number | undefined, digits = 2) => v == null ? 'нет данных' : v.toFixed(digits)

/*
 * PATCH RATIONALE — FrameDetail.tsx
 * This modal remains intentionally shallow.  The iteration is about the
 * timeline; it opens only the context needed to judge a timeline point:
 * applicability, pose and provenance.  Skin diagnostics are collapsed because
 * the backend declares texture as visualization/readiness-only, not identity
 * evidence.  Deeper inspector pages are explicitly deferred.
 */
export function FrameDetail({ frame, metrics, visible, onClose }: FrameDetailProps) {
  if (!visible || !frame) return null
  const conflicts = Boolean(frame.dateConflictSources && frame.dateConflictSources !== '[]')
  return <div className="modal-backdrop" onClick={onClose}>
    <article className="detail-modal" onClick={e => e.stopPropagation()}>
      <header><div><h2>{frame.date}</h2><p>{getPoseLabel(frame.poseBin)} · {frame.id}</p></div><button onClick={onClose}>Закрыть</button></header>
      <div className="detail-grid">
        <div className="detail-image"><img src={`/storage/stage1/${frame.id}/face_crop.jpg`} onError={e => { const t = e.target as HTMLImageElement; if (t.src.includes('face_crop')) t.src = `/storage/stage1/${frame.id}/thumb.jpg`; else t.style.display = 'none' }} alt={frame.date} /><p>Crop Stage 1. Цвет рамки не кодирует forensic-вывод.</p></div>
        <div className="detail-data">
          <section><h3>Применимость анализа</h3><Row label="Видимость" value={`${(frame.combinedVisibleFraction * 100).toFixed(1)}%`} /><Row label="Alignment quality" value={value(metrics?.alignmentQuality)} /><Row label="Skin quality" value={value(metrics?.skinQualityScore)} /><Row label="Резкость Laplacian" value={value(metrics?.laplacianVariance, 1)} />{/* V8: poseConfidence удалён — метрика квантована (5 значений), исключена каталогом */}{/* V14: статусы, ранее не отображаемые */}<Row label="UV status" value={metrics?.uvStatus ?? frame.uvStatus} /><Row label="Mask status" value={metrics?.maskStatus ?? 'нет данных'} /></section>
          <section><h3>Мимика кадра</h3><Row label="Улыбка" value={metrics?.smileDetected ? '✓ да' : metrics?.smileDetected === false ? '— нет' : 'нет данных'} /><Row label="Челюсть открыта" value={metrics?.jawOpenDetected ? '✓ да' : metrics?.jawOpenDetected === false ? '— нет' : 'нет данных'} /><Row label="Jaw open degree" value={value(metrics?.jawOpenDegree, 1)} /><Row label="Экспрессия (magnitude)" value={value(metrics?.expressionMagnitude, 2)} /><Row label="Уголки губ (corner lift)" value={value(metrics?.cornerLiftIoc, 4)} /></section>
          <section><h3>Поза</h3><Row label="Yaw / Pitch / Roll" value={`${frame.yaw.toFixed(1)}° / ${frame.pitch.toFixed(1)}° / ${frame.roll.toFixed(1)}°`} /><Row label="Pose bin" value={frame.poseBin} /></section>
          <section><h3>Датировка и источник</h3><Row label="Provenance даты" value={frame.dateProvenanceStatus} /><Row label="Provenance источника" value={frame.sourceProvenanceStatus} />{conflicts && <Row label="Конфликт дат" value={frame.dateConflictSources} />}<Row label="Файл" value={frame.sourceFilename} /></section>
          <details><summary>Диагностика кожи — не identity evidence</summary><Row label="Authenticity score" value={value(metrics?.skinAuthenticityScore)} /><Row label="Статус" value={metrics?.skinAuthenticityStatus ?? 'нет данных'} /><Row label="Покрытие маски" value={`${(frame.skinMaskCoverage * 100).toFixed(1)}%`} /><Row label="UV coverage" value={`${(frame.uvObservedCoverage * 100).toFixed(1)}%`} /></details>
        </div>
      </div>
      <footer>Кандидат требует проверки пары, калибровки, FDR, persistence и альтернативных объяснений. Этот экран не выдаёт вердикт.</footer>
    </article>
  </div>
}
function Row({ label, value }: { label: string; value: string }) { return <div className="detail-row"><span>{label}</span><strong>{value}</strong></div> }
