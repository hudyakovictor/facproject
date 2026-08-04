import { useEffect, useState } from "react";
import { fetchCalibrationHealth, fetchZoneCatalog } from "../lib/api";
import { Banner, Button, Empty, Panel } from "../components/ui";
import StructuredData from "../components/StructuredData";
export default function CalibrationPage() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [zones, setZones] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState("");
  const load = async () => {
    setErr("");
    try {
      const [h, z] = await Promise.all([
        fetchCalibrationHealth().catch(e => ({ error: String((e as Error).message || e) })),
        fetchZoneCatalog().catch(e => ({ error: String((e as Error).message || e) })),
      ]);
      setHealth(h); setZones(z);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };
  useEffect(() => { void load(); }, []);
  return (
    <div className="page">
      <div className="page-hd"><div><h1>Калибровка</h1><p>Статус calibration bundle и каталог зон.</p></div><Button onClick={() => void load()}>обновить</Button></div>
      {err && <Banner kind="bad">{err}</Banner>}
      {!health && !err && <Empty title="Загрузка…" />}
      <div className="grid-2">
        <Panel title="calibration/health"><StructuredData data={health} /></Panel>
        <Panel title="zones/catalog"><StructuredData data={zones} /></Panel>
      </div>
    </div>
  );
}
