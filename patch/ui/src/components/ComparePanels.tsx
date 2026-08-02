import { useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import { heatHex, DEFAULT_HEATMAP_STOPS } from "../heatscale";
import { photoImageUrl, type CompareResult } from "../api";

type Stops = typeof DEFAULT_HEATMAP_STOPS;

/** Кадр A или B рядом с оппонентом (ТЗ: «визуализацией обоих изображений рядом»).
 *
 * Раньше режим сравнения показывал только меш, и сопоставить лица глазами
 * было невозможно. Изображение берётся из артефактов Stage 1; если его нет
 * (demo-режим), показывается причина, а не пустой прямоугольник. */
export function PhotoPair({ a, b }: {
  a: { id: string; date: string; bucket: string };
  b: { id: string; date: string; bucket: string };
}) {
  return (
    <div className="grid grid-cols-2 gap-2">
      <PhotoCard photo={a} side="A" accent="#5591c7" />
      <PhotoCard photo={b} side="B" accent="#e8af34" />
    </div>
  );
}

function PhotoCard({ photo, side, accent }: {
  photo: { id: string; date: string; bucket: string }; side: string; accent: string;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <figure className="bg-surface border border-border" style={{ borderTopColor: accent, borderTopWidth: 2 }}>
      <div className="relative aspect-[3/4] bg-surface-2 flex items-center justify-center overflow-hidden">
        {failed ? (
          <div className="p-3 text-center font-mono text-[9px] text-text-muted">
            <Icon name="image" size={16} className="mx-auto mb-1 opacity-40" />
            {t.photoImageUnavailable}
          </div>
        ) : (
          <img
            src={photoImageUrl(photo.id, "original")}
            alt={`${side}: ${photo.id}`}
            onError={() => setFailed(true)}
            className="w-full h-full object-cover"
          />
        )}
        <span className="absolute top-1 left-1 font-mono text-[9px] px-1.5 py-0.5 bg-bg/80" style={{ color: accent }}>
          {side}
        </span>
      </div>
      <figcaption className="p-1.5 font-mono text-[9px]">
        <div className="text-text truncate" title={photo.id}>{photo.id}</div>
        <div className="text-text-muted">{photo.date} · {photo.bucket}</div>
      </figcaption>
    </figure>
  );
}

/** Легенда тепловой карты: градиент с числовой шкалой.
 *
 * Без шкалы карту нельзя прочитать — видно лишь «где-то краснее». Значения
 * подписываются в тех же единицах, что и residual. */
export function HeatmapLegend({ stops, unit = "" }: { stops: Stops; unit?: string }) {
  const steps = 40;
  // Легенда не должна ронять весь режим сравнения, если цветовая функция
  // недоступна (например WebGL-слой не инициализирован): деградируем до
  // нейтрального градиента, а сами числа шкалы остаются верными.
  const swatch = (fraction: number): string => {
    try {
      return heatHex(fraction, stops);
    } catch {
      return "#797876";
    }
  };
  const gradient = Array.from({ length: steps + 1 }, (_, i) =>
    `${swatch(i / steps)} ${(i / steps) * 100}%`).join(", ");
  const maxRef = stops.maxReference;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => ({ f, value: f * maxRef }));

  return (
    <div className="font-mono text-[9px]">
      <div className="text-text-muted tracking-forensic mb-1">{t.heatmapLegendTitle}</div>
      <div className="h-3 w-full border border-border" style={{ background: `linear-gradient(to right, ${gradient})` }} />
      <div className="relative h-4 mt-0.5">
        {ticks.map(({ f, value }) => (
          <span key={f} className="absolute text-text-faint -translate-x-1/2"
            style={{ left: `${f * 100}%` }}>
            {value.toFixed(3)}
          </span>
        ))}
      </div>
      <div className="text-text-faint mt-0.5">{t.heatmapLegendHint}{unit ? ` (${unit})` : ""}</div>
    </div>
  );
}

/** Таблица зон со ЗНАКОВЫМИ смещениями.
 *
 * Backend уже возвращает per-zone `rmse`/`median`/`p95` и медианные
 * `signed_x/y/z`, но интерфейс не показывал ничего. Знак смещения отвечает на
 * вопрос «в чём именно различие»: куда сместилась геометрия зоны, а не только
 * насколько сильно. */
