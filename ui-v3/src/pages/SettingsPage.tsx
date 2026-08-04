import { useEffect,useState } from "react";
import { fetchSettings,resetSettings,saveSettings } from "../lib/api";
import { Banner,Button,Input,Panel,Select } from "../components/ui";
export default function SettingsPage({pushToast}:{pushToast:(k:"ok"|"warn"|"bad"|"info",t:string)=>void}){
 const [settings,setSettings]=useState<Record<string,any>|null>(null);const [err,setErr]=useState("");
 const load=async()=>{try{setSettings(await fetchSettings());setErr("")}catch(e){setErr(String(e))}};useEffect(()=>{void load()},[]);
 const setThreshold=(k:string,v:number)=>setSettings(s=>s?{...s,thresholds:{...(s.thresholds||{}),[k]:v}}:s);
 const save=async()=>{if(!settings)return;try{setSettings(await saveSettings(settings));pushToast("ok","Настройки сохранены")}catch(e){pushToast("bad",String(e))}};
 if(!settings)return <div className="page">{err?<Banner kind="bad">{err}</Banner>:"Загрузка…"}</div>;const t=settings.thresholds||{};
 return <div className="page"><div className="page-hd"><div><h1>Настройки</h1><p>Валидируемые настройки; diagnostic thresholds не являются evidence.</p></div><div className="row"><Button onClick={()=>void resetSettings().then(setSettings)}>reset</Button><Button variant="primary" onClick={()=>void save()}>сохранить</Button></div></div>
 <Banner kind={settings.threshold_mode==="calibrated"?"ok":"warn"} title="Режим порогов">{String(settings.threshold_mode)}</Banner>
 <Panel title="Applicability"><div className="grid-2"><label>Режим<Select value={settings.threshold_mode} onChange={e=>setSettings({...settings,threshold_mode:e.target.value})}><option value="diagnostic_only">diagnostic only</option><option value="calibrated">calibrated</option></Select></label><label>Quality min<Input type="number" min={0} max={1} step={.01} value={t.quality_min??.35} onChange={e=>setThreshold("quality_min",Number(e.target.value))}/></label><label>Confidence min<Input type="number" min={0} max={1} step={.01} value={t.confidence_min??.5} onChange={e=>setThreshold("confidence_min",Number(e.target.value))}/></label></div></Panel></div>
}
