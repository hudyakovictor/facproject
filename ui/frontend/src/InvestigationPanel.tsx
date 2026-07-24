import {useEffect,useState} from "react";
import {applyPatch,applyPatchSafe,createCapsule,loadBackups,loadInvestigation,revertPatch,rollbackBackup} from "./api";
import type {BackupManifest,Investigation,IsolatedPatchResult,RunRecord} from "./types";
const terminal=new Set(['succeeded','failed','cancelled','timed_out','interrupted']);
export function InvestigationPanel({run}:{run:RunRecord|null}){
 const [inv,setInv]=useState<Investigation|null>(null),[capsulePath,setCapsulePath]=useState(''),[diff,setDiff]=useState(''),[backups,setBackups]=useState<BackupManifest[]>([]),[error,setError]=useState(''),[message,setMessage]=useState(''),[patchResult,setPatchResult]=useState<IsolatedPatchResult|null>(null),[revertSha,setRevertSha]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{if(!run||!terminal.has(run.status)){setInv(null);return}loadInvestigation(run.id).then(setInv).catch(e=>setError(String(e)))},[run?.id,run?.status]);
 useEffect(()=>{loadBackups().then(setBackups).catch(()=>{})},[]);
 async function makeCapsule(){if(!run||busy)return;setError('');setMessage('');setBusy(true);try{const c=await createCapsule(run.id);setCapsulePath(c.path)}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function sendPatchSafe(){if(busy||!diff.trim())return;setError('');setMessage('');setPatchResult(null);setBusy(true);try{const r=await applyPatchSafe(diff);setPatchResult(r);if(r.applied){setBackups(await loadBackups());setDiff('');setMessage(`Патч применён и закоммичен: ${r.commit_sha ?? '—'}. Изолированные тесты прошли.`)}}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function sendPatchUnsafe(){if(busy||!diff.trim())return;if(typeof window!=="undefined"&&!window.confirm('Применить без изолированного прогона тестов? Будет создан только файловый backup, без коммита и без гарантии, что тесты проходят.'))return;setError('');setMessage('');setBusy(true);try{const r=await applyPatch(diff);setBackups(await loadBackups());setDiff('');setMessage(`Патч применён (без тестов), backup ${r.backup_id}, файлы: ${r.applied_files.join(', ')}`)}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function rollback(id:string){if(busy)return;setError('');setMessage('');setBusy(true);try{const r=await rollbackBackup(id);setMessage(`Откат ${id}: восстановлены ${r.restored.join(', ')}`)}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function revert(){if(busy||!revertSha.trim())return;setError('');setMessage('');setBusy(true);try{const r=await revertPatch(revertSha.trim());setMessage(`Коммит ${r.reverted_commit} отменён новым коммитом ${r.revert_commit ?? '—'}`);setRevertSha('')}catch(e){setError(String(e))}finally{setBusy(false)}}
 const spec=inv?.spec;
 return <section className="investigation-panel">
  <header><div><small>INVESTIGATION FEEDBACK LOOP</small><h2>Разбор сбоя и исправление</h2></div>{spec&&<b className={`prio-${spec.priority}`}>{spec.priority}</b>}</header>
  {!run&&<p className="investigation-empty">Запустите прогон, чтобы получить разбор причин.</p>}
  {run&&!inv&&<p className="investigation-empty">Ожидание завершения запуска…</p>}
  {run&&inv&&!spec&&<p className="investigation-empty">Прогон завершился без нарушений — разбор не требуется.</p>}
  {spec&&<div className="investigation-spec">
   <h3>{spec.title}</h3>
   <p className="human">{spec.human_summary}</p>
   <p className="technical">{spec.technical_summary}</p>
   {spec.suspected_functions.length>0&&<div className="suspects"><small>Подозреваемые функции</small><ul>{spec.suspected_functions.map(f=><li key={f.code}><code>{f.code}</code> — {f.what} ({f.status})</li>)}</ul></div>}
   <div className="acceptance"><small>Критерии готовности</small><ul>{spec.acceptance_criteria.map((a,i)=><li key={i}>{a}</li>)}</ul></div>
   <button disabled={busy} onClick={makeCapsule}>Сформировать Fix Capsule</button>
   {capsulePath&&<p className="capsule-path">Капсула сохранена: {capsulePath}</p>}
  </div>}
  <div className="patch-controls">
   <small>Применить патч разработчика (unified diff, только внутри app6)</small>
   <textarea value={diff} onChange={e=>setDiff(e.target.value)} placeholder="*** diff --git a/... ***" rows={6}/>
   <button disabled={!diff.trim()||busy} onClick={sendPatchSafe}>Применить безопасно (изолированный тест-гейт + коммит)</button>
   <button disabled={!diff.trim()||busy} className="patch-unsafe" onClick={sendPatchUnsafe}>Применить без тестов (только backup, устаревший режим)</button>
   {patchResult&&<div className={`patch-result ${patchResult.passed?'passed':'failed'}`}>
    <b>{patchResult.passed?'Изолированные тесты прошли':'Тесты не прошли — реальное дерево не тронуто'}</b>
    {patchResult.error&&<span>{patchResult.error}</span>}
    {patchResult.commit_sha&&<span>Коммит: {patchResult.commit_sha}</span>}
    {patchResult.test_output&&<pre>{patchResult.test_output}</pre>}
   </div>}
  </div>
  <div className="revert-controls">
   <small>Откатить коммит патча (git revert по SHA)</small>
   <div><input value={revertSha} onChange={e=>setRevertSha(e.target.value)} placeholder="commit sha"/><button disabled={!revertSha.trim()||busy} onClick={revert}>Откатить коммит</button></div>
  </div>
  {backups.length>0&&<div className="backup-list"><small>Бэкапы</small><ul>{backups.map(b=><li key={b.id}><span>{b.id} · {b.files.length} файлов</span><button disabled={busy} onClick={()=>rollback(b.id)}>Откатить</button></li>)}</ul></div>}
  {message&&<p className="investigation-message">{message}</p>}
  {error&&<p className="investigation-error">{error}</p>}
 </section>
}
