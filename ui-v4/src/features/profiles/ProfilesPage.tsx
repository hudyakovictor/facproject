import { useEffect, useMemo, useState } from "react";
import {
  applyCuration,
  cloneProfile,
  createProfile,
  diffProfiles,
  exportProfile,
  fetchProfileStatuses,
  freezeProfile,
  getProfile,
  importProfile,
  listProfiles,
  lockProfile,
  renameProfile,
  restoreAutomatic,
  type ProfileDetail,
  type ProfileStatusMap,
  type ProfileSummary,
} from "../../shared/api";

const STATUSES = [
  "primary",
  "diagnostic_only",
  "automatic_exclusion",
  "manual_exclusion",
  "manual_include",
  "manual_review",
  "invalid",
] as const;

const REASONS = [
  "quality_gate",
  "pose_outlier",
  "expression",
  "date_conflict",
  "near_duplicate",
  "missing_artifact",
  "manual_reviewer",
  "restored_automatic",
  "bulk_action",
  "other",
] as const;

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [statuses, setStatuses] = useState<ProfileStatusMap | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [status, setStatus] = useState<string>("manual_exclusion");
  const [reason, setReason] = useState<string>("manual_reviewer");
  const [comment, setComment] = useState("");
  const [name, setName] = useState("Selection profile");
  const [description, setDescription] = useState("");
  const [diffOther, setDiffOther] = useState("");
  const [diffResult, setDiffResult] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [filterStatus, setFilterStatus] = useState("all");
  const [importText, setImportText] = useState("");

  const refreshList = async () => {
    const rows = await listProfiles();
    setProfiles(rows);
    if (!activeId && rows[0]) setActiveId(rows[0].id);
  };

  const refreshActive = async (id = activeId) => {
    if (!id) { setDetail(null); setStatuses(null); return; }
    const [profile, statusMap] = await Promise.all([getProfile(id), fetchProfileStatuses(id)]);
    setDetail(profile);
    setStatuses(statusMap);
    setSelected([]);
  };

  useEffect(() => { void refreshList().catch(e => setMessage(e instanceof Error ? e.message : String(e))); }, []);
  useEffect(() => {
    if (!activeId) return;
    void refreshActive(activeId).catch(e => setMessage(e instanceof Error ? e.message : String(e)));
  }, [activeId]);

  const rows = useMemo(() => {
    const photos = Object.values(statuses?.photos || {});
    if (filterStatus === "all") return photos;
    return photos.filter(item => item.status === filterStatus);
  }, [statuses, filterStatus]);

  const runWithProfile = () => {
    if (!activeId) return;
    window.dispatchEvent(new CustomEvent("deeputin:navigate", { detail: { view: "runs" } }));
    window.setTimeout(() => window.dispatchEvent(new CustomEvent("deeputin:open-run-form", { detail: { profile_id: activeId } })), 60);
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setMessage("");
    try { await fn(); }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  };

  const toggle = (id: string) => {
    setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  };

  const selectVisible = () => setSelected(rows.map(item => item.photo_id));

  return <div className="page-shell profiles-page">
    <div className="page-heading">
      <div>
        <small>ITERATION 04 · CURATION</small>
        <h1>Analysis Profiles</h1>
        <p>Ручная курация, journal overrides и immutable selection_manifest. Stage 1 не изменяется.</p>
      </div>
      <button className="ghost" disabled={busy} onClick={() => void run(async () => { await refreshList(); await refreshActive(); })}>↻ Обновить</button>
    </div>
    {message && <div className="notice wide">{message}</div>}

    <div className="profiles-layout">
      <section className="card profiles-list-card">
        <header><span>01</span><div><b>Профили</b><small>save / clone / lock / export</small></div></header>
        <div className="profile-create">
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Имя профиля" />
          <input value={description} onChange={e => setDescription(e.target.value)} placeholder="Описание" />
          <button className="primary" disabled={busy || !name.trim()} onClick={() => void run(async () => {
            const created = await createProfile({ name: name.trim(), description });
            await refreshList();
            setActiveId(created.id);
            setMessage(`Создан профиль ${created.id}`);
          })}>＋ Создать</button>
        </div>
        <div className="profile-rows">
          {profiles.map(profile => (
            <button key={profile.id} className={profile.id === activeId ? "active" : ""} onClick={() => setActiveId(profile.id)}>
              <b>{profile.name}</b>
              <span>{profile.id}{profile.locked ? " · LOCKED" : ""}</span>
              <em>{profile.has_manifest ? "manifest" : "draft"}</em>
            </button>
          ))}
          {profiles.length === 0 && <div className="empty-row">Профилей пока нет</div>}
        </div>
      </section>

      <section className="card profile-detail-card">
        <header><span>02</span><div><b>{detail?.config?.name || "Профиль не выбран"}</b><small>{activeId || "—"}{detail?.locked ? " · locked" : ""}</small></div></header>
        {detail && <>
          <div className="status-counts">
            {STATUSES.map(key => <div key={key}><strong>{detail.photo_status_counts?.[key] ?? statuses?.status_counts?.[key] ?? 0}</strong><span>{key}</span></div>)}
          </div>
          <div className="profile-actions">
            <button disabled={busy || detail.locked} onClick={() => void run(async () => {
              const next = prompt("Новое имя", detail.config?.name || activeId);
              if (!next) return;
              await renameProfile(activeId, { name: next, description: detail.config?.description });
              await refreshList(); await refreshActive();
            })}>Переименовать</button>
            <button disabled={busy} onClick={() => void run(async () => {
              const cloned = await cloneProfile(activeId, `${detail.config?.name || activeId} copy`);
              await refreshList(); setActiveId(cloned.id);
            })}>Клонировать</button>
            <button disabled={busy} onClick={() => void run(async () => {
              await lockProfile(activeId, !detail.locked);
              await refreshList(); await refreshActive();
            })}>{detail.locked ? "Разблокировать" : "Заблокировать"}</button>
            <button className="primary run-profile-btn" disabled={busy || detail.locked} onClick={runWithProfile} title="Запустить Stage 2 с этой выборкой (новый run, откат возможен)">▶ Stage 2 с этим профилем</button>
            <button className="primary" disabled={busy || detail.locked} onClick={() => void run(async () => {
              const frozen = await freezeProfile(activeId);
              setMessage(`selection_manifest frozen · ${frozen.path}`);
              await refreshList(); await refreshActive();
            })}>Freeze manifest</button>
            <button disabled={busy} onClick={() => void run(async () => {
              const payload = await exportProfile(activeId);
              await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
              setMessage("Export JSON скопирован в буфер");
            })}>Export</button>
          </div>

          <div className="curation-toolbar">
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
              <option value="all">Все статусы</option>
              {STATUSES.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
            <select value={status} onChange={e => setStatus(e.target.value)}>{STATUSES.map(item => <option key={item} value={item}>{item}</option>)}</select>
            <select value={reason} onChange={e => setReason(e.target.value)}>{REASONS.map(item => <option key={item} value={item}>{item}</option>)}</select>
            <input value={comment} onChange={e => setComment(e.target.value)} placeholder="Комментарий" />
            <button disabled={busy || !selected.length || detail.locked} onClick={() => void run(async () => {
              await applyCuration(activeId, { photo_ids: selected, status, reason_code: reason, comment });
              await refreshActive(); setMessage(`Обновлено ${selected.length} фото`);
            })}>Применить статус</button>
            <button disabled={busy || !selected.length || detail.locked} onClick={() => void run(async () => {
              await restoreAutomatic(activeId, selected);
              await refreshActive(); setMessage(`Restore automatic · ${selected.length}`);
            })}>Restore auto</button>
            <button disabled={!rows.length} onClick={selectVisible}>Select visible</button>
          </div>

          <div className="curation-table">
            <div className="curation-head"><span></span><span>Photo</span><span>Status</span><span>Source</span><span>Reasons</span><span>Comment</span></div>
            {rows.map(item => (
              <label key={item.photo_id} className={`curation-row ${item.included ? "in" : "out"}`}>
                <input type="checkbox" checked={selected.includes(item.photo_id)} onChange={() => toggle(item.photo_id)} />
                <code>{item.photo_id}</code>
                <b className={`st ${item.status}`}>{item.status}</b>
                <span>{item.source}</span>
                <span>{(item.reasons || []).join(", ") || "—"}</span>
                <span>{item.comment || "—"}</span>
              </label>
            ))}
            {rows.length === 0 && <div className="empty-row">Нет фото для выбранного фильтра</div>}
          </div>

          <div className="profile-secondary">
            <article>
              <header><b>Journal</b><span>last {detail.journal_tail?.length || 0}</span></header>
              <pre>{(detail.journal_tail || []).slice().reverse().slice(0, 12).map(entry => JSON.stringify(entry)).join("\n") || "пусто"}</pre>
            </article>
            <article>
              <header><b>Diff / Import</b></header>
              <div className="diff-line">
                <select value={diffOther} onChange={e => setDiffOther(e.target.value)}>
                  <option value="">Сравнить с…</option>
                  {profiles.filter(item => item.id !== activeId).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <button disabled={!diffOther || busy} onClick={() => void run(async () => {
                  setDiffResult(await diffProfiles(activeId, diffOther));
                })}>Diff</button>
              </div>
              {diffResult && <pre>{JSON.stringify({
                filter_state_equal: diffResult.filter_state_equal,
                status_change_count: diffResult.status_change_count,
                a_counts: diffResult.a_counts,
                b_counts: diffResult.b_counts,
                sample: (diffResult.status_changes as unknown[] | undefined)?.slice?.(0, 8),
              }, null, 2)}</pre>}
              <textarea value={importText} onChange={e => setImportText(e.target.value)} placeholder="Вставьте export JSON для import" />
              <button disabled={busy || !importText.trim()} onClick={() => void run(async () => {
                const payload = JSON.parse(importText);
                const imported = await importProfile(payload);
                await refreshList(); setActiveId(imported.id); setImportText("");
                setMessage(`Импортирован ${imported.id}`);
              })}>Import JSON</button>
            </article>
          </div>
        </>}
      </section>
    </div>
  </div>;
}
