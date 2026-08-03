import { useMemo, useState } from "react";
import { t } from "../i18n";
import type { Photo } from "../data";

interface Props {
  photos: Photo[];
  value: string;
  onChange: (id: string) => void;
  label: string;
  /** Сколько позиций показывать одновременно. */
  pageSize?: number;
}

/** Выбор фотографии из большого архива с поиском.
 *
 * Прежние селекторы делали `photos.slice(0, 300)` / `.slice(0, 500)`: при
 * 1700+ кадрах бо́льшая часть архива была недоступна для выбора, и
 * пользователь никак об этом не узнавал. ТЗ прямо требует поддержки больших
 * коллекций.
 *
 * Здесь список фильтруется поиском и усечение показывается явно — с числом
 * скрытых позиций.
 */
export default function PhotoPicker({ photos, value, onChange, label, pageSize = 200 }: Props) {
  const [query, setQuery] = useState("");

  const matched = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return photos;
    return photos.filter(p =>
      p.id.toLowerCase().includes(q)
      || p.date.includes(q)
      || p.bucket.toLowerCase().includes(q));
  }, [photos, query]);

  // Выбранный кадр обязан присутствовать в списке, даже если не попал в
  // текущую страницу: иначе select показал бы чужое значение.
  const visible = useMemo(() => {
    const head = matched.slice(0, pageSize);
    if (value && !head.some(p => p.id === value)) {
      const selected = photos.find(p => p.id === value);
      if (selected) return [selected, ...head];
    }
    return head;
  }, [matched, pageSize, value, photos]);

  const hidden = Math.max(0, matched.length - pageSize);

  return (
    <div className="space-y-1">
      <input
        type="search" value={query} onChange={e => setQuery(e.target.value)}
        placeholder={t.pickerSearch} aria-label={`${label}: ${t.pickerSearch}`}
        className="w-full bg-surface-2 border border-border px-2 py-1 font-mono text-[10px] text-text"
      />
      <select value={value} onChange={e => onChange(e.target.value)} aria-label={label}
        disabled={matched.length === 0}
        className="w-full bg-surface-2 border border-border p-2 font-mono text-[10px]">
        {matched.length === 0
          ? <option value="">{t.pickerNoMatch}</option>
          : visible.map(p => (
              <option key={p.id} value={p.id}>{p.id} · {p.date} · {p.bucket}</option>
            ))}
      </select>
      <div className="font-mono text-[8px] text-text-faint">
        {t.pickerShowing} {Math.min(visible.length, matched.length)} {t.pickerOf} {photos.length}
        {hidden > 0 && (
          <span className="text-warning"> · {t.pickerTruncated} (+{hidden})</span>
        )}
      </div>
    </div>
  );
}
