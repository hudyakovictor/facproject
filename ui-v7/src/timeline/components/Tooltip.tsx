import type { TimelinePhoto } from '../../types/timeline';

/**
 * Tooltip component for timeline data points.
 * Shows detailed information on hover.
 */

interface TooltipProps {
  photo: TimelinePhoto;
  x: number;
  y: number;
}

const pct = (v: number | null | undefined) => (v == null ? 'н/д' : `${Math.round(v * 100)}%`);
const deg = (v: number | null | undefined) => (v == null ? 'н/д' : `${v.toFixed(1)}°`);

function getAuthenticityStatus(value: number | null | undefined): { text: string; color: string } {
  if (value == null) return { text: 'н/д', color: 'var(--text-muted)' };
  if (value >= 0.7) return { text: 'Аутентичная', color: 'var(--color-authentic)' };
  if (value >= 0.4) return { text: 'Граничная', color: 'var(--color-warning)' };
  return { text: 'Синтетическая?', color: 'var(--color-synthetic)' };
}

function getSiliconeStatus(value: number | null | undefined): { text: string; color: string } {
  if (value == null) return { text: 'н/д', color: 'var(--text-muted)' };
  if (value <= 0.2) return { text: 'Норма', color: 'var(--color-authentic)' };
  if (value <= 0.5) return { text: 'Подозрительно', color: 'var(--color-warning)' };
  return { text: 'Силикон?', color: 'var(--color-synthetic)' };
}

export function Tooltip({ photo, x, y }: TooltipProps) {
  const authenticity = getAuthenticityStatus(photo.skinAuthenticity);
  const silicone = getSiliconeStatus(photo.siliconeProb);
  const hasFinding = photo.flags.some(f => ['coherent_jump_candidate', 'persistent_geometric_change'].includes(f));

  // Adjust position to keep tooltip in viewport
  const adjustedX = Math.min(x + 10, window.innerWidth - 280);
  const adjustedY = Math.min(y + 10, window.innerHeight - 200);

  return (
    <div
      className="timeline-tooltip"
      style={{ left: adjustedX, top: adjustedY }}
      role="tooltip"
    >
      <div className="tooltip-header">
        <span className="tooltip-date">{photo.date ?? 'дата н/д'}</span>
        <span className="tooltip-pose">{photo.bucket}</span>
      </div>

      <div className="tooltip-section">
        <div className="tooltip-row">
          <span className="tooltip-label">Качество</span>
          <span className="tooltip-value">{pct(photo.quality)}</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Выравнивание</span>
          <span className="tooltip-value">{pct(photo.alignmentQuality)}</span>
        </div>
      </div>

      <div className="tooltip-section">
        <div className="tooltip-row highlight">
          <span className="tooltip-label">Аутентичность</span>
          <span className="tooltip-value" style={{ color: authenticity.color }}>
            {authenticity.text}
          </span>
        </div>
        <div className="tooltip-row highlight">
          <span className="tooltip-label">Признак силикона</span>
          <span className="tooltip-value" style={{ color: silicone.color }}>
            {silicone.text}
          </span>
        </div>
      </div>

      <div className="tooltip-section">
        <div className="tooltip-row">
          <span className="tooltip-label">Различие формы</span>
          <span className="tooltip-value">{pct(photo.ldmShapeDifference)}</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Костная основа</span>
          <span className="tooltip-value">{pct(photo.boneScore)}</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Симметрия</span>
          <span className="tooltip-value">{pct(photo.symmetry)}</span>
        </div>
      </div>

      <div className="tooltip-section">
        <div className="tooltip-row">
          <span className="tooltip-label">Yaw / Pitch / Roll</span>
          <span className="tooltip-value">
            {deg(photo.yaw)} / {deg(photo.pitch)} / {deg(photo.roll)}
          </span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Визуальный возраст</span>
          <span className="tooltip-value">{photo.visualAge?.toFixed(0) ?? 'н/д'} лет</span>
        </div>
      </div>

      {hasFinding && (
        <div className="tooltip-finding">
          <span className="tooltip-finding-icon">⚑</span>
          <span>Требует проверки</span>
        </div>
      )}

      <div className="tooltip-hint">
        Клик — выбрать · Shift+клик — в пару
      </div>
    </div>
  );
}
