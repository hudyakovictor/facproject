/**
 * Compact timeline menu bar.
 */

interface TimelineToolbarProps {
  qualityThreshold: number;
  findingsMode: boolean;
  onQualityChange: (value: number) => void;
  onFindingsToggle: () => void;
  onToggleFilters: () => void;
  onExportCSV: () => void;
  onToggle3D: () => void;
  show3D: boolean;
  onShowPresets: () => void;
}

export function TimelineToolbar({
  qualityThreshold,
  findingsMode,
  onQualityChange,
  onFindingsToggle,
  onToggleFilters,
  onExportCSV,
  onToggle3D,
  show3D,
  onShowPresets,
}: TimelineToolbarProps) {
  return (
    <div className="timeline-toolbar">
      <div className="toolbar-section">
        <button
          className={`toolbar-btn ${findingsMode ? 'active' : ''}`}
          onClick={onFindingsToggle}
          title="Показать только находки"
        >
          ⚑ Находки
        </button>
      </div>

      <div className="toolbar-section">
        <button className="toolbar-btn" onClick={onShowPresets} title="Пресеты фильтров">
          ⊡ Пресеты
        </button>
        <button className="toolbar-btn" onClick={onToggleFilters} title="Фильтры (F)">
          ⊞ Фильтры
        </button>
        <button
          className={`toolbar-btn ${show3D ? 'active' : ''}`}
          onClick={onToggle3D}
          title="3D модель"
        >
          ◈ 3D
        </button>
        <button className="toolbar-btn" onClick={onExportCSV} title="Экспорт CSV">
          ↓ CSV
        </button>
      </div>

      <div className="toolbar-section">
        <label className="toolbar-slider">
          <span>Качество</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={qualityThreshold}
            onChange={(e) => onQualityChange(parseFloat(e.target.value))}
          />
          <span className="toolbar-slider-value">{qualityThreshold.toFixed(2)}</span>
        </label>
      </div>

    </div>
  );
}
