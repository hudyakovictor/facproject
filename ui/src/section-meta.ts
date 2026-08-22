export type SectionKey = 'atlas' | 'casework' | 'matrix' | 'keypoints' | 'methodology' | 'calibration' | 'persistence' | 'metrics' | 'report' | 'integrity'

export const SECTION_META: { key: SectionKey; label: string; short: string; hint: string }[] = [
  { key: 'atlas', label: 'Зональный атлас', short: 'Атлас', hint: 'Где именно на лице локализованы различия пар (3×3 зоны), включая хронологию зон по годам' },
  { key: 'casework', label: 'Проверка кандидатов', short: 'Очередь', hint: 'Все FDR-кандидаты всех ракурсов; решения 1/2/3; фильтры по ракурсу и статусу' },
  { key: 'matrix', label: 'Корроборация', short: 'Корроб.', hint: 'Сигнал одного периода в нескольких ракурсах = независимое подтверждение' },
  { key: 'keypoints', label: 'Ключевые точки', short: 'Точки', hint: 'Смещение ключевых точек пар: векторы, анимация по хронологии, пороги шума и аномалий' },
  { key: 'methodology', label: 'Методика и качество', short: 'Методика', hint: 'Единый контрольный слой: калибровка, целостность архива и смысл метрик' },
  { key: 'calibration', label: 'Калибровка', short: 'Калибр.', hint: 'Шум метода: распределения z, здоровье ракурсов, рекомендации' },
  { key: 'persistence', label: 'Устойчивость во времени', short: 'Устойчивость', hint: 'Цепочки устойчивых изменений во времени — сдвиг, удержавшийся годами' },
  { key: 'metrics', label: 'Метрики и поля', short: 'Метрики', hint: 'Справочник метрик и полей: назначение, приоритет и место отображения' },
  { key: 'report', label: 'Отчёт', short: 'Отчёт', hint: 'Принятые к отчёту кандидаты, заметки, экспорт HTML/CSV/JSON' },
  { key: 'integrity', label: 'Целостность данных', short: 'Данные', hint: 'Самопроверка данных в браузере (PASS/FAIL), покрытие, контракт' },
]
