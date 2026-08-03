import { memo, useState } from "react";
import { t } from "../i18n";
import Icon from "./Icon";
import type { KeyValue } from "../api";
import {
  commonPrefix, filledCount, formatKeyValue, groupTitle, isLongValue, keyLabel, keyTone,
  TONE_COLORS,
} from "../keys";

/** Универсальная таблица «ключ → значение» для данных пайплайна.
 *
 * Один компонент обслуживает все девять категорий карты размещения ключей:
 * заводить по компоненту на группу означало бы ~45 почти одинаковых файлов.
 *
 * Отсутствующие значения показываются как «—» и НЕ скрываются: пропуск —
 * это результат («канал не измерен»), а не пустое место. Скрыть их можно
 * переключателем, и тогда факт скрытия подписывается явно.
 */
function KeyGroupBase({ id, values, defaultOpen = true, dense = false }: {
  id: string;
  values: Record<string, KeyValue>;
  defaultOpen?: boolean;
  dense?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [hideEmpty, setHideEmpty] = useState(false);

  const keys = Object.keys(values);
  if (keys.length === 0) return null;

  const filled = filledCount(values);
  const prefix = commonPrefix(keys);
  const shown = hideEmpty ? keys.filter(k => values[k] !== null) : keys;
  const hiddenCount = keys.length - shown.length;

  return (
    <div className="border border-border bg-surface-2">
      <div className="flex items-center gap-2 px-2 py-1 border-b border-border/60">
        <button
          onClick={() => setOpen(v => !v)}
          aria-expanded={open}
          className="flex items-center gap-1.5 flex-1 min-w-0 text-left font-mono text-[9px] tracking-forensic text-text-muted hover:text-text">
          <Icon name={open ? "chevron-down" : "chevron-right"} size={10} />
          <span className="truncate">{groupTitle(id)}</span>
          {/* Честный счётчик: сколько ключей группы реально измерено. */}
          <span className={filled === keys.length ? "text-text-faint" : "text-warning"}>
            {filled}/{keys.length}
          </span>
        </button>
        {open && filled < keys.length && (
          <button
            onClick={() => setHideEmpty(v => !v)}
            aria-pressed={hideEmpty}
            title={t.keysHideEmptyTitle}
            className={`px-1.5 py-0.5 font-mono text-[8px] tracking-forensic border ${hideEmpty ? "bg-info/25 border-info text-text" : "border-border text-text-muted hover:text-text"}`}>
            {t.keysHideEmpty}
          </button>
        )}
      </div>

      {open && (
        <div className={dense ? "" : "px-0.5 py-0.5"}>
          <table className="w-full border-collapse font-mono text-[10px]">
            <tbody>
              {shown.map(key => {
                const value = values[key];
                const tone = keyTone(key, value);
                const color = TONE_COLORS[tone];
                const long = isLongValue(value);
                return (
                  <tr key={key} className="border-t border-border/40 align-top">
                    <td className="py-0.5 px-1 text-text-muted w-1/2" title={key}>
                      {keyLabel(key, prefix)}
                    </td>
                    <td
                      className={`py-0.5 px-1 text-right tabular-nums ${long ? "break-all text-left" : ""}`}
                      style={{ color }}
                      title={value === null ? t.keysNoData : String(value)}>
                      {formatKeyValue(value)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {hiddenCount > 0 && (
            <div className="px-1 py-0.5 font-mono text-[8px] text-text-faint">
              {t.keysHiddenNotice(hiddenCount)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Категория целиком: заголовок + все её подгруппы. */
export function KeyCategory({ title, groups, defaultOpen = true, note }: {
  title: string;
  groups: Record<string, Record<string, KeyValue>>;
  defaultOpen?: boolean;
  note?: string;
}) {
  const ids = Object.keys(groups);
  if (ids.length === 0) return null;
  const total = ids.reduce((sum, id) => sum + Object.keys(groups[id]).length, 0);
  const filled = ids.reduce((sum, id) => sum + filledCount(groups[id]), 0);

  return (
    <section className="space-y-1.5">
      <header className="flex items-baseline gap-2">
        <h3 className="font-display text-xs tracking-forensic">{title}</h3>
        <span className="font-mono text-[9px] text-text-faint">{filled}/{total}</span>
      </header>
      {note && <p className="font-mono text-[9px] text-text-faint">{note}</p>}
      {ids.map(id => (
        <KeyGroup key={id} id={id} values={groups[id]} defaultOpen={defaultOpen} />
      ))}
    </section>
  );
}

/** Группа перерисовывается только при смене объекта `values`.
 *
 * В панели метрик пары одновременно живут до девяти групп, в сводке
 * прогона — больше двадцати. Раскрытие одной из них меняло состояние
 * родителя и перерисовывало все остальные вместе с их таблицами.
 *
 * `values` приходит из `useMemo` вызывающего кода, поэтому ссылочное
 * сравнение здесь корректно. */
export const KeyGroup = memo(KeyGroupBase);

export default KeyGroup;