export function ZoneBreakdown({ zones }: { zones: CompareResult["zones"] }) {
  const measured = zones.filter(z => z.status === "measured");
  const skipped = zones.filter(z => z.status !== "measured");
  const worst = Math.max(1e-9, ...measured.map(z => z.rmse ?? 0));

  return (
    <div className="font-mono text-[9px]">
      <div className="text-text-muted tracking-forensic mb-1">
        {t.zoneBreakdownTitle} · {measured.length}/{zones.length}
      </div>
      {measured.length === 0 ? (
        <div className="text-text-faint">{t.zoneBreakdownEmpty}</div>
      ) : (
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-text-faint">
              <th className="text-left font-normal py-0.5">{t.zoneCol}</th>
              <th className="text-right font-normal">RMSE</th>
              <th className="text-right font-normal">n</th>
              <th className="text-right font-normal" title={t.signedShiftTitle}>Δx / Δy / Δz</th>
            </tr>
          </thead>
          <tbody>
            {[...measured].sort((x, y) => (y.rmse ?? 0) - (x.rmse ?? 0)).map(zone => {
              const share = (zone.rmse ?? 0) / worst;
              const sx = zone.signed_x ?? 0, sy = zone.signed_y ?? 0, sz = zone.signed_z ?? 0;
              return (
                <tr key={zone.zone} className="border-t border-border/60">
                  <td className="py-0.5 text-text">{zone.zone}</td>
                  <td className="text-right">
                    <span className="inline-flex items-center gap-1 justify-end">
                      <span className="inline-block h-1" style={{
                        width: `${Math.max(2, share * 32)}px`,
                        background: share > 0.75 ? "#dd6974" : share > 0.4 ? "#e8af34" : "#6daa45",
                      }} />
                      {(zone.rmse ?? 0).toFixed(4)}
                    </span>
                  </td>
                  <td className="text-right text-text-muted">{zone.point_count}</td>
                  <td className="text-right text-text-muted tabular-nums">
                    {[sx, sy, sz].map((v, i) => (
                      <span key={i} style={{ color: Math.abs(v) > 0.005 ? "#e8af34" : undefined }}>
                        {v >= 0 ? "+" : ""}{v.toFixed(3)}{i < 2 ? " " : ""}
                      </span>
                    ))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {skipped.length > 0 && (
        <div className="text-text-faint mt-1">
          {t.zoneSkipped}: {skipped.map(z => `${z.zone} (${z.point_count})`).join(", ")}
        </div>
      )}
    </div>
  );
}

/** Диагностика выравнивания (ТЗ: «детали выравнивания и диагностика»).
 *
 * Показывает, на скольких точках построено выравнивание и сколько выбросов
 * отброшено. Без этого нельзя оценить, доверять ли итоговому числу. */
export function AlignmentDiagnostics({ diagnostics }: { diagnostics: Record<string, unknown> }) {
  const num = (key: string, digits = 4): string => {
    const raw = diagnostics[key];
    return typeof raw === "number" && Number.isFinite(raw) ? raw.toFixed(digits) : "—";
  };
  const int = (key: string): string => {
    const raw = diagnostics[key];
    return typeof raw === "number" ? String(raw) : "—";
  };
  const text = (key: string): string => {
    const raw = diagnostics[key];
    return typeof raw === "string" ? raw : "—";
  };

  const before = diagnostics.alignment134_residual_before_median;
  const after = diagnostics.alignment134_residual_after_median;
  const improved = typeof before === "number" && typeof after === "number" && after < before;

  return (
    <div className="font-mono text-[9px] space-y-0.5">
      <div className="text-text-muted tracking-forensic mb-1">{t.alignmentDiagTitle}</div>
      <Row label={t.diagCoverage} value={`${num("coverage134", 3)} · ${int("common_visible134")} pts`} />
      <Row label={t.diagAnchors} value={`${int("anchor134_count")} · ${text("anchor134_policy")}`} />
      <Row label={t.diagTrimmed} value={int("alignment134_trimmed_count")} />
      <Row label={t.diagResidualBefore} value={num("alignment134_residual_before_median")} />
      <Row label={t.diagResidualAfter}
        value={num("alignment134_residual_after_median")}
        color={improved ? "#6daa45" : "#e8af34"} />
      <Row label={t.diagPoseDistance} value={num("pose_distance", 3)} />
      <div className="text-text-faint pt-1 leading-snug">{t.alignmentDiagHint}</div>
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-text-muted">{label}</span>
      <span style={color ? { color } : undefined}>{value}</span>
    </div>
  );
}

/** Человекочитаемые метрики вместо сырого дампа `Object.entries`.
 *
 * Раньше выводились технические ключи с 5 знаками (`ldm106_rmse 0.04697`) без
 * подписи и без указания, много это или мало. */
const METRIC_LABELS: Record<string, { label: string; hint?: string }> = {
  ldm106_rmse: { label: "RMSE 106 точек" },
  ldm106_median: { label: "Медиана 106" },
  ldm106_p95: { label: "p95 · 106" },
  ldm106_max: { label: "Максимум 106" },
  ldm134_rmse: { label: "RMSE 134 точек" },
  ldm134_median: { label: "Медиана 134" },
  ldm134_p95: { label: "p95 · 134" },
  ldm134_max: { label: "Максимум 134" },
  alpha_id_l2: { label: "Δ identity (alpha_id)", hint: "форма без мимики" },
  alpha_exp_l2: { label: "Δ выражения (alpha_exp)", hint: "мимика, не идентичность" },
  identity_only_ldm134_rmse: { label: "RMSE 134 · identity-only" },
};

export function MetricsTable({ metrics }: { metrics: Record<string, number> }) {
  const entries = Object.entries(metrics);
  if (!entries.length) {
    return <div className="font-mono text-[9px] text-text-faint">{t.metricsEmpty}</div>;
  }
  return (
    <div className="font-mono text-[9px] space-y-0.5">
      {entries.map(([key, value]) => {
        const meta = METRIC_LABELS[key];
        return (
          <div key={key} className="flex justify-between gap-2" title={key}>
            <span className="text-text-muted truncate">
              {meta?.label ?? key}
              {meta?.hint && <span className="text-text-faint"> · {meta.hint}</span>}
            </span>
            <span className="tabular-nums">{typeof value === "number" ? value.toFixed(4) : String(value)}</span>
          </div>
        );
      })}
    </div>
  );
}
