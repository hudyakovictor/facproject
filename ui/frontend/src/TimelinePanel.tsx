import {useEffect,useRef,useState} from "react";
import {loadRunTimeline,loadRunTimelineState} from "./api";
import type {RunRecord,TimelinePayload,TimelineState} from "./types";
export function TimelinePanel({run}:{run:RunRecord|null}){
 const [runId,setRunId]=useState(''),[timeline,setTimeline]=useState<TimelinePayload|null>(null),[state,setState]=useState<TimelineState|null>(null),[atSeq,setAtSeq]=useState(0),[error,setError]=useState(''),[busy,setBusy]=useState(false),[scale,setScale]=useState(18),[selectedSpan,setSelectedSpan]=useState<number|null>(null);
 const scrubTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
 useEffect(()=>{if(run&&!runId)setRunId(run.id)},[run?.id]);
 const maxSeq=timeline?Math.max(0,...timeline.spans.map(s=>s.seq)):0;
 async function load(){if(busy||!runId.trim())return;setError('');setBusy(true);try{const t=await loadRunTimeline(runId.trim());setTimeline(t);const maxS=Math.max(0,...t.spans.map(s=>s.seq));setAtSeq(maxS);setSelectedSpan(null);setState(await loadRunTimelineState(runId.trim(),maxS))}catch(e){setError(String(e))}finally{setBusy(false)}}
 function scrub(seq:number){setAtSeq(seq);if(!runId.trim())return;if(scrubTimer.current)clearTimeout(scrubTimer.current);scrubTimer.current=setTimeout(()=>{loadRunTimelineState(runId.trim(),seq).then(setState).catch(e=>setError(String(e)))},150)}
 function selectSpan(seq:number){setSelectedSpan(seq);scrub(seq)}
 function onWheelZoom(e:React.WheelEvent){e.preventDefault();setScale(z=>Math.min(60,Math.max(3,z-e.deltaY*0.02)))}
 return <section className="timeline-panel">
  <header><div><small>REPLAY RECONSTRUCTION</small><h2>Таймлайн запуска</h2></div></header>
  <p className="timeline-note">app6 работает в режиме read-only observation без пофункциональной инструментации: тут восстанавливается только последовательность фактически напечатанных строк лога (тесты, прогресс stage1). Начало каждого отрезка — оценка (граница с предыдущим отрезком той же дорожки), а не измеренное время; это явно помечено флагом «оценка начала».</p>
  <div className="timeline-controls"><input value={runId} onChange={e=>setRunId(e.target.value)} placeholder="run id"/><button disabled={busy||!runId.trim()} onClick={load}>Загрузить таймлайн</button></div>
  {error&&<p className="timeline-error">{error}</p>}
  {timeline&&<>
   <div className="timeline-scrubber"><input type="range" min={0} max={maxSeq} value={atSeq} onChange={e=>scrub(+e.target.value)}/><span>seq {atSeq} / {maxSeq}</span></div>
   <div className="timeline-zoom-toolbar"><span>Масштаб дорожек</span><button onClick={()=>setScale(z=>Math.max(3,z-4))} aria-label="уменьшить масштаб">−</button><input type="range" min={3} max={60} value={scale} onChange={e=>setScale(+e.target.value)} aria-label="Масштаб таймлайна"/><button onClick={()=>setScale(z=>Math.min(60,z+4))} aria-label="увеличить масштаб">+</button><button onClick={()=>setScale(18)}>По размеру</button><small>колесо мыши над дорожками также масштабирует</small></div>
   <div className="timeline-tracks" onWheel={onWheelZoom}>{timeline.tracks.map(track=>{
    const spans=timeline.spans.filter(s=>s.track_id===track.id);
    return <div className="timeline-track" key={track.id}><h3>{track.title}</h3>
     <div className="timeline-strip-wrap"><div className="timeline-strip" style={{width:`${(maxSeq+2)*scale}px`}}>{spans.map(s=>{
      const done=state?state.completed.some(c=>c.seq===s.seq):s.seq<=atSeq;
      return <button key={s.seq} className={`strip-span status-${s.status} ${done?'done':'pending'} ${selectedSpan===s.seq?'active':''}`} style={{left:`${s.seq*scale}px`,width:`${Math.max(scale*.85,5)}px`}} onClick={()=>selectSpan(s.seq)} title={`#${s.seq} ${s.label}`}/>;
     })}</div></div>
     <ul>{spans.map(s=>{
     const done=state?state.completed.some(c=>c.seq===s.seq):s.seq<=atSeq;
     return <li key={s.seq} className={`${done?'done':'pending'} ${selectedSpan===s.seq?'active':''}`} onClick={()=>selectSpan(s.seq)}><code>#{s.seq}</code><b className={`status-${s.status}`}>{s.status}</b><span>{s.label}</span>{s.start_is_estimated&&<small className="estimate-flag" title="Начало отрезка оценено, а не измерено">оценка начала</small>}</li>;
    })}</ul></div>;
   })}</div>
   {selectedSpan!=null&&(()=>{const s=timeline.spans.find(x=>x.seq===selectedSpan);if(!s)return null;const trackTitle=timeline.tracks.find(t=>t.id===s.track_id)?.title??s.track_id;return <aside className="span-detail"><b>#{s.seq}</b><span className={`status-${s.status}`}>{s.status}</span><p>{s.label}</p><small>дорожка: {trackTitle}</small>{s.start_is_estimated&&<small className="estimate-flag">начало отрезка — оценка, не измерение</small>}</aside>})()}
  </>}
  {!timeline&&!error&&<p className="timeline-empty">Укажите id запуска (из панели «Запуски») и загрузите таймлайн.</p>}
 </section>;
}
