import { useEffect, useMemo, useState } from "react";
import { Spinner } from "./Loading";
import Icon from "./Icon";
import { t } from "../i18n";
import { fetchSkinZones, type SkinZone, type SkinZoneReport } from "../api";

import { useDetailLevel, isVisibleAt } from "../settings";

interface Props {
  photoId: string;
}

const STATUS_COLOR: Record<SkinZone["status"], string> = {
  active: "#6daa45",
  excluded: "#e8af34",
  no_data: "#4a4a52",
};

const QUALITY_CLASS_COLOR: Record<string, string> = {
  good: "#6daa45", ok: "#5591c7", fair: "#e8af34", poor: "#dd6974", bad: "#ff3b30",
};

/** Форматирование значения, которого может не быть.
 *
 * Ключевой принцип (`app6/AGENTS.md`): отсутствующие данные показываются как
 * «нет данных», а НЕ как 0 — ноль здесь означал бы измеренное нулевое
 * значение и вводил бы читателя отчёта в заблуждение. */
function num(value: number | null, digits = 3, suffix = ""): string {
  return value === null ? "—" : `${value.toFixed(digits)}${suffix}`;
}
function pct(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function statusLabel(status: SkinZone["status"]): string {
  if (status === "active") return t.zoneStatusActive;
  if (status === "excluded") return t.zoneStatusExcluded;
  return t.zoneStatusNoData;
}

/** Панель зон кожи.
 *
 * 🚨 Панель НЕ выполняет анализ кожи и не вычисляет метрики: она отображает
 * то, что Stage 1 уже сохранил на диск (`skin_zone_quality.json`,
 * `quality.json`, `wrinkle_zones.json`) и что backend отдаёт через
 * `/api/v1/photos/{id}/skin_zones`. Если артефактов нет — показывается явная
 * причина, а не синтетические числа.
 */
export default function SkinZonesPanel({ photoId }: Props) {
  const [report, setReport] = useState<SkinZoneReport | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [group, setGroup] = useState<string>("all");
  const detailLevel = useDetailLevel();
  const showStandard = isVisibleAt("standard", detailLevel);
  const showExpert = isVisibleAt("expert", detailLevel);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setReport(null);
    fetchSkinZones(photoId)
      .then(data => { if (!cancelled) { setReport(data); setStatus("ready"); } })
      .catch((err: unknown) => {
        if (cancelled) return;
        setStatus("unavailable");
        setErrorMessage(err instanceof Error ? err.message : String(err));
      });
    return () => { cancelled = true; };
  }, [photoId]);

  const groups = useMemo(() => {
    if (!report) return [];
    return Array.from(new Set(report.zones.map(z => z.group).filter((g): g is string => !!g))).sort();
  }, [report]);

  const visibleZones = useMemo(() => {
    if (!report) return [];
    const rows = group === "all" ? report.zones : report.zones.filter(z => z.group === group);
    // Сначала активные с худшей текстурой — именно они требуют внимания
    // аналитика; зоны без данных всегда в конце, чтобы не выдавать их за
    // измерения.
    return [...rows].sort((a, b) => {
      if (a.status !== b.status) {
        const rank = { active: 0, excluded: 1, no_data: 2 } as const;
        return rank[a.status] - rank[b.status];
      }
      const av = a.texture_score ?? Number.POSITIVE_INFINITY;
      const bv = b.texture_score ?? Number.POSITIVE_INFINITY;
      return av - bv;
    });
  }, [report, group]);

  if (status === "loading") {
    return <div className="p-3"><Spinner /></div>;
  }

  if (status === "unavailable") {
    return (
      <div role="status" className="bg-warning/15 border border-warning p-3 font-mono text-[10px] text-warning flex items-start gap-2">
        <Icon name="alert-triangle" size={14} color="#e8af34" className="mt-0.5 flex-shrink-0" />
        <div>
          {t.skinZonesUnavailable}
          <div className="text-text-faint mt-1 break-words">{errorMessage}</div>
        </div>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="space-y-3">
      <p className="font-mono text-[9px] text-text-faint leading-snug">{t.skinZonesSub}</p>

      {/* Сводка по фото */}
      <div className="grid grid-cols-4 gap-2 font-mono text-[10px]">
        <div className="bg-surface-2 border border-border p-2">
          <div className="text-text-muted text-[9px]">{t.zoneStatusActive}</div>
          <div className="text-base" style={{ color: STATUS_COLOR.active }}>{report.active_zone_count}</div>
        </div>
        <div className="bg-surface-2 border border-border p-2">
          <div className="text-text-muted text-[9px]">{t.zoneStatusExcluded}</div>
          <div className="text-base" style={{ color: STATUS_COLOR.excluded }}>{report.excluded_zone_count}</div>
        </div>
        <div className="bg-surface-2 border border-border p-2">
          <div className="text-text-muted text-[9px]">{t.zoneStatusNoData}</div>
          <div className="text-base" style={{ color: STATUS_COLOR.no_data }}>{report.no_data_zone_count}</div>
        </div>
        <div className="bg-surface-2 border border-border p-2">
          <div className="text-text-muted text-[9px]">{t.zoneCoverage}</div>
          <div className="text-base">{pct(report.skin_mask_coverage)}</div>
        </div>
      </div>

      {report.global_texture_quality && (
        <div className="bg-surface-2 border border-border p-2 font-mono text-[10px] flex justify-between">
          <span className="text-text-muted">{t.zoneGlobalTexture}</span>
          <span>
            {report.global_texture_quality.status ?? "—"}
            {report.global_texture_quality.texture_score_0_1 !== undefined
              && ` · ${report.global_texture_quality.texture_score_0_1.toFixed(3)}`}
          </span>
        </div>
      )}

      {/* Фильтр по анатомической группе */}
      {groups.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] text-text-muted tracking-forensic">{t.zoneGroupFilter}</span>
          <select value={group} onChange={e => setGroup(e.target.value)} aria-label={t.zoneGroupFilter}
            className="bg-surface-2 border border-border px-2 py-1 font-mono text-[10px] text-text">
            <option value="all">{t.zoneAll}</option>
            {groups.map(g => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
      )}

      {/* Таблица зон */}
      <div className="space-y-1">
        {visibleZones.map(zone => (
          <details key={zone.name} className="bg-surface-2 border-l-2 border border-border"
            style={{ borderLeftColor: STATUS_COLOR[zone.status] }}>
            <summary className="px-2 py-1 cursor-pointer grid grid-cols-12 gap-1 font-mono text-[10px] items-center">
              <span className={`col-span-5 ${zone.status === "no_data" ? "text-text-muted" : "text-text"}`}>
                {zone.label_ru}
                {zone.zone_id && <span className="text-text-faint ml-1">{zone.zone_id}</span>}
              </span>
              <span className="col-span-3 text-right text-text-muted">
                {t.zoneVisible} {pct(zone.visible_fraction)}
              </span>
              <span className="col-span-2 text-right"
                style={{ color: zone.quality_class ? QUALITY_CLASS_COLOR[zone.quality_class] ?? "#e2e2e8" : "#4a4a52" }}>
                {num(zone.texture_score)}
              </span>
              <span className="col-span-2 text-right text-[9px]" style={{ color: STATUS_COLOR[zone.status] }}>
                {statusLabel(zone.status)}
              </span>
            </summary>

            <div className="px-3 pb-2 pt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 font-mono text-[9px] border-t border-border">
              <Row label={t.zoneTextureScore} value={num(zone.texture_score)} />
              <Row label={t.zoneQualityClass} value={zone.quality_class ?? "—"} />
              {showStandard && (
                <>
                  <Row label={t.zoneSharpness} value={num(zone.laplacian_var, 1)} />
                  <Row label={t.zoneTenengrad} value={num(zone.tenengrad_mean, 1)} />
                </>
              )}
              <Row label={t.zoneHighlight} value={pct(zone.highlight_fraction)} />
              <Row label={t.zoneShadow} value={pct(zone.shadow_fraction)} />
              {showExpert && (
                <Row label={t.zoneSkinPixels} value={zone.skin_pixels === null ? "—" : String(zone.skin_pixels)} />
              )}
              <Row label={t.zoneVisible} value={pct(zone.visible_fraction)} />
              {zone.exclusion_reasons.length > 0 && (
                <div className="col-span-2 mt-1 text-warning">
                  {t.zoneExclusionReasons}: {zone.exclusion_reasons.join(", ")}
                </div>
              )}
              {showExpert && zone.roi_source && (
                <div className="col-span-2 text-text-faint mt-0.5 break-words">roi_source: {zone.roi_source}</div>
              )}
            </div>
          </details>
        ))}
      </div>

      {/* Честный перечень источников: из чего построен отчёт */}
      <div className="bg-surface-2 border border-border p-2 font-mono text-[9px]">
        <div className="text-text-muted tracking-forensic mb-1">{t.zoneSourcesTitle}</div>
        <SourceRow label={t.zoneSourceSkin} present={report.available_sources.skin_zone_quality} />
        <SourceRow label={t.zoneSourceQuality} present={report.available_sources.per_zone_quality} />
        <SourceRow label={t.zoneSourceWrinkle} present={report.available_sources.wrinkle_zones} />
        {report.available_sources.wrinkle_note && (
          <div className="text-text-faint mt-1 break-words">{report.available_sources.wrinkle_note}</div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-text-muted">{label}</span>
      <span className={value === "—" ? "text-text-faint" : "text-text"}>{value}</span>
    </div>
  );
}

function SourceRow({ label, present }: { label: string; present: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-muted">{label}</span>
      <span style={{ color: present ? "#6daa45" : "#797876" }}>
        {present ? t.zoneSourcePresent : t.zoneSourceAbsent}
      </span>
    </div>
  );
}
