import type { CatalogResponse, ProjectHealth, SourceResponse } from "./types";
async function unwrap<T>(r:Response):Promise<T>{if(!r.ok){let detail='';try{const body=await r.json();detail=(body&&typeof body.detail==='string')?body.detail:''}catch{}throw new Error(detail||`API error ${r.status}`)}return await r.json() as T}
export async function loadHealth(signal?:AbortSignal):Promise<ProjectHealth>{return unwrap<ProjectHealth>(await fetch("/api/health",{signal}))}
export async function loadCatalog(signal?:AbortSignal):Promise<CatalogResponse>{return unwrap<CatalogResponse>(await fetch("/api/catalog",{signal}))}
export async function loadSource(path:string,lineStart:number,lineEnd:number):Promise<SourceResponse>{const query=new URLSearchParams({path,line_start:String(lineStart),line_end:String(lineEnd)});return unwrap<SourceResponse>(await fetch(`/api/source?${query}`))}

import type { CanvasGraph } from "./types";
export async function loadCanvas():Promise<CanvasGraph>{return unwrap<CanvasGraph>(await fetch('/api/canvas'))}
import type { ReadinessItem } from "./types";
export async function loadReadiness():Promise<ReadinessItem[]>{return ((await unwrap<{items:ReadinessItem[]}>(await fetch('/api/readiness'))).items)}

import type { RunEvent,RunRecord,RunnerSpec } from "./types";
export async function loadRunners():Promise<RunnerSpec[]>{return (await unwrap<{runners:RunnerSpec[]}>(await fetch('/api/runners'))).runners}
export async function startRun(runner_id:string,seed=0):Promise<RunRecord>{return unwrap<RunRecord>(await fetch('/api/runs',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({runner_id,seed})}))}
export async function loadRun(id:string):Promise<RunRecord>{return unwrap<RunRecord>(await fetch(`/api/runs/${id}`))}
export async function loadRunEvents(id:string):Promise<RunEvent[]>{return (await unwrap<{events:RunEvent[]}>(await fetch(`/api/runs/${id}/events`))).events}
export async function cancelRun(id:string):Promise<void>{await unwrap<unknown>(await fetch(`/api/runs/${id}/cancel`,{method:'POST'}))}

import type { Scenario,ScenarioPlan } from './types';
export async function loadScenarios():Promise<Scenario[]>{return (await unwrap<{scenarios:Scenario[]}>(await fetch('/api/scenarios'))).scenarios}
export async function loadScenarioPlan(id:string,pose:string,combinations:number):Promise<ScenarioPlan>{const q=new URLSearchParams({scenario_id:id,pose,combinations:String(combinations)});return unwrap<ScenarioPlan>(await fetch(`/api/scenarios/plan?${q}`))}

import type { BackupManifest,Capsule,Investigation,IsolatedPatchResult,RevertResult } from './types';
export async function loadInvestigation(runId:string):Promise<Investigation>{return unwrap<Investigation>(await fetch(`/api/runs/${runId}/investigation`))}
export async function createCapsule(runId:string):Promise<Capsule>{return unwrap<Capsule>(await fetch('/api/capsules',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({run_id:runId})}))}
export async function loadBackups():Promise<BackupManifest[]>{return (await unwrap<{backups:BackupManifest[]}>(await fetch('/api/backups'))).backups}
export async function applyPatch(diff:string):Promise<{backup_id:string;applied_files:string[]}>{return unwrap<{backup_id:string;applied_files:string[]}>(await fetch('/api/patches/apply',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({diff})}))}
export async function applyPatchSafe(diff:string,commitMessage?:string):Promise<IsolatedPatchResult>{return unwrap<IsolatedPatchResult>(await fetch('/api/patches/apply-safe',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({diff,commit_message:commitMessage})}))}
export async function revertPatch(commitSha:string):Promise<RevertResult>{return unwrap<RevertResult>(await fetch(`/api/patches/${commitSha}/revert`,{method:'POST'}))}
export async function rollbackBackup(backupId:string):Promise<{backup_id:string;restored:string[]}>{return unwrap<{backup_id:string;restored:string[]}>(await fetch(`/api/backups/${backupId}/rollback`,{method:'POST'}))}

import type { TimelinePayload,TimelineState } from "./types";
export async function loadRunTimeline(runId:string):Promise<TimelinePayload>{return unwrap<TimelinePayload>(await fetch(`/api/runs/${runId}/timeline`))}
export async function loadRunTimelineState(runId:string,atSeq:number):Promise<TimelineState>{const q=new URLSearchParams({at_seq:String(atSeq)});return unwrap<TimelineState>(await fetch(`/api/runs/${runId}/timeline/state?${q}`))}

import type { CalibrationRunGroup,RunHashesInput } from "./types";
export async function listCalibrationRunGroups():Promise<CalibrationRunGroup[]>{return (await unwrap<{run_groups:CalibrationRunGroup[]}>(await fetch('/api/calibration/run-groups'))).run_groups}
export async function createCalibrationRunGroup(id?:string):Promise<CalibrationRunGroup>{return unwrap<CalibrationRunGroup>(await fetch('/api/calibration/run-groups',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id})}))}
export async function getCalibrationRunGroup(groupId:string):Promise<CalibrationRunGroup>{return unwrap<CalibrationRunGroup>(await fetch(`/api/calibration/run-groups/${groupId}`))}
export async function registerCalibrationMember(groupId:string,role:string,runId:string,hashes:RunHashesInput):Promise<CalibrationRunGroup>{return unwrap<CalibrationRunGroup>(await fetch(`/api/calibration/run-groups/${groupId}/members`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({role,run_id:runId,...hashes})}))}
export async function attachCalibrationTable(groupId:string,path?:string):Promise<CalibrationRunGroup>{return unwrap<CalibrationRunGroup>(await fetch(`/api/calibration/run-groups/${groupId}/table`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({path})}))}
export async function approveCalibrationRunGroup(groupId:string,approvedBy:string):Promise<CalibrationRunGroup>{return unwrap<CalibrationRunGroup>(await fetch(`/api/calibration/run-groups/${groupId}/approve`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({approved_by:approvedBy})}))}
export async function rejectCalibrationRunGroup(groupId:string,reason:string):Promise<CalibrationRunGroup>{return unwrap<CalibrationRunGroup>(await fetch(`/api/calibration/run-groups/${groupId}/reject`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({reason})}))}
export async function verifyCalibrationRunGroup(groupId:string):Promise<{group_id:string;bundle_intact:boolean}>{return unwrap<{group_id:string;bundle_intact:boolean}>(await fetch(`/api/calibration/run-groups/${groupId}/verify`))}

import type { PosePolicy } from "./types";
export async function loadPosePolicy():Promise<PosePolicy>{return unwrap<PosePolicy>(await fetch('/api/calibration/pose-policy'))}
