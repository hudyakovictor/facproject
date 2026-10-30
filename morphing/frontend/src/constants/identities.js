// Цвета трёх эталонных личностей — одни и те же во всём интерфейсе:
// панель «Сходство с эталонами» и таблица метрик формы красят этим же.
export const IDENTITY_COLORS = { put: '#1f6feb', vas: '#ab7df8', udmurt: '#f0883e' };

// Подпись личности: полное имя в легенде, одна буква — в тесной ячейке таблицы.
export const IDENTITY_LABELS = { put: 'put', vas: 'vas', udmurt: 'udmurt' };
export const IDENTITY_LETTERS = { put: 'П', vas: 'В', udmurt: 'У' };

export const UNKNOWN_COLOR = '#8b949e';

export function identityColor(ident) {
  return IDENTITY_COLORS[ident] || UNKNOWN_COLOR;
}
