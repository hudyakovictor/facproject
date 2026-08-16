/**
 * Слепой режим (§18.3 ТЗ).
 *
 * Рецензент должен оценивать геометрию, а не узнавать кадр по дате и имени
 * файла: знание «это 2014 год, тот самый снимок» смещает суждение ещё до того,
 * как он посмотрит на измерения. В слепом режиме идентифицирующие подписи
 * заменяются устойчивыми псевдонимами.
 *
 * Скрываются подписи, а не данные. Метрики, ракурс и качество остаются видимы:
 * прятать измерения означало бы сделать оценку невозможной.
 */

/**
 * Устойчивый псевдоним кадра.
 *
 * Порядковый номер берётся из позиции в переданном списке, а не из хеша: он
 * должен быть коротким и читаемым вслух при обсуждении. Один и тот же кадр в
 * пределах сессии всегда получает один и тот же псевдоним.
 */
export function blindAlias(id: string, order: number): string {
  return `КАДР-${String(order + 1).padStart(3, "0")}`;
}

/** Построить таблицу псевдонимов для набора кадров. */
export function blindAliases(ids: readonly string[]): Map<string, string> {
  return new Map(ids.map((id, index) => [id, blindAlias(id, index)]));
}

/**
 * Подпись кадра с учётом режима.
 *
 * В слепом режиме дата не показывается совсем: округление до года всё ещё
 * позволяет узнать снимок, а «примерно 2014» создаёт ложное ощущение, что
 * дата известна приблизительно, хотя она известна точно.
 */
export function frameLabel(
  options: { id: string; date: string | null; order: number },
  blind: boolean,
): string {
  if (blind) return blindAlias(options.id, options.order);
  return options.date ?? options.id;
}

/** Подробная подпись: идентификатор и дата, либо псевдоним. */
export function frameTitle(
  options: { id: string; date: string | null; order: number },
  blind: boolean,
): string {
  if (blind) return `${blindAlias(options.id, options.order)} · подписи скрыты слепым режимом`;
  return `${options.date ?? "дата отсутствует"} · ${options.id}`;
}
