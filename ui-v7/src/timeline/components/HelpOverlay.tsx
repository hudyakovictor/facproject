/**
 * Help overlay component.
 * Shows keyboard shortcuts and usage information.
 */

interface HelpOverlayProps {
  onClose: () => void;
}

const KEYBOARD_SHORTCUTS = [
  { category: 'Навигация', shortcuts: [
    { keys: ['←', '→'], description: 'Предыдущий/следующий кадр' },
    { keys: ['Tab'], description: 'Следующая находка' },
    { keys: ['Shift', 'Tab'], description: 'Предыдущая находка' },
    { keys: ['0'], description: 'Вписать весь диапазон' },
  ]},
  { category: 'Зум', shortcuts: [
    { keys: ['+', '='], description: 'Приблизить' },
    { keys: ['-'], description: 'Отдалить' },
    { keys: ['Scroll'], description: 'Зум от курсора' },
    { keys: ['Shift', 'Scroll'], description: 'Горизонтальная прокрутка' },
  ]},
  { category: 'Выбор', shortcuts: [
    { keys: ['Click'], description: 'Выбрать кадр' },
    { keys: ['Shift', 'Click'], description: 'Назначить в пару A/B' },
    { keys: ['A'], description: 'Назначить выбранный в пару' },
    { keys: ['Esc'], description: 'Снять выбор / закрыть панель' },
  ]},
  { category: 'Интерфейс', shortcuts: [
    { keys: ['F'], description: 'Открыть фильтры' },
    { keys: ['?'], description: 'Показать эту справку' },
  ]},
];

const METRIC_LEGEND = [
  { color: 'var(--metric-quality)', label: 'Качество', description: 'Качество кадра и выравнивания' },
  { color: 'var(--metric-texture)', label: 'Текстура', description: 'Аутентичность кожи, признак силикона' },
  { color: 'var(--metric-geometry)', label: 'Геометрия', description: 'Костная основа, симметрия' },
  { color: 'var(--metric-anomaly)', label: 'LDM различие', description: 'Изменения формы лица' },
  { color: 'var(--color-synthetic)', label: 'Аномалия', description: 'Обнаруженные аномалии' },
];

export function HelpOverlay({ onClose }: HelpOverlayProps) {
  return (
    <>
      <div className="help-overlay" onClick={onClose} />
      <div className="help-panel">
        <div className="help-header">
          <span className="help-title">СПРАВКА · КЛАВИАТУРНЫЕ СОКРАЩЕНИЯ</span>
          <button className="help-close" onClick={onClose} aria-label="Закрыть">×</button>
        </div>
        <div className="help-content">
          <div className="help-section">
            <div className="help-section-title">Клавиатурные сокращения</div>
            <div className="help-shortcuts">
              {KEYBOARD_SHORTCUTS.map(category => (
                <div key={category.category} className="help-shortcut-category">
                  <div className="help-category-name">{category.category}</div>
                  <div className="help-shortcut-list">
                    {category.shortcuts.map(shortcut => (
                      <div key={shortcut.keys.join('-')} className="help-shortcut-item">
                        <div className="help-shortcut-keys">
                          {shortcut.keys.map((key, i) => (
                            <kbd key={i}>{key}</kbd>
                          ))}
                        </div>
                        <span className="help-shortcut-desc">{shortcut.description}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="help-section">
            <div className="help-section-title">Легенда метрик</div>
            <div className="help-legend">
              {METRIC_LEGEND.map(item => (
                <div key={item.label} className="help-legend-item">
                  <span className="help-legend-swatch" style={{ backgroundColor: item.color }} />
                  <div className="help-legend-text">
                    <span className="help-legend-label">{item.label}</span>
                    <span className="help-legend-desc">{item.description}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="help-section">
            <div className="help-section-title">О системе</div>
            <div className="help-about">
              <p>
                <strong>DEEPUTIN UI-v7</strong> — исследовательская рабочая станция для 
                продольного технического сравнения фотоархива.
              </p>
              <p>
                Система извлекает и визуализирует геометрию, landmarks, pose, visibility, 
                provenance, quality и хронологические измерения.
              </p>
              <p className="help-warning">
                ⚠ Автоматический статус является наблюдением/кандидатом на ручную проверку, 
                <strong> не вердиктом о личности</strong>.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
