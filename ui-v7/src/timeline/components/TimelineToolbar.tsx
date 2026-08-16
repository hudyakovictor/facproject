import type { Viewport, TimeBounds } from '../../types/timeline';
import { zoomLevel } from '../viewport';

/**
 * Timeline toolbar component.
 * Contains controls for zoom, filters, and view options.
 */

interface TimelineToolbarProps {
  viewport: Viewport;
  bounds: TimeBounds;
  photoCount: number;
  filteredCount: number;
  qualityThreshold: number;
  findingsMode: boolean;
  searchQuery: string;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitView: () => void;
  onQualityChange: (value: number) => void;
  onFindingsToggle: () => void;
  onSearchChange: (value: string) => void;
  onToggleFilters: () => void;
  onExportCSV: () => void;
  onToggle3D: () => void;
  show3D: boolean;
  onShowPresets: () => void;
}

export function TimelineToolbar({
  viewport,
  bounds,
  photoCount,
  filteredCount,
  qualityThreshold,
  findingsMode,
  searchQuery,
  onZoomIn,
  onZoomOut,
  onFitView,
  onQualityChange,
  onFindingsToggle,
  onSearchChange,
  onToggleFilters,
  onExportCSV,
  onToggle3D,
  show3D,
  onShowPresets,
}: TimelineToolbarProps) {
  const zoom = zoomLevel(viewport, bounds);

  return (
    <div className="timeline-toolbar">
      <div className="toolbar-section">
        <span className="toolbar-title">ТАЙМЛАЙН</span>
        <span className="toolbar-subtitle">
          {photoCount} кадров · {filteredCount} в выборке
        </span>
      </div>

      <div className="toolbar-section">
        <input
          type="text"
          className="toolbar-search"
          placeholder="Поиск по ID, дате, флагам..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

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

      <div className="toolbar-section toolbar-zoom">
        <button className="toolbar-btn" onClick={onZoomOut} title="Отдалить">−</button>
        <button className="toolbar-btn" onClick={onFitView} title="Вписать">⊡</button>
        <button className="toolbar-btn" onClick={onZoomIn} title="Приблизить">+</button>
        <span className="toolbar-zoom-level">×{zoom.toFixed(1)}</span>
      </div>
    </div>
  );
}
