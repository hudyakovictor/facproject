import { useEffect, useMemo, useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import { fetchZoneCatalog, type ZoneCatalogEntry } from "../api";

/** 🗂 Нормативный атлас зон кожи (`GET /api/v1/zones/catalog`).
 *
 * Эндпоинт и клиент `fetchZoneCatalog` существовали, но не имели ни одного
 * потребителя. Панель показывает ПОЛНЫЙ список зон из
 * `app6/atlas/skin_zone_atlas.json`, включая те, для которых у конкретного
 * фото нет данных, — иначе отсутствие зоны в отчёте невозможно отличить от
 * её отсутствия в атласе.
 */
export default function ZoneCatalog() {
  const [zones, setZones] = useState<ZoneCatalogEntry[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchZoneCatalog()
      .then(payload => { if (!cancelled) setZones(payload.zones); })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => { cancelled = true; };
  }, []);

  const byGroup = useMemo(() => {
    const out = new Map<string, ZoneCatalogEntry[]>();
    for (const zone of zones ?? []) {
      const key = zone.group ?? "—";
      const list = out.get(key);
      if (list) list.push(zone); else out.set(key, [zone]);
    }
    return [...out.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [zones]);

  if (error) {
    return (
      <div role="status" className="font-mono text-[10px] text-warning">
        {t.zoneCatalogUnavailable}: {error}
      </div>
    );
  }
  if (!zones) return <div className="font-mono text-[10px] text-text-muted">{t.loading}…</div>;

  return (
    <section>
      <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-1">
        {t.zoneCatalogTitle} · {zones.length} {t.zoneCatalogTotal}
      </div>
      <p className="font-mono text-[8px] text-text-faint mb-2 leading-snug">{t.zoneCatalogHint}</p>
      <div className="space-y-2">
        {byGroup.map(([group, list]) => (
          <div key={group}>
            <div className="font-mono text-[8px] text-text-muted tracking-forensic mb-0.5">
              {group} · {list.length}
            </div>
            <div className="flex flex-wrap gap-1">
              {list.map(zone => (
                <span key={zone.zone_id}
                  title={zone.excluded_by_segmentation ? t.zoneCatalogExcluded : zone.name}
                  className="font-mono text-[8px] px-1 py-0.5 border flex items-center gap-1"
                  style={{
                    borderColor: zone.excluded_by_segmentation ? "#e8af34" : "var(--color-border)",
                    color: zone.excluded_by_segmentation ? "#e8af34" : undefined,
                  }}>
                  {zone.excluded_by_segmentation && <Icon name="eye-off" size={7} color="#e8af34" />}
                  {zone.label_ru}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
