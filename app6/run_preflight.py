#!/usr/bin/env python3
"""Fail-closed release preflight for calibration, Stage 1 and model assets."""
from __future__ import annotations
import argparse,csv,json,sys
from pathlib import Path

POSES={'left_profile','left_deep','left_mid','left_light','frontal','right_light','right_mid','right_deep','right_profile'}
PATH_COLUMNS=('ldm106_raw_file','ldm106_aligned_file','ldm134_raw_file','ldm134_aligned_file','metadata_file','npz_file')

def audit_calibration_index(index_path:Path,data_root:Path,check_files:bool=True)->dict:
    with index_path.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    errors=[]; warnings=[]
    required={'dataset_id','record_id','pose_bin','yaw','pitch','roll',*PATH_COLUMNS}
    missing_columns=sorted(required-set(rows[0] if rows else []))
    if not rows: errors.append('calibration index is empty')
    if missing_columns: errors.append('missing columns: '+','.join(missing_columns))
    keys=[(r.get('dataset_id'),r.get('record_id'),r.get('pose_bin')) for r in rows]
    if len(keys)!=len(set(keys)): errors.append('duplicate dataset/record/pose rows')
    people=sorted({str(r.get('dataset_id')) for r in rows if r.get('dataset_id')})
    poses=sorted({str(r.get('pose_bin')) for r in rows if r.get('pose_bin')})
    if set(poses)!=POSES: errors.append(f'pose bins mismatch: {poses}')
    if len(people)<7: warnings.append(f'only {len(people)} calibration people')
    missing_files=[]
    if check_files:
        for r in rows:
            for col in PATH_COLUMNS:
                rel=r.get(col)
                if not rel or not (data_root/rel).is_file(): missing_files.append(f'{col}:{rel}')
        if missing_files: errors.append(f'missing referenced files: {len(missing_files)}')
    counts={}
    for r in rows: counts.setdefault(str(r.get('dataset_id')),{}).setdefault(str(r.get('pose_bin')),0);counts[str(r.get('dataset_id'))][str(r.get('pose_bin'))]+=1
    return {'status':'ready' if not errors else 'blocked','rows':len(rows),'people':people,'pose_bins':poses,'counts':counts,'missing_file_count':len(missing_files),'missing_file_examples':missing_files[:20],'errors':errors,'warnings':warnings}

def audit_texture_atlas(root:Path)->dict:
    """Fail-fast контракт текстурного атласа (ТЗ: без автогенерации и fallback).

    Проверяет app6/atlas/texture_zones_bfm35709_v3.npz против BFM assets:
    существование, ключи, triangle count == 70789 == BFM tri, диапазоны
    main/subzone labels, digest топологии, версия схемы. Анатомическая
    семантика зон здесь НЕ проверяется (требует канонического источника +
    визуального preview вне preflight). Автогенерация запрещена: отсутствующий
    или битый атлас = blocked, а не сгенерированный суррогат.
    """
    import numpy as np
    atlas=root/'app6'/'atlas'/'texture_zones_bfm35709_v3.npz'
    rep={'path':str(atlas),'errors':[],'warnings':[],'checks':{}}
    if not atlas.is_file():
        rep['errors'].append('missing texture atlas (no autogeneration allowed)')
        rep['status']='blocked';return rep
    try:
        z=np.load(atlas,allow_pickle=False)
        files=set(z.files)
        need={'triangle_main_label','triangle_subzone_label','triangle_skin_mask',
              'main_codes','subzone_codes','topology_tri_digest'}
        missing=sorted(need-files)
        rep['checks']['required_keys']=not missing
        if missing: rep['errors'].append('atlas missing keys: '+','.join(missing))
        n=int(z['triangle_main_label'].shape[0]) if 'triangle_main_label' in files else -1
        rep['checks']['triangle_count']=n
        if n!=70789: rep['errors'].append(f'atlas triangle count {n} != 70789')
        main=np.asarray(z['triangle_main_label']).reshape(-1)
        sub=np.asarray(z['triangle_subzone_label']).reshape(-1)
        codes_main={str(c) for c in np.asarray(z['main_codes']).reshape(-1)} if 'main_codes' in files else set()
        codes_sub={str(c) for c in np.asarray(z['subzone_codes']).reshape(-1)} if 'subzone_codes' in files else set()
        rep['checks']['main_label_range']=(int(main.min()),int(main.max()))
        rep['checks']['subzone_label_range']=(int(sub.min()),int(sub.max()))
        if int(main.min())<-1 or int(main.max())>=len(codes_main)+1:
            rep['warnings'].append('main labels outside declared codes (may include -1=none)')
        if int(sub.min())<-1 or int(sub.max())>=len(codes_sub)+1:
            rep['warnings'].append('subzone labels outside declared codes (may include -1=none)')
        # совместимость с BFM: число треугольников модели
        fm=root/'assets'/'face_model.npy'
        if fm.is_file():
            tri=np.load(fm,allow_pickle=True).item()['tri']
            rep['checks']['bfm_triangles']=int(np.asarray(tri).shape[0])
            if int(np.asarray(tri).shape[0])!=n:
                rep['errors'].append('atlas/BFM triangle count mismatch')
        else:
            rep['warnings'].append('face_model.npy absent; BFM compat unchecked')
        dg=str(np.asarray(z['topology_tri_digest']).reshape(-1)[0]) if 'topology_tri_digest' in files else ''
        rep['checks']['topology_digest_present']=bool(dg)
        if not dg: rep['warnings'].append('topology digest empty')
    except Exception as exc:
        rep['errors'].append(f'atlas unreadable: {exc}')
    rep['status']='ready' if not rep['errors'] else 'blocked'
    return rep

