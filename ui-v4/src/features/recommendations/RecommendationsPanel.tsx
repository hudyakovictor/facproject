/**
 * Recommendations panel (Iteration 13).
 *
 * Slide-out panel with advisory suggestions aggregated from the current
 * workstation state. Every card has an action button that navigates to the
 * relevant module (no data is changed without the operator's explicit click).
 * The gear button opens per-type settings (enable / limit / max total) —
 * recommendations can be tuned or switched off, as requested.
 */
import { useEffect, useMemo, useState } from "react";
import {
  recommendations, recommendationSettings, saveRecommendationSettings,
  type Recommendation, type Recommendations, type RecSettings,
} from "../../shared/api";
import { logError } from "../../shared/logger";

interface Props {
  open: boolean;
  onClose: () => void;
  onNavigate: (kind: string, extra?: Record<string, unknown>) => void;
}

const TYPE_LABELS: Record<string, string> = {
  stage1_integrity: "Целостность Stage 1",
  no_stage2: "Stage 2 не запускался",
  stale_profile_run: "Профиль изменён",
  run_invalid: "Невалидный прогон",
  report_missing: "Нет отчёта",
  public_report: "Нет public-отчёта",
  dense_zones: "Зоны перекопирования",
  coverage_gap: "Пропуски покрытия",
  calibration_gap: "Слабая калибровка",
  exceedance_cluster: "Тревожные пары",
  return_events: "Возвраты состояния",
  duplicate_heavy: "Много дубликатов",
  findings_unviewed: "Находки Stage 2",
  log_errors: "Ошибки в журнале",
};

export default function RecommendationsPanel({ open, onClose, onNavigate }: Props) {
  const [data, setData] = useState<Recommendations | null>(null);
  const [settings, setSettings] = useState<RecSettings | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    setBusy(true);
    try {
      const [recs, recSettings] = await Promise.all([recommendations(), recommendationSettings()]);
      setData(recs);
      setSettings(recSettings);
    } catch (error) {
      logError("recommendations", "не удалось загрузить рекомендации", error);
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (open) void refresh();
  }, [open]);

  const recs = useMemo(() => data?.recommendations ?? [], [data]);

  const toggleType = (key: string, field: "enabled" | "limit", value: boolean | number) => {
    if (!settings) return;
    const next: RecSettings = {
      ...settings,
      types: {
        ...settings.types,
        [key]: { ...settings.types[key], [field]: value },
      },
    };
    setSettings(next);
  };

  const saveSettings = async () => {
    if (!settings) return;
    setBusy(true);
    try {
      const saved = await saveRecommendationSettings(settings);
      setSettings(saved);
      setSettingsOpen(false);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="rec-backdrop" onClick={onClose}>
      <aside className="rec-panel" onClick={event => event.stopPropagation()}>
        <header className="rec-panel-head">
          <div>
            <small>ITERATION 13 · ADVISOR</small>
            <b>Рекомендации</b>
            <span>{data?.generated_at ? `обновлено ${new Date(data.generated_at).toLocaleTimeString("ru-RU")}` : "советы системы · всё можно подкрутить"}</span>
          </div>
          <div className="rec-head-actions">
            <button className={settingsOpen ? "active" : ""} onClick={() => setSettingsOpen(value => !value)} title="Настройки рекомендаций">⚙</button>
            <button className="rec-close" onClick={onClose} title="Закрыть">×</button>
          </div>
        </header>

        {settingsOpen ? (
          <div className="rec-settings">
            <div className="rec-settings-total">
              <label><span>Максимум рекомендаций</span>
                <input type="number" min={1} max={50} value={settings?.max_total ?? 12}
                  onChange={event => setSettings(current => current ? { ...current, max_total: Number(event.target.value) } : current)} />
              </label>
            </div>
            <div className="rec-settings-list">
              {settings && Object.entries(settings.types).map(([key, cfg]) => (
                <article key={key}>
                  <label className="rec-toggle">
                    <input type="checkbox" checked={cfg.enabled} onChange={event => toggleType(key, "enabled", event.target.checked)} />
                    <b>{TYPE_LABELS[key] || key}</b>
                  </label>
                  <label className="rec-limit">
                    <span>лимит</span>
                    <input type="number" min={0} max={10} value={cfg.limit}
                      onChange={event => toggleType(key, "limit", Number(event.target.value))} />
                  </label>
                </article>
              ))}
            </div>
            {message && <div className="rec-message">{message}</div>}
            <footer className="rec-settings-foot">
              <button className="ghost" onClick={() => { setSettingsOpen(false); void refresh(); }}>Отмена</button>
              <button className="primary" disabled={busy} onClick={() => void saveSettings()}>Сохранить настройки</button>
            </footer>
          </div>
        ) : (
          <>
            {message && <div className="rec-message">{message}</div>}
            <div className="rec-list">
              {busy && recs.length === 0 && <div className="rec-empty">Сбор рекомендаций…</div>}
              {!busy && recs.length === 0 && <div className="rec-empty">Рекомендаций нет — система в порядке ✓</div>}
              {recs.map((rec: Recommendation, index) => (
                <article key={`${rec.type}-${index}`} className={`rec-card prio-${rec.priority >= 90 ? "high" : rec.priority >= 78 ? "mid" : "low"}`}>
                  <div className="rec-card-head">
                    <i>{rec.priority}</i>
                    <b>{rec.title}</b>
                  </div>
                  <p>{rec.body}</p>
                  {rec.action && (
                    <button className="rec-action" onClick={() => onNavigate(rec.action!.kind, rec.action as unknown as Record<string, unknown>)}>
                      Перейти →
                    </button>
                  )}
                </article>
              ))}
            </div>
            <footer className="rec-panel-foot">
              <button className="ghost" disabled={busy} onClick={() => void refresh()}>{busy ? "Сбор…" : "⟳ Обновить"}</button>
              <button className="ghost" onClick={() => setSettingsOpen(true)}>⚙ Настроить типы</button>
              <span className="rec-hint">{recs.length}/{data?.max_total ?? 12} · советы не меняют данные</span>
            </footer>
          </>
        )}
      </aside>
    </div>
  );
}
