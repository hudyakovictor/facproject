export type StorageState = "ready"|"volume_missing"|"heavy_root_missing"|"wrong_volume"|"not_writable"|"low_space"|"unsafe_path"|"storage_interrupted";
export interface StorageHealth {state:StorageState;ready:boolean;mount_path:string;heavy_root:string;free_bytes:number|null;volume_identity:string|null;reasons:string[]}
export interface DatasetHealth {role:string;root:string|null;available:boolean;file_count:number;total_bytes:number;fingerprint:string|null;reasons:string[]}
export interface ProjectHealth {status:"ready"|"configuration_required";app6:{root:string;available:boolean;python_file_count:number;read_only_observation:boolean};storage:StorageHealth;datasets:Record<"main"|"calibration",DatasetHealth>;database:{path:string;schema_version:number;storage_checks:number;datasets:number}}
export interface CatalogEntry {id:string;title:string;description:string;why_important:string;failure_impact:string;technical_name:string;source_path:string;line_start:number;line_end:number;stage:string;criticality:string;status:string;blocker:string|null;test_count:number;binding_confidence:string[];description_source:string;task_priority:string|null}
export interface CatalogResponse {entries:CatalogEntry[];summary:{functions:number;status_entries:number;tests:number;bindings:number;missing_descriptions:number}}
export interface SourceResponse {path:string;line_start:number;line_end:number;content:string}

export interface CanvasNodeData{id:string;kind:string;title:string;technical_name:string;parent_id:string|null;stage:string;status:string;criticality:string;x:number;y:number;badges:string[]}
export interface CanvasEdge{id:string;source:string;target:string;confidence:string;label:string}
export interface CanvasGraph{nodes:CanvasNodeData[];edges:CanvasEdge[];presets:Record<string,string[]>;summary:{nodes:number;edges:number}}
export interface ReadinessItem{function_id:string;policy:string;status:string;missing:string[];blocked_by:string[];explanation:string;code_hash:string;dimensions:{name:string;state:string;source:string;reason:string}[]}

export interface RunnerSpec{id:string;title:string;module:string;fixed_args:string[];timeout:number}
export interface RunRecord{id:string;runner_id:string;status:string;created_at:string;started_at:string|null;finished_at:string|null;pid:number|null;exit_code:number|null;reason:string|null;code_hash:string;config_hash:string;seed:number}
export interface RunEvent{schema:string;seq:number;ts:string;type:string;payload:Record<string,unknown>}

export interface Scenario{id:string;block:string;priority:string;mode:string;description:string;frame_count:number;source:string}
export interface ScenarioPlan{scenario_id:string;pose:string;poses:{pose_no:number;pose_bin:string}[];combinations:{combo_no:number;roles:Record<string,string>}[];case_count:number;synthetic_disclaimer:string}

export interface SuspectedFunction{code:string;what:string;status:string}
export interface FixSpec{schema:string;priority:string;category:string;title:string;human_summary:string;technical_summary:string;reproduction:{runner_id:string|null;run_id:string|null;seed:number|null;scenario_id:string|null;code_hash:string|null};suspected_functions:SuspectedFunction[];acceptance_criteria:string[];created_at:string}
export interface Classification{priority:string;category:string;human_summary:string;technical_summary:string;evidence:string[]}
export interface Investigation{classification:Classification|null;spec:FixSpec|null}
export interface Capsule{id:string;path:string;run_id:string}
export interface BackupManifest{schema:string;id:string;created_at:string;files:{path:string;existed:boolean;sha256:string}[]}
export interface IsolatedPatchResult{passed:boolean;test_output:string;applied:boolean;commit_sha:string|null;error:string|null;backup_id:string|null}
export interface RevertResult{reverted_commit:string;revert_commit:string|null}

export interface TimelineTrack{id:string;title:string;kind:string}
export interface TimelineSpan{seq:number;track_id:string;label:string;status:string;start_ts:string;end_ts:string;start_is_estimated:boolean;module_guess:string|null;stage_guess:string|null;raw_line:string}
export interface TimelinePayload{tracks:TimelineTrack[];spans:TimelineSpan[]}
export interface TimelineState{completed:TimelineSpan[];active:TimelineSpan[];pending:TimelineSpan[];at_seq:number}

export interface RunHashesInput{dataset_hash:string;code_hash:string;model_hash:string;config_hash:string}
export interface CalibrationMember{run_id:string;role:string;hashes:RunHashesInput;registered_at:string}
export interface CalibrationRunGroup{schema:string;id:string;status:string;members:Record<string,CalibrationMember>;missing_roles:string[];created_at:string;updated_at:string;approved_at:string|null;approved_by:string|null;rejected_reason:string|null;trusted_table:Record<string,unknown>|null;bundle_hash:string|null}

export interface PosePolicyBin{name:string;code:string;yaw_min:number;yaw_max:number;canonical_yaw:number}
export interface PosePolicy{bins:PosePolicyBin[];source:string;note:string}
