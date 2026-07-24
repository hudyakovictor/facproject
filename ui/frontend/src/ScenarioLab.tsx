import {useEffect,useState} from 'react';import {loadScenarioPlan,loadScenarios} from './api';import type {Scenario,ScenarioPlan} from './types';
export function ScenarioLab(){
 const [items,setItems]=useState<Scenario[]>([]),[id,setId]=useState('S01_stability_frontal_A'),[pose,setPose]=useState('frontal'),[count,setCount]=useState(1),[plan,setPlan]=useState<ScenarioPlan|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{loadScenarios().then(setItems).catch(e=>setError(String(e)))},[]);
 async function build(){if(busy)return;setError('');setBusy(true);try{setPlan(await loadScenarioPlan(id,pose,count))}catch(e){setError(String(e))}finally{setBusy(false)}}
 return <section className="scenario-lab"><small>SCIENTIFIC VALIDATION CORE</small><h2>Лаборатория сценариев</h2><p>Использует существующие 21 сценарий app6. Synthetic проверяет контракты, а не forensic accuracy.</p>
 <div><select value={id} onChange={e=>setId(e.target.value)}>{items.map(x=><option key={x.id}>{x.id}</option>)}</select><select value={pose} onChange={e=>setPose(e.target.value)}><option>frontal</option><option>all</option>{[1,2,3,4,5,6,7,8,9].map(x=><option key={x}>{x}</option>)}</select><select value={count} onChange={e=>setCount(+e.target.value)}>{[1,3,7].map(x=><option key={x}>{x}</option>)}</select><button disabled={busy} onClick={build}>Собрать безопасный план</button></div>
 {error&&<p className="scenario-error">{error}</p>}
 {plan&&<article><b>{plan.case_count} тестовых случаев</b><span>{plan.poses.map(x=>x.pose_bin).join(' · ')}</span>{plan.combinations.map(x=><code key={x.combo_no}>c{x.combo_no}: A={x.roles.A} B={x.roles.B} C={x.roles.C}</code>)}</article>}
 </section>}
