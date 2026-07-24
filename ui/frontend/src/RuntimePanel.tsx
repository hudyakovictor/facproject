import {useEffect,useState} from "react";
import {cancelRun,loadRun,loadRunEvents,loadRunners,startRun} from "./api";
import type {RunEvent,RunRecord,RunnerSpec} from "./types";
const terminal=new Set(['succeeded','failed','cancelled','timed_out','interrupted']);
export function RuntimePanel({onRunChange}:{onRunChange?:(run:RunRecord|null)=>void}={}){
 const [runners,setRunners]=useState<RunnerSpec[]>([]),[run,setRun]=useState<RunRecord|null>(null),[events,setEvents]=useState<RunEvent[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{loadRunners().then(setRunners).catch(e=>setError(String(e)))},[]);
 useEffect(()=>{onRunChange?.(run)},[run]);
 useEffect(()=>{if(!run||terminal.has(run.status))return;let inFlight=false;const id=setInterval(async()=>{if(inFlight)return;inFlight=true;try{const next=await loadRun(run.id);setRun(next);setEvents(await loadRunEvents(run.id))}catch(e){setError(String(e))}finally{inFlight=false}},400);return()=>clearInterval(id)},[run?.id,run?.status]);
 async function launch(id:string){if(busy)return;setError('');setEvents([]);setBusy(true);try{setRun(await startRun(id,0))}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function cancel(){if(!run||busy)return;setError('');setBusy(true);try{await cancelRun(run.id);setRun(await loadRun(run.id))}catch(e){setError(String(e))}finally{setBusy(false)}}
 return <section className="runtime-panel"><header><div><small>CRITICAL EXECUTION CORE</small><h2>Безопасные запуски</h2></div>{run&&<b className={`run-${run.status}`}>{run.status}</b>}</header>
 <div className="runner-buttons">{runners.map(r=><button key={r.id} disabled={busy||(!!run&&!terminal.has(run.status))} onClick={()=>launch(r.id)}><b>{r.title}</b><small>{r.id} · timeout {r.timeout}s</small></button>)}
 {run&&!terminal.has(run.status)&&<button className="cancel" disabled={busy} onClick={cancel}>Отменить и остановить процесс</button>}</div>
 {run&&<div className="run-meta"><span>Run: {run.id}</span><span>Code: {run.code_hash.slice(0,12)}</span><span>Seed: {run.seed}</span></div>}
 {error&&<p className="runtime-error">{error}</p>}
 <pre className="runtime-log">{events.filter(e=>e.type==='log').slice(-80).map(e=>String(e.payload.text??'')).join('\n')||'Логи появятся после запуска.'}</pre>
 </section>}
