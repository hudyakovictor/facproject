import { useMemo } from 'react'
import type { Frame, PairConnection, ZoneMetric } from './types'
import type { SectionKey } from './section-meta'
import { SectionShell } from './SectionShell'

/* Единая точка входа для технических разделов.
 * Полные аудиты намеренно остаются отдельными deep-link экранами, но в меню
 * журналиста показывается один слой «Методика и качество». */
export function Methodology({ frames, pairs, zones, onClose, onNavigate }: {
  frames: Frame[]
  pairs: PairConnection[]
  zones: Map<string, ZoneMetric[]>
  onClose: () => void
  onNavigate: (key: SectionKey) => void
}) {
  const summary = useMemo(() => {
    const frameIds = new Set(frames.map(f => f.id))
    const orphanPairs = pairs.filter(p => !frameIds.has(p.photoA) || !frameIds.has(p.photoB)).length
    const calibrated = pairs.filter(p => p.meshCalibratedMetricCount != null).length
    const elevated = pairs.filter(p => p.meshCalibratedStatus === 'mesh_elevated').length
    const fdr = pairs.filter(p => p.mtSignificantFdr10).length
    const zoneRows = [...zones.values()].reduce((n, rows) => n + rows.length, 0)
    const conflicts = frames.filter(f => f.dateConflictSources && f.dateConflictSources !== '[]').length
    return { orphanPairs, calibrated, elevated, fdr, zoneRows, conflicts }
  }, [frames, pairs, zones])

  const auditButton = (key: SectionKey, label: string) => (
    <button className="methodology-open" onClick={() => onNavigate(key)}>{label} →</button>
  )

  return (
    <SectionShell title="Методика и качество" current="methodology" onNavigate={onNavigate} onClose={onClose}
      scope={`${frames.length} кадров · ${pairs.length} пар · ${zones.size} пар с зонами`}
      help={<>Этот раздел не выносит технические поля на первый план. Здесь собраны только проверки, которые влияют на силу вывода: калибровка, целостность исходного архива и смысл метрик. «Кандидат» по-прежнему не является вердиктом.</>}>
      <div className="methodology-intro">
        <h3>Что нужно знать перед интерпретацией</h3>
        <p>Сначала проверяем, что архив полный и связан корректно. Затем смотрим, насколько измерения отделяются от шума. Только после этого читаем метрики и FDR-кандидатов в рабочих разделах.</p>
      </div>

      <div className="methodology-grid">
        <article className="sec-card methodology-card">
          <div className="methodology-kicker">01 · НАДЁЖНОСТЬ ИЗМЕРЕНИЯ</div>
          <h3>Калибровка</h3>
          <div className="methodology-stats"><b>{summary.calibrated}</b><span>из {pairs.length} пар с калибровкой</span><b>{summary.elevated}</b><span>повышенных</span></div>
          <p className="sec-note">Показывает, превышает ли сигнал ожидаемый шум метода. FDR-кандидаты ({summary.fdr}) — повод для проверки, а не доказательство.</p>
          {auditButton('calibration', 'Открыть полный аудит калибровки')}
        </article>

        <article className="sec-card methodology-card">
          <div className="methodology-kicker">02 · ДОСТОВЕРНОСТЬ АРХИВА</div>
          <h3>Целостность данных</h3>
          <div className="methodology-stats"><b className={summary.orphanPairs ? 'methodology-bad' : 'methodology-good'}>{summary.orphanPairs}</b><span>сиротских пар</span><b>{summary.zoneRows}</b><span>строк зон</span></div>
          <p className="sec-note">Проверяет связи кадров, 3×3 зоны, пропуски и конфликты дат. Ошибка здесь обесценивает последующий анализ.</p>
          {auditButton('integrity', 'Открыть полный аудит целостности')}
        </article>

        <article className="sec-card methodology-card">
          <div className="methodology-kicker">03 · СМЫСЛ ПОКАЗАТЕЛЕЙ</div>
          <h3>Метрики и поля</h3>
          <div className="methodology-stats"><b>6</b><span>геометрических метрик</span><b>3</b><span>уровня интерпретации</span></div>
          <p className="sec-note">Справочник объясняет, что реально используется в интерфейсе: RMSE/robust-z, FDR и контекстные ограничения. Остальные поля — техническая трассировка.</p>
          {auditButton('metrics', 'Открыть справочник метрик')}
        </article>
      </div>

      <details className="sec-disclosure methodology-disclosure">
        <summary>Короткая схема чтения результатов</summary>
        <div className="sec-disclosure-body">
          <div className="methodology-flow"><span>Архив</span><i>→</i><span>Целостность</span><i>→</i><span>Калибровка</span><i>→</i><span>Метрики</span><i>→</i><span>Кандидат</span></div>
          <p className="sec-note">Если слева есть проблема, справа нельзя делать сильный вывод. Хронология, ракурс и повторяемость в нескольких независимых ракурсах проверяются уже в основных разделах.</p>
        </div>
      </details>
    </SectionShell>
  )
}
