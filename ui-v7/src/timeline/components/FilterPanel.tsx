import { useTimelineStore } from '../store';
import { POSE_BINS } from '../poseBins';
import type { AnomalyKind } from '../../types/timeline';

/**
 * Filter panel component.
 * Advanced filtering options for the timeline.
 */

interface FilterPanelProps {
  onClose: () => void;
}

const ANOMALY_KIND_LABELS: Record<AnomalyKind, string> = {
  change_point: 'Точки перелома',
  persistent_change: 'Устойчивые изменения',
  return: 'Возвраты к базе',
  rapid_rate: 'Аномальный темп',
  same_day: 'Конфликты дня',
  provenance: 'Конфликты датировки',
  review: 'Требуют проверки',
};

export function FilterPanel({ onClose }: FilterPanelProps) {
  const store = useTimelineStore();

  return (
    <>
      <div className="filter-overlay" onClick={onClose} />
      <div className="filter-panel">
        <div className="filter-header">
          <span className="filter-title">ФИЛЬТРЫ</span>
          <span className="filter-note">только вид · не пересчитывает анализ</span>
          <button className="filter-close" onClick={onClose} aria-label="Закрыть">×</button>
        </div>

        <div className="filter-content">
          {/* Quality Section */}
          <div className="filter-section">
            <div className="filter-section-title">Качество</div>
            <div className="filter-row">
              <label className="filter-label">
                <span>Порог качества</span>
                <span className="filter-value">{store.qualityThreshold.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={store.qualityThreshold}
                onChange={(e) => store.setQualityThreshold(parseFloat(e.target.value))}
              />
              <div className="filter-histogram">
                {Array.from({ length: 20 }, (_, i) => {
                  const binStart = i / 20;
                  const count = store.photos.filter(p => {
                    const q = p.quality;
                    return q != null && q >= binStart && q < binStart + 0.05;
                  }).length;
                  const maxCount = Math.max(...Array.from({ length: 20 }, (_, j) => 
                    store.photos.filter(p => {
                      const q = p.quality;
                      return q != null && q >= j / 20 && q < (j + 1) / 20;
                    }).length
                  ), 1);
                  const height = Math.max(4, (count / maxCount) * 32);
                  const isKept = binStart >= store.qualityThreshold;
                  return (
                    <div
                      key={i}
                      className={`hist-bar ${isKept ? 'kept' : 'cut'}`}
                      style={{ height: `${height}px` }}
                      title={`${(binStart * 100).toFixed(0)}-${((binStart + 0.05) * 100).toFixed(0)}%: ${count}`}
                    />
                  );
                })}
              </div>
              <div className="filter-stats">
                Останется: {store.photos.filter(p => p.quality == null || p.quality >= store.qualityThreshold).length} из {store.photos.length}
              </div>
            </div>

            <div className="filter-row">
              <label className="filter-label">
                <span>Допуск угла позы</span>
                <span className="filter-value">±{store.poseAngleThreshold}°</span>
              </label>
              <input
                type="range"
                min={0}
                max={30}
                step={1}
                value={store.poseAngleThreshold}
                onChange={(e) => store.setPoseAngleThreshold(parseFloat(e.target.value))}
              />
            </div>

            <div className="filter-row">
              <label className="filter-label">
                <span>Порог активности рта</span>
                <span className="filter-value">{store.mouthThreshold.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={store.mouthThreshold}
                onChange={(e) => store.setMouthThreshold(parseFloat(e.target.value))}
              />
            </div>
          </div>

          {/* Texture Section */}
          <div className="filter-section">
            <div className="filter-section-title">Текстура кожи</div>
            <div className="filter-row">
              <label className="filter-label">
                <span>Мин. аутентичность</span>
                <span className="filter-value">{store.skinAuthenticityThreshold.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={store.skinAuthenticityThreshold}
                onChange={(e) => store.setSkinAuthenticityThreshold(parseFloat(e.target.value))}
              />
            </div>
            <div className="filter-row">
              <label className="filter-label">
                <span>Макс. признак силикона</span>
                <span className="filter-value">{store.siliconeProbThreshold.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={store.siliconeProbThreshold}
                onChange={(e) => store.setSiliconeProbThreshold(parseFloat(e.target.value))}
              />
            </div>
          </div>

          {/* LDM Section */}
          <div className="filter-section">
            <div className="filter-section-title">LDM Анализ</div>
            <div className="filter-row">
              <label className="filter-label">
                <span>Макс. различие формы</span>
                <span className="filter-value">{store.shapeDifferenceThreshold.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={store.shapeDifferenceThreshold}
                onChange={(e) => store.setShapeDifferenceThreshold(parseFloat(e.target.value))}
              />
            </div>
          </div>

          {/* Pose Section */}
          <div className="filter-section">
            <div className="filter-section-title">Ракурс</div>
            <div className="filter-pose-bins">
              <label className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={store.showMultiPose}
                  onChange={(e) => store.setShowMultiPose(e.target.checked)}
                />
                <span>Все ракурсы</span>
              </label>
              {!store.showMultiPose && (
                <div className="pose-bin-grid">
                  {POSE_BINS.map(bin => {
                    const count = store.photos.filter(p => p.bucket === bin.id).length;
                    const isActive = store.activePoseBin === bin.id;
                    return (
                      <button
                        key={bin.id}
                        className={`pose-bin-btn ${isActive ? 'active' : ''}`}
                        onClick={() => store.setActivePoseBin(isActive ? null : bin.id)}
                        disabled={count === 0}
                      >
                        <span>{bin.label}</span>
                        <span className="pose-bin-count">{count}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Anomaly Section */}
          <div className="filter-section">
            <div className="filter-section-title">Аномалии</div>
            <div className="filter-anomaly-kinds">
              {(Object.entries(ANOMALY_KIND_LABELS) as [AnomalyKind, string][]).map(([kind, label]) => (
                <label key={kind} className="filter-checkbox">
                  <input
                    type="checkbox"
                    checked={store.activeAnomalyKinds.has(kind)}
                    onChange={() => store.toggleAnomalyKind(kind)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="filter-actions">
          <button className="filter-btn primary" onClick={onClose}>
            Применить
          </button>
          <button
            className="filter-btn secondary"
            onClick={() => {
              store.setQualityThreshold(0);
              store.setPoseAngleThreshold(6);
              store.setMouthThreshold(0.35);
              store.setSkinAuthenticityThreshold(0);
              store.setSiliconeProbThreshold(1);
              store.setShapeDifferenceThreshold(1);
              store.setActivePoseBin(null);
              store.setShowMultiPose(false);
            }}
          >
            Сбросить все
          </button>
        </div>
      </div>
    </>
  );
}
