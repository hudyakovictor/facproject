import type { TimelinePhoto } from '../../types/timeline';

/**
 * Photo detail card component.
 * Shows detailed information about selected photo.
 */

interface PhotoDetailCardProps {
  photo: TimelinePhoto;
  onClose: () => void;
  onAssignPair: () => void;
  onClearPair: () => void;
  pairAId: string | null;
  pairBId: string | null;
}

const pct = (v: number | null | undefined) => (v == null ? 'н/д' : `${Math.round(v * 100)}%`);
const deg = (v: number | null | undefined) => (v == null ? 'н/д' : `${v.toFixed(1)}°`);
const num = (v: number | null | undefined) => (v == null ? 'н/д' : v.toFixed(2));

function getAuthenticityColor(value: number | null | undefined): string {
  if (value == null) return 'var(--text-muted)';
  if (value >= 0.7) return 'var(--color-authentic)';
  if (value >= 0.4) return 'var(--color-warning)';
  return 'var(--color-synthetic)';
}

function getSiliconeColor(value: number | null | undefined): string {
  if (value == null) return 'var(--text-muted)';
  if (value <= 0.2) return 'var(--color-authentic)';
  if (value <= 0.5) return 'var(--color-warning)';
  return 'var(--color-synthetic)';
}

export function PhotoDetailCard({ photo, onClose, onAssignPair, onClearPair, pairAId, pairBId }: PhotoDetailCardProps) {
  const isPairA = photo.id === pairAId;
  const isPairB = photo.id === pairBId;
  const hasFinding = photo.flags.some(f => ['coherent_jump_candidate', 'persistent_geometric_change'].includes(f));

  return (
    <>
      <div className="detail-overlay" onClick={onClose} />
      <div className="detail-card">
        <div className="detail-header">
          <div className="detail-title">
            <span className="detail-title-icon">◆</span>
            <span>КАРТОЧКА КАДРА</span>
          </div>
          <button className="detail-close" onClick={onClose} aria-label="Закрыть">×</button>
        </div>

        <div className="detail-content">
          <div className="detail-main">
            <div className="detail-photo-section">
              <div className="detail-photo-placeholder">
                <span className="detail-photo-id">{photo.id.slice(0, 20)}...</span>
              </div>
              <div className="detail-date">
                <span className="detail-date-label">Дата</span>
                <span className="detail-date-value">{photo.date ?? 'н/д'}</span>
              </div>
              <div className="detail-pose">
                <span className="detail-pose-label">Ракурс</span>
                <span className="detail-pose-value">{photo.bucket}</span>
              </div>
            </div>

            <div className="detail-metrics">
              <div className="detail-section-title">Качество и текстура</div>
              <div className="detail-metric-grid">
                <div className="detail-metric">
                  <span className="detail-metric-label">Качество кадра</span>
                  <span className="detail-metric-value">{pct(photo.quality)}</span>
                  <div className="detail-metric-bar">
                    <div className="detail-metric-fill" style={{ width: pct(photo.quality), background: 'var(--metric-quality)' }} />
                  </div>
                </div>
                <div className="detail-metric">
                  <span className="detail-metric-label">Выравнивание</span>
                  <span className="detail-metric-value">{pct(photo.alignmentQuality)}</span>
                  <div className="detail-metric-bar">
                    <div className="detail-metric-fill" style={{ width: pct(photo.alignmentQuality), background: 'var(--metric-quality)' }} />
                  </div>
                </div>
                <div className="detail-metric highlight">
                  <span className="detail-metric-label">Аутентичность кожи</span>
                  <span className="detail-metric-value" style={{ color: getAuthenticityColor(photo.skinAuthenticity) }}>
                    {pct(photo.skinAuthenticity)}
                  </span>
                  <div className="detail-metric-bar">
                    <div className="detail-metric-fill" style={{ width: pct(photo.skinAuthenticity), background: getAuthenticityColor(photo.skinAuthenticity) }} />
                  </div>
                </div>
                <div className="detail-metric highlight">
                  <span className="detail-metric-label">Признак силикона</span>
                  <span className="detail-metric-value" style={{ color: getSiliconeColor(photo.siliconeProb) }}>
                    {pct(photo.siliconeProb)}
                  </span>
                  <div className="detail-metric-bar">
                    <div className="detail-metric-fill" style={{ width: pct(photo.siliconeProb), background: getSiliconeColor(photo.siliconeProb) }} />
                  </div>
                </div>
              </div>

              <div className="detail-section-title">Геометрия</div>
              <div className="detail-metric-grid">
                <div className="detail-metric">
                  <span className="detail-metric-label">Костная основа</span>
                  <span className="detail-metric-value">{pct(photo.boneScore)}</span>
                  <div className="detail-metric-bar">
                    <div className="detail-metric-fill" style={{ width: pct(photo.boneScore), background: 'var(--metric-geometry)' }} />
                  </div>
                </div>
                <div className="detail-metric">
                  <span className="detail-metric-label">Симметрия</span>
                  <span className="detail-metric-value">{pct(photo.symmetry)}</span>
                  <div className="detail-metric-bar">
                    <div className="detail-metric-fill" style={{ width: pct(photo.symmetry), background: 'var(--metric-geometry)' }} />
                  </div>
                </div>
                <div className="detail-metric">
                  <span className="detail-metric-label">Глазница</span>
                  <span className="detail-metric-value">{num(photo.orbit)}</span>
                </div>
                <div className="detail-metric">
                  <span className="detail-metric-label">Подбородок</span>
                  <span className="detail-metric-value">{num(photo.chin)}</span>
                </div>
              </div>

              <div className="detail-section-title">LDM Анализ</div>
              <div className="detail-metric-grid">
                <div className="detail-metric highlight">
                  <span className="detail-metric-label">Различие формы</span>
                  <span className="detail-metric-value" style={{ color: photo.ldmShapeDifference != null && photo.ldmShapeDifference > 0.5 ? 'var(--color-synthetic)' : 'var(--text-primary)' }}>
                    {pct(photo.ldmShapeDifference)}
                  </span>
                  <div className="detail-metric-bar">
                    <div className="detail-metric-fill" style={{ width: pct(photo.ldmShapeDifference), background: 'var(--metric-anomaly)' }} />
                  </div>
                </div>
                <div className="detail-metric">
                  <span className="detail-metric-label">LDM106 различие</span>
                  <span className="detail-metric-value">{pct(photo.ldm106Difference)}</span>
                </div>
                <div className="detail-metric">
                  <span className="detail-metric-label">LDM134 различие</span>
                  <span className="detail-metric-value">{pct(photo.ldm134Difference)}</span>
                </div>
                <div className="detail-metric">
                  <span className="detail-metric-label">Видимые точки</span>
                  <span className="detail-metric-value">{photo.visibleLdm106 ?? 'н/д'} / {photo.visibleLdm134 ?? 'н/д'}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="detail-sidebar">
            <div className="detail-section-title">Поза</div>
            <div className="detail-pose-grid">
              <div className="detail-pose-item">
                <span>Yaw</span>
                <strong>{deg(photo.yaw)}</strong>
              </div>
              <div className="detail-pose-item">
                <span>Pitch</span>
                <strong>{deg(photo.pitch)}</strong>
              </div>
              <div className="detail-pose-item">
                <span>Roll</span>
                <strong>{deg(photo.roll)}</strong>
              </div>
              <div className="detail-pose-item">
                <span>Residual</span>
                <strong>{deg(photo.residualYaw)}</strong>
              </div>
            </div>

            <div className="detail-section-title">Хронология</div>
            <div className="detail-chronology">
              <div className="detail-chronology-item">
                <span>Визуальный возраст</span>
                <strong>{photo.visualAge?.toFixed(0) ?? 'н/д'} лет</strong>
              </div>
              <div className="detail-chronology-item">
                <span>Календарный возраст</span>
                <strong>{photo.calendarAge?.toFixed(0) ?? 'н/д'} лет</strong>
              </div>
              <div className="detail-chronology-item">
                <span>Выражение</span>
                <strong>{photo.expressionMagnitude?.toFixed(1) ?? 'н/д'}</strong>
              </div>
              <div className="detail-chronology-item">
                <span>Открытие рта</span>
                <strong>{deg(photo.jawOpenDegree)}</strong>
              </div>
            </div>

            <div className="detail-section-title">Статус</div>
            <div className="detail-status">
              <div className="detail-status-item">
                <span>Измерение</span>
                <span className={`status-badge ${photo.measurementStatus === 'measured' ? 'ok' : 'limited'}`}>
                  {photo.measurementStatus ?? 'н/д'}
                </span>
              </div>
              <div className="detail-status-item">
                <span>Датировка</span>
                <span className={`status-badge ${photo.dateProvenanceStatus === 'filename_only' ? 'ok' : 'warning'}`}>
                  {photo.dateProvenanceStatus ?? 'н/д'}
                </span>
              </div>
              {hasFinding && (
                <div className="detail-status-item">
                  <span>Находка</span>
                  <span className="status-badge finding">⚑ требует проверки</span>
                </div>
              )}
            </div>

            {photo.flags.length > 0 && (
              <>
                <div className="detail-section-title">Флаги</div>
                <div className="detail-flags">
                  {photo.flags.map(flag => (
                    <span key={flag} className="detail-flag">{flag}</span>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        <div className="detail-actions">
          <button
            className={`detail-btn ${isPairA ? 'active-a' : isPairB ? 'active-b' : ''}`}
            onClick={onAssignPair}
          >
            {isPairA ? '✓ A назначен' : isPairB ? '✓ B назначен' : 'Назначить A/B'}
          </button>
          <button className="detail-btn secondary" onClick={onClearPair} disabled={!pairAId && !pairBId}>
            Сбросить пару
          </button>
        </div>
      </div>
    </>
  );
}
