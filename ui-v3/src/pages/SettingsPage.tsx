import { useEffect, useState } from "react";
import { fetchSettings, resetSettings, saveSettings } from "../lib/api";
import { Banner, Button, Panel, Textarea } from "../components/ui";
export default function SettingsPage({ pushToast }: { pushToast: (k: "ok"|"warn"|"bad"|"info", t: string) => void }) {
  const [text, setText] = useState("{}\n");
  const [err, setErr] = useState("");
  const load = async () => {
    try { setText(JSON.stringify(await fetchSettings(), null, 2)); setErr(""); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };
  useEffect(() => { void load(); }, []);
  const save = async () => {
    try { const s = await saveSettings(JSON.parse(text)); setText(JSON.stringify(s, null, 2)); pushToast("ok", "Настройки сохранены"); }
    catch (e) { pushToast("bad", e instanceof Error ? e.message : String(e)); }
  };
  const reset = async () => {
    try { setText(JSON.stringify(await resetSettings(), null, 2)); pushToast("warn", "Настройки сброшены"); }
    catch (e) { pushToast("bad", e instanceof Error ? e.message : String(e)); }
  };
  return (
    <div className="page">
      <div className="page-hd">
        <div><h1>Настройки</h1><p>Пороги backend. JSON редактор.</p></div>
        <div className="row"><Button onClick={() => void load()}>перечитать</Button><Button onClick={() => void reset()}>reset</Button><Button variant="primary" onClick={() => void save()}>сохранить</Button></div>
      </div>
      {err && <Banner kind="warn" title="settings API">{err}</Banner>}
      <Panel title="settings JSON"><Textarea value={text} onChange={e => setText(e.target.value)} style={{ minHeight: 420 }} /></Panel>
    </div>
  );
}
