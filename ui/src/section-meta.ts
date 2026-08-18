export type SectionKey = 'atlas' | 'casework' | 'matrix' | 'keypoints' | 'calibration' | 'persistence' | 'metrics' | 'report' | 'integrity'

export const SECTION_META: { key: SectionKey; label: string; short: string; hint: string }[] = [
  { key: 'atlas', label: 'Зональный атлас', short: 'Атлас', hint: 'Где именно на лице локализованы различия пар (3×3 зоны), включая хронологию зон по годам' },
  { key: 'casework', label: 'Проверка кандидатов', short: 'Очередь', hint: 'Все FDR-кандидаты всех ракурсов; решения 1/2/3; фильтры по ракурсу и статусу' },
  { key: 'matrix', label: 'Корроборация', short: 'Корроб.', hint: 'Сигнал одного периода в нескольких ракурсах = независимое подтверждение' },
  { key: 'keypoints', label: 'Ключевые точки', short: 'Точки', hint: 'Смещение ключевых точек пар: векторы, анимация по хронологии, пороги шума и аномалий' },
  { key: 'calibration', label: 'Калибровка', short: 'Калибр.', hint: 'Шум метода: распределения z, здоровье ракурсов, рекомендации' },
  { key: 'persistence', label: 'Persistence', short: 'Persist.', hint: 'Цепочки устойчивых изменений во времени — сдвиг, удержавшийся годами' },
  { key: 'metrics', label: 'Метрики пар', short: 'Метрики', hint: 'Полный каталог метрик: статусы, калибровка, роли FDR — что где отображается' },
  { key: 'report', label: 'Отчёт', short: 'Отчёт', hint: 'Принятые к отчёту кандидаты, заметки, экспорт HTML/CSV/JSON' },
  { key: 'integrity', label: 'Целостность данных', short: 'Данные', hint: 'Самопроверка данных в браузере (PASS/FAIL), покрытие, контракт' },
]
