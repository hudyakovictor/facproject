import {useEffect,useState} from "react";
import {approveCalibrationRunGroup,attachCalibrationTable,createCalibrationRunGroup,getCalibrationRunGroup,listCalibrationRunGroups,loadPosePolicy,registerCalibrationMember,rejectCalibrationRunGroup,verifyCalibrationRunGroup} from "./api";
import type {CalibrationRunGroup,PosePolicy} from "./types";
const ROLES=["main_extraction","calibration_extraction","calibration_build","main_analysis"];
export function CalibrationPanel(){
 const [groups,setGroups]=useState<CalibrationRunGroup[]>([]),[selected,setSelected]=useState<CalibrationRunGroup|null>(null),[newId,setNewId]=useState(''),[error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 const [role,setRole]=useState(ROLES[0]),[memberRunId,setMemberRunId]=useState(''),[datasetHash,setDatasetHash]=useState(''),[codeHash,setCodeHash]=useState(''),[modelHash,setModelHash]=useState(''),[configHash,setConfigHash]=useState('');
 const [tablePath,setTablePath]=useState(''),[approvedBy,setApprovedBy]=useState(''),[rejectReason,setRejectReason]=useState('');
 const [posePolicy,setPosePolicy]=useState<PosePolicy|null>(null),[poseError,setPoseError]=useState('');
 function refreshList(){listCalibrationRunGroups().then(setGroups).catch(e=>setError(String(e)))}
 useEffect(()=>{refreshList()},[]);
 useEffect(()=>{loadPosePolicy().then(setPosePolicy).catch(e=>setPoseError(String(e)))},[]);
 async function create(){if(busy)return;setError('');setMessage('');setBusy(true);try{const g=await createCalibrationRunGroup(newId.trim()||undefined);setNewId('');refreshList();setSelected(g)}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function open(id:string){if(busy)return;setError('');setBusy(true);try{setSelected(await getCalibrationRunGroup(id))}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function registerMember(){if(busy||!selected||!memberRunId.trim())return;setError('');setMessage('');setBusy(true);try{const g=await registerCalibrationMember(selected.id,role,memberRunId.trim(),{dataset_hash:datasetHash,code_hash:codeHash,model_hash:modelHash,config_hash:configHash});setSelected(g);refreshList();setMemberRunId('')}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function attachTable(){if(busy||!selected)return;setError('');setMessage('');setBusy(true);try{const g=await attachCalibrationTable(selected.id,tablePath.trim()||undefined);setSelected(g);setMessage('Верифицированная таблица привязана')}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function approve(){if(busy||!selected||!approvedBy.trim())return;setError('');setMessage('');setBusy(true);try{const g=await approveCalibrationRunGroup(selected.id,approvedBy.trim());setSelected(g);refreshList()}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function reject(){if(busy||!selected||!rejectReason.trim())return;setError('');setMessage('');setBusy(true);try{const g=await rejectCalibrationRunGroup(selected.id,rejectReason.trim());setSelected(g);refreshList()}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function verify(){if(busy||!selected)return;setError('');setMessage('');setBusy(true);try{const r=await verifyCalibrationRunGroup(selected.id);setMessage(r.bundle_intact?'Связка хешей подтверждена: bundle целостен':'внимание: bundle нарушен, хеши расходятся')}catch(e){setError(String(e))}finally{setBusy(false)}}
 return <section className="calibration-panel">
  <header><div><small>RUN GROUP INTEGRITY CORE</small><h2>Калибровочные группы запусков</h2></div></header>
  <p className="calibration-note">Группа становится candidate только после регистрации всех 4 ролей с одинаковыми dataset/code/model/config хешами; любое рассогласование отклоняется fail-closed.</p>
  <div className="calibration-create"><input value={newId} onChange={e=>setNewId(e.target.value)} placeholder="id новой группы (необязательно)"/><button disabled={busy} onClick={create}>Создать группу</button></div>
  <div className="calibration-list">{groups.length===0&&<p className="calibration-empty">Групп пока нет.</p>}<ul>{groups.map(g=><li key={g.id} className={selected?.id===g.id?'active':''}><button disabled={busy} onClick={()=>open(g.id)}><b>{g.id}</b><span className={`status-${g.status}`}>{g.status}</span></button></li>)}</ul></div>
  {error&&<p className="calibration-error">{error}</p>}
  {message&&<p className="calibration-message">{message}</p>}
  {selected&&<div className="calibration-detail">
   <h3>{selected.id}</h3>
   <p>Статус: <b className={`status-${selected.status}`}>{selected.status}</b>{selected.bundle_hash&&<code>bundle {selected.bundle_hash.slice(0,12)}</code>}</p>
   {selected.missing_roles.length>0&&<p className="missing-roles">Не зарегистрированы роли: {selected.missing_roles.join(', ')}</p>}
   <ul className="member-list">{ROLES.map(r=>{const m=selected.members[r];return <li key={r}><b>{r}</b>{m?<span>run {m.run_id} · {m.registered_at}</span>:<span className="absent">не зарегистрирована</span>}</li>;})}</ul>
   {selected.status!=='approved'&&selected.status!=='rejected'&&<div className="member-form">
    <small>Зарегистрировать роль</small>
    <select value={role} onChange={e=>setRole(e.target.value)}>{ROLES.map(r=><option key={r}>{r}</option>)}</select>
    <input value={memberRunId} onChange={e=>setMemberRunId(e.target.value)} placeholder="run id"/>
    <input value={datasetHash} onChange={e=>setDatasetHash(e.target.value)} placeholder="dataset_hash"/>
    <input value={codeHash} onChange={e=>setCodeHash(e.target.value)} placeholder="code_hash"/>
    <input value={modelHash} onChange={e=>setModelHash(e.target.value)} placeholder="model_hash"/>
    <input value={configHash} onChange={e=>setConfigHash(e.target.value)} placeholder="config_hash"/>
    <button disabled={busy||!memberRunId.trim()||!datasetHash.trim()||!codeHash.trim()||!modelHash.trim()||!configHash.trim()} onClick={registerMember} title="все 4 хеша обязательны — пустые значения тривиально «совпадают» и ломают защиту fail-closed">Добавить участника</button>
    <p className="hash-warning">Все 4 хеша обязательны. При несовпадении с уже зарегистрированными ролями backend откажет запись (fail-closed).</p>
   </div>}
   {selected.trusted_table?<p className="table-attached">Доверенная таблица уже привязана.</p>:selected.status!=='approved'&&selected.status!=='rejected'&&<div className="table-form">
    <small>Привязать доверенную таблицу (только pair-привязки/углы, координаты отвергаются)</small>
    <input value={tablePath} onChange={e=>setTablePath(e.target.value)} placeholder="путь к CSV (пусто = автопоиск в calibration_root)"/>
    <button disabled={busy} onClick={attachTable}>Привязать таблицу</button>
   </div>}
   {selected.status!=='approved'&&selected.status!=='rejected'&&<div className="decision-form">
    <div><input value={approvedBy} onChange={e=>setApprovedBy(e.target.value)} placeholder="ваше имя (approved_by)"/><button disabled={busy||selected.status!=='candidate'||!approvedBy.trim()} onClick={approve}>Одобрить</button></div>
    <div><input value={rejectReason} onChange={e=>setRejectReason(e.target.value)} placeholder="причина отказа"/><button disabled={busy||!rejectReason.trim()} onClick={reject}>Отклонить</button></div>
    {selected.status!=='candidate'&&<p className="approve-hint">Одобрить можно только группу в статусе candidate (все 4 роли зарегистрированы).</p>}
   </div>}
   {selected.rejected_reason&&<p className="rejected-reason">Причина отказа: {selected.rejected_reason}</p>}
   {selected.status==='approved'&&<button disabled={busy} onClick={verify}>Проверить целостность bundle</button>}
  </div>}
  <div className="pose-lab">
   <h3>Pose Lab (черновая версия)</h3>
   <p className="pose-lab-note">Девять канонических pose bins — реальная статическая политика из <code>app6/stage1/config.py:POSE_BINS</code> (та же, что использует <code>geometry.classify_pose()</code>). Границы pitch/roll, residual distance, pair eligibility и coverage здесь не показаны: они не заданы этой статической политикой и требуют настоящего calibration run — придумывать их здесь нельзя.</p>
   {poseError&&<p className="calibration-error">{poseError}</p>}
   {posePolicy&&<table className="pose-bin-table"><thead><tr><th>Bin (LP–RP)</th><th>Название</th><th>Yaw min</th><th>Yaw max</th><th>Canonical yaw</th></tr></thead><tbody>{posePolicy.bins.map(b=><tr key={b.name}><td><b>{b.code}</b></td><td>{b.name}</td><td>{b.yaw_min.toFixed(1)}°</td><td>{b.yaw_max.toFixed(1)}°</td><td>{b.canonical_yaw.toFixed(1)}°</td></tr>)}</tbody></table>}
  </div>
 </section>;
}
