import { FILTER_PRESETS, applyPreset } from '../filterPresets';

/**
 * Filter presets component.
 * Quick selection of predefined filter configurations.
 */

interface FilterPresetsProps {
  onClose: () => void;
}

export function FilterPresets({ onClose }: FilterPresetsProps) {

  const handleApplyPreset = (presetId: string) => {
    applyPreset(presetId);
    onClose();
  };

  return (
    <>
      <div className="filter-overlay" onClick={onClose} />
      <div className="presets-panel">
        <div className="presets-header">
          <span className="presets-title">ПРЕСЕТЫ ФИЛЬТРОВ</span>
          <button className="presets-close" onClick={onClose} aria-label="Закрыть">×</button>
        </div>
        <div className="presets-content">
          {FILTER_PRESETS.map(preset => (
            <button
              key={preset.id}
              className="preset-item"
              onClick={() => handleApplyPreset(preset.id)}
            >
              <span className="preset-label">{preset.label}</span>
              <span className="preset-description">{preset.description}</span>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
