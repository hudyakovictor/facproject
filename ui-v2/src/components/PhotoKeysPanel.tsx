import { useEffect, useMemo, useState } from "react";
import { fetchPhotoInfoKeys, type PhotoInfoKeys, type KeyValue } from "../api";
import { CATEGORY_ORDER, flattenKeys } from "../keys";
import { KeyGroup } from "./KeyTable";
import { Spinner } from "./Loading";
import Icon from "./Icon";
import { getLanguage, t } from "../i18n";

/** Ключи Stage 1 `info.json` одного фото: параметры кадра, маски, UV, провенанс.
 *
 * Stage 1 сохраняет 156 листовых значений на кадр — параметры резкости и
 * шума, доли площади восьми семантических каналов маски, покрытие UV,
 * репроекцию, камеру, кроп и хэши воспроизводимости. Интерфейс использовал
 * из них около восьми.
 *
 * `only` ограничивает вывод конкретными категориями: панель встраивается и
 * в вкладку «Фото» (параметры кадра), и в попап провенанса (G), и в
 * «Кожу» (маски/UV) — с разным набором.
 */
export default function PhotoKeysPanel({ photoId, only, defaultOpen = false }: {
  photoId: string;
  only?: readonly string[];
  defaultOpen?: boolean;
}) {
  const [data, setData] = useState<PhotoInfoKeys | null>(null);
  const [state, setState] = useState<"loading" | "idle" | "unavailable" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!photoId) return;
    let cancelled = false;
    setState("loading");
    setData(null);
    fetchPhotoInfoKeys(photoId)
      .then(payload => { if (!cancelled) { setData(payload); setState("idle"); } })
      .catch((err: unknown) => {
        if (cancelled) return;
        const text = err instanceof Error ? err.message : String(err);
        setState(/409|404/.test(text) ? "unavailable" : "error");
        setMessage(text);
      });
    return () => { cancelled = true; };
  }, [photoId]);

  /** Ветви `info.json` вложены до трёх уровней (`crop.letterbox.offset_x`);
   * таблица работает с плоскими парами, поэтому уплощаем здесь. */
  const flat = useMemo(() => {
    if (!data) return {};
    const out: Record<string, Record<string, Record<string, KeyValue>>> = {};
    for (const category of CATEGORY_ORDER) {
      const groups = data.categories[category];
      if (!groups) continue;
      if (only && !only.includes(category)) continue;
      for (const [group, values] of Object.entries(groups)) {
        out[category] ??= {};
        out[category][group] = flattenKeys(values);
      }
    }
    return out;
  }, [data, only]);

  if (state === "loading") return <Spinner label={t.keysLoading} />;

  if (state === "unavailable") {
    return (
      <div role="status" className="bg-warning/10 border border-warning/40 p-2 font-mono text-[9px] text-warning flex items-start gap-1.5">
        <Icon name="alert-triangle" size={11} color="#e8af34" className="mt-0.5 flex-shrink-0" />
        <div>
          <div>{t.keysPhotoUnavailable}</div>
          <div className="text-text-faint mt-0.5 break-words">{message}</div>
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div role="alert" className="font-mono text-[9px] text-critical break-words">
        {t.keysLoadFailed}: {message}
      </div>
    );
  }

  const categories = Object.keys(flat);
  if (!data || categories.length === 0) return null;

  return (
    <div className="space-y-2">
      {categories.map(category => (
        <div key={category} className="space-y-1">
          <div className="font-mono text-[9px] tracking-forensic text-text-muted">
            {titleOf(data, category)}
          </div>
          {Object.entries(flat[category]).map(([group, values]) => (
            <KeyGroup key={group} id={group} values={values} defaultOpen={defaultOpen} />
          ))}
        </div>
      ))}
      <div className="font-mono text-[8px] text-text-faint">
        {t.keysPhotoLeafCount(data.leaf_count)}
      </div>
    </div>
  );
}

function titleOf(data: PhotoInfoKeys, id: string): string {
  const entry = data.category_titles[id];
  if (!entry) return id;
  return getLanguage() === "en" ? entry.en : entry.ru;
}