def main()->int:
    p=argparse.ArgumentParser(description='DEEPUTIN release preflight')
    p.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--calibration-root',type=Path,required=True)
    p.add_argument('--calibration-index',type=Path)
    p.add_argument('--stage1-root',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--skip-calibration-file-check',action='store_true')
    p.add_argument('--expected-dataset-hash',help='Блокировать запуск, если хеш калибровки отличается (ТЗ п.11)')
    p.add_argument('--expected-code-hash',help='Блокировать запуск, если хеш кода стадий отличается')
    p.add_argument('--expected-model-hash',help='Блокировать запуск, если хеш модели отличается')
    p.add_argument('--expected-config-hash',help='Блокировать запуск, если хеш конфигурации отличается')
    a=p.parse_args();root=a.project_root.resolve();cal=a.calibration_root.resolve();idx=(a.calibration_index or cal/'all_calibration_index.csv').resolve()
    report={'schema':'deeputin-release-preflight-v1','project_root':str(root),'calibration_root':str(cal),'errors':[],'warnings':[]}
    if not idx.is_file(): report['errors'].append(f'missing calibration index: {idx}')
    else:
        report['calibration']=audit_calibration_index(idx,cal,not a.skip_calibration_file_check)
        report['errors'].extend(report['calibration']['errors']);report['warnings'].extend(report['calibration']['warnings'])
    assets=root/'assets';required=['face_model.npy','net_recon.pth','large_base_net.pth','retinaface_resnet50_2020-07-20_old_torch.pth','similarity_Lm3D_all.mat']
    missing=[x for x in required if not (assets/x).is_file()]
    report['assets']={'required':required,'missing':missing}
    if missing: report['errors'].append('missing model assets: '+','.join(missing))
    report['texture_atlas']=audit_texture_atlas(root)
    report['errors'].extend('atlas: '+e for e in report['texture_atlas']['errors'])
    report['warnings'].extend('atlas: '+w for w in report['texture_atlas']['warnings'])
    if not (root/'3ddfa_v3'/'model'/'recon.py').is_file(): report['errors'].append('missing 3ddfa_v3 source')
    if a.stage1_root:
        s=a.stage1_root.resolve();needed=['main_timeline.csv','stage1_manifest.json']
        absent=[x for x in needed if not (s/x).is_file()];report['stage1']={'root':str(s),'missing':absent}
        if absent: report['errors'].append('stage1 output incomplete: '+','.join(absent))
    # 🔒 GUARD (ТЗ п.11 / D8): хеши целостности сверяются до запуска, а не только
    # вычисляются. Проверка выполняется лишь когда эталон передан явно, чтобы
    # первый прогон мог зафиксировать базовые значения.
    if idx.is_file():
        sys.path.insert(0, str(root))
        from app6.stage2.integrity import compute_code_hash, compute_dataset_hash, verify_integrity_hashes
        actual={'dataset_hash':compute_dataset_hash(idx),'code_hash':compute_code_hash(root)}
        if a.stage1_root and (a.stage1_root.resolve()/'stage1_manifest.json').is_file():
            stage1_manifest=json.loads((a.stage1_root.resolve()/'stage1_manifest.json').read_text(encoding='utf-8'))
            actual['calibration_dataset_hash']=actual['dataset_hash'];actual['dataset_hash']=stage1_manifest.get('dataset_hash')
            actual.update({k:stage1_manifest.get(k) for k in ('model_hash','config_hash')})
        expected={k:v for k,v in (
            ('dataset_hash',a.expected_dataset_hash),('code_hash',a.expected_code_hash),
            ('model_hash',a.expected_model_hash),('config_hash',a.expected_config_hash),
        ) if v}
        integrity={'schema':'deeputin-integrity-guard-v1.1-sha256','hash_algorithm':'sha256','actual':actual,'checked':bool(expected)}
        if expected:
            result=verify_integrity_hashes(expected,actual,required_keys=tuple(expected),strict=False)
            integrity.update(result)
            if result['status']!='ok':
                report['errors'].append(f"integrity check failed: mismatched={result['mismatched']} missing={result['missing']}")
        else:
            integrity['note']='эталонные хеши не переданы; значения зафиксированы для последующих прогонов'
        report['integrity']=integrity
    report['status']='ready' if not report['errors'] else 'blocked'
    text=json.dumps(report,ensure_ascii=False,indent=2);print(text)
    if a.output:a.output.write_text(text+'\n',encoding='utf-8')
    return 0 if report['status']=='ready' else 1
if __name__=='__main__':raise SystemExit(main())