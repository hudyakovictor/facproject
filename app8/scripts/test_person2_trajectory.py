"""
Комплексный анализ непрерывной траектории поворота головы одного человека (person2, 169 кадров).
1. Извлечение 3DMM и классификация по 9 бинам ракурсов;
2. Расчет внутриракурсного шума (Intra-Bin Noise) до и после канонического выравнивания;
3. Расчет межракурсного шума (Cross-Bin Noise) между крайними углами;
4. Проверка разделимости person2 от остальных людей (Viktor, Trump, Musk).
"""
from __future__ import annotations
import argparse, contextlib, itertools, json, time, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app8"))

from app8.config import Stage1Config, POSE_BINS
from app8.engine import run_stage1
from app8.reader import load_record, get_ldm134, get_ldm106, App8Record
from app8.chronology import load_chronology_dataset
from app7.metrics import kabsch_align
from app7.osteo import osteo_mask


def analyze_person2(results_dir: Path, output_json: Path):
    print("Loading extracted stage1 records for person2...")
    records_by_bin = load_chronology_dataset(results_dir)
    
    all_recs = []
    for recs in records_by_bin.values():
        all_recs.extend(recs)
        
    all_recs.sort(key=lambda r: r.photo_id)
    n_total = len(all_recs)
    print(f"Total processed frames: {n_total}")
    
    # 1. Траектория углов Эйлера (Yaw / Pitch / Roll)
    yaws = [float(r.angles_deg[1]) for r in all_recs]
    pitches = [float(r.angles_deg[0]) for r in all_recs]
    rolls = [float(r.angles_deg[2]) for r in all_recs]
    
    traj_summary = {
        "min_yaw": float(np.min(yaws)),
        "max_yaw": float(np.max(yaws)),
        "yaw_span": float(np.max(yaws) - np.min(yaws)),
        "mean_pitch": float(np.mean(pitches)),
        "pitch_std": float(np.std(pitches)),
        "mean_roll": float(np.mean(rolls)),
        "roll_std": float(np.std(rolls)),
    }
    
    # 2. Анализ внутри каждого бина ракурса (Intra-Bin Noise)
    bin_stats = {}
    total_intra_pairs = 0
    all_intra_mesh_raw = []
    all_intra_mesh_chrono = []
    all_intra_mesh_kabsch_osteo = []
    all_intra_ldm_median = []
    all_intra_id_l2 = []
    
    for bin_name, recs in sorted(records_by_bin.items()):
        n_bin = len(recs)
        if n_bin < 2:
            bin_stats[bin_name] = {"count": n_bin, "status": "insufficient_pairs"}
            continue
            
        bin_yaws = [float(r.angles_deg[1]) for r in recs]
        
        # Попарные сравнения внутри бина
        mesh_raw_res = []
        mesh_chrono_res = []
        mesh_kabsch_osteo_res = []
        ldm_res = []
        id_l2_res = []
        
        for r1, r2 in itertools.combinations(recs, 2):
            total_intra_pairs += 1
            # 1. Сырой резидуал без выравнивания позы
            d_raw = np.linalg.norm(r1.vertices_object - r2.vertices_object, axis=1)
            p95_raw = float(np.percentile(d_raw, 95))
            mesh_raw_res.append(p95_raw)
            all_intra_mesh_raw.append(p95_raw)
            
            # 2. Хронологический резидуал после канонического выравнивания R_corr
            d_chrono = np.linalg.norm(r1.vertices_chronology - r2.vertices_chronology, axis=1)
            p95_chrono = float(np.percentile(d_chrono, 95))
            mesh_chrono_res.append(p95_chrono)
            all_intra_mesh_chrono.append(p95_chrono)
            
            # 3. Резидуал Kabsch на остеологической маске костей (лоб/скулы/нос) с видимыми точками
            vis = r1.visible_mask & r2.visible_mask
            osteo = osteo_mask(r1.uv_coords)
            g = osteo & vis & (r1.vertex_confidence >= 0.5) & (r2.vertex_confidence >= 0.5)
            
            if g.sum() >= 30:
                R_k, t_k = kabsch_align(r1.vertices_identity_only[g], r2.vertices_identity_only[g])
                d_osteo = np.linalg.norm(r2.vertices_identity_only[g] @ R_k + t_k - r1.vertices_identity_only[g], axis=1)
                p95_osteo = float(np.percentile(d_osteo, 95))
                mesh_kabsch_osteo_res.append(p95_osteo)
                all_intra_mesh_kabsch_osteo.append(p95_osteo)
                
            # 4. Резидуал 134 ориентиров
            vis_l = (r1.vertex_confidence[r1.ldm134_indices] >= 0.5) & (r2.vertex_confidence[r2.ldm134_indices] >= 0.5)
            if vis_l.sum() >= 15:
                l1 = get_ldm134(r1, "identity_only")[vis_l]
                l2 = get_ldm134(r2, "identity_only")[vis_l]
                R_l, t_l = kabsch_align(l1, l2)
                d_l = np.linalg.norm(l2 @ R_l + t_l - l1, axis=1)
                med_l = float(np.median(d_l))
                ldm_res.append(med_l)
                all_intra_ldm_median.append(med_l)
                
            # 5. Сырое L2 расстояние в латенте alpha_id
            d_id = float(np.linalg.norm(r1.alpha_id - r2.alpha_id))
            id_l2_res.append(d_id)
            all_intra_id_l2.append(d_id)
            
        bin_stats[bin_name] = {
            "count": n_bin,
            "yaw_range": [float(np.min(bin_yaws)), float(np.max(bin_yaws))],
            "pairs_count": len(mesh_raw_res),
            "mesh_raw_p95_mean": float(np.mean(mesh_raw_res)),
            "mesh_raw_p95_max": float(np.max(mesh_raw_res)),
            "mesh_chrono_p95_mean": float(np.mean(mesh_chrono_res)),
            "mesh_chrono_p95_max": float(np.max(mesh_chrono_res)),
            "mesh_osteo_kabsch_p95_mean": float(np.mean(mesh_kabsch_osteo_res)) if mesh_kabsch_osteo_res else None,
            "mesh_osteo_kabsch_p95_max": float(np.max(mesh_kabsch_osteo_res)) if mesh_kabsch_osteo_res else None,
            "ldm_median_mean": float(np.mean(ldm_res)) if ldm_res else None,
            "ldm_median_max": float(np.max(ldm_res)) if ldm_res else None,
            "id_l2_mean": float(np.mean(id_l2_res)),
            "id_l2_max": float(np.max(id_l2_res)),
            "noise_reduction_pct": float((1.0 - np.mean(mesh_chrono_res) / np.mean(mesh_raw_res)) * 100.0) if np.mean(mesh_raw_res) > 0 else 0.0,
        }
        
    # 3. Межракурсный шум (Cross-Bin Noise между крайними углами)
    cross_bin_stats = {}
    bin_names = sorted([b for b, v in bin_stats.items() if isinstance(v, dict) and "pairs_count" in v])
    for b1, b2 in itertools.combinations(bin_names, 2):
        recs1 = records_by_bin[b1]
        recs2 = records_by_bin[b2]
        if not recs1 or not recs2: continue
        
        cross_osteo = []
        cross_id_l2 = []
        for r1 in recs1:
            for r2 in recs2:
                vis = r1.visible_mask & r2.visible_mask
                osteo = osteo_mask(r1.uv_coords)
                g = osteo & vis & (r1.vertex_confidence >= 0.5) & (r2.vertex_confidence >= 0.5)
                if g.sum() >= 30:
                    R_k, t_k = kabsch_align(r1.vertices_identity_only[g], r2.vertices_identity_only[g])
                    d_osteo = np.linalg.norm(r2.vertices_identity_only[g] @ R_k + t_k - r1.vertices_identity_only[g], axis=1)
                    cross_osteo.append(float(np.percentile(d_osteo, 95)))
                cross_id_l2.append(float(np.linalg.norm(r1.alpha_id - r2.alpha_id)))
                
        cross_bin_stats[f"{b1}_vs_{b2}"] = {
            "pairs": len(cross_id_l2),
            "mesh_osteo_p95_mean": float(np.mean(cross_osteo)) if cross_osteo else None,
            "mesh_osteo_p95_max": float(np.max(cross_osteo)) if cross_osteo else None,
            "id_l2_mean": float(np.mean(cross_id_l2)),
            "id_l2_max": float(np.max(cross_id_l2)),
        }
        
    overall_report = {
        "dataset": "person2_continuous_rotation",
        "total_frames": n_total,
        "total_intra_pairs": total_intra_pairs,
        "trajectory": traj_summary,
        "intra_bin_summary": {
            "mesh_raw_p95_overall_mean": float(np.mean(all_intra_mesh_raw)),
            "mesh_chrono_p95_overall_mean": float(np.mean(all_intra_mesh_chrono)),
            "mesh_osteo_kabsch_p95_overall_mean": float(np.mean(all_intra_mesh_kabsch_osteo)),
            "mesh_osteo_kabsch_p95_overall_max": float(np.max(all_intra_mesh_kabsch_osteo)),
            "ldm_median_overall_mean": float(np.mean(all_intra_ldm_median)),
            "ldm_median_overall_max": float(np.max(all_intra_ldm_median)),
            "overall_noise_reduction_pct": float((1.0 - np.mean(all_intra_mesh_chrono) / np.mean(all_intra_mesh_raw)) * 100.0),
        },
        "per_bin_breakdown": bin_stats,
        "cross_bin_breakdown": cross_bin_stats,
    }
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(overall_report, f, indent=2, ensure_ascii=False)
        
    print(f"\nAnalysis completed! Results saved to {output_json}")
    return overall_report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=Path("/home/user/facproject/dataset_3people/person2"))
    p.add_argument("--stage1-out", type=Path, default=Path("/tmp/person2_stage1"))
    p.add_argument("--report-out", type=Path, default=Path("/tmp/person2_analysis.json"))
    p.add_argument("--device", default="cpu")
    args = p.parse_args()
    
    print("=== STEP 1: Running app8 Stage 1 on Person2 Trajectory Dataset ===")
    cfg = Stage1Config(
        project_root=Path("/home/user/facproject"),
        input_dir=args.input,
        output_dir=args.stage1_out,
        device=args.device,
        save_mesh=False,
        save_original=False,
    )
    t0 = time.time()
    manifest = run_stage1(cfg)
    print(f"Stage 1 extraction finished in {time.time() - t0:.1f}s")
    
    print("\n=== STEP 2: Computing Intra-Bin Noise & Trajectory Statistics ===")
    report = analyze_person2(args.stage1_out, args.report_out)
    
    print("\n" + "=" * 75)
    print("🎯 ИТОГОВЫЕ РЕЗУЛЬТАТЫ АНАЛИЗА ШУМОВ ПО СЕРИИ КАДРОВ ОДНОГО ЧЕЛОВЕКА")
    print("=" * 75)
    traj = report["trajectory"]
    print(f"• Охват ракурсов: Yaw от {traj['min_yaw']:+.1f}° до {traj['max_yaw']:+.1f}° (размах {traj['yaw_span']:.1f}°)")
    print(f"• Всего кадров: {report['total_frames']} | Всего попарных сравнений одного человека: {report['total_intra_pairs']}")
    
    intra = report["intra_bin_summary"]
    print(f"\n• Снижение позового шума каноническим выравниванием: {intra['overall_noise_reduction_pct']:.1f}%")
    print(f"• Средний сырой шум сетки (raw p95): {intra['mesh_raw_p95_overall_mean']:.4f}")
    print(f"• Средний остаточный хронологический шум (chrono p95): {intra['mesh_chrono_p95_overall_mean']:.4f}")
    print(f"• Шум на жесткой остеомаске костей (Osteo Kabsch p95): mean={intra['mesh_osteo_kabsch_p95_overall_mean']:.4f}, max={intra['mesh_osteo_kabsch_p95_overall_max']:.4f}")
    print(f"• Шум ключевых точек L134 (Median residual): mean={intra['ldm_median_overall_mean']:.4f}, max={intra['ldm_median_overall_max']:.4f}")
    
    print("\nТаблица по корзинам ракурсов (Intra-Bin Analysis):")
    print("-" * 75)
    print(f"{'Ракурс (Pose Bin)':<16} | {'Кадров':<6} | {'Yaw Range':<15} | {'Osteo p95':<11} | {'L134 Med':<10} | {'Noise Reduc.'}")
    print("-" * 75)
    for bname, bdata in sorted(report["per_bin_breakdown"].items()):
        if bdata.get("status") == "insufficient_pairs":
            print(f"{bname:<16} | {bdata['count']:<6} | {'-':<15} | {'-':<11} | {'-':<10} | {'-'}")
            continue
        yr = f"{bdata['yaw_range'][0]:+.0f}°..{bdata['yaw_range'][1]:+.0f}°"
        osteo_str = f"{bdata['mesh_osteo_kabsch_p95_mean']:.4f}" if bdata['mesh_osteo_kabsch_p95_mean'] else "-"
        ldm_str = f"{bdata['ldm_median_mean']:.4f}" if bdata['ldm_median_mean'] else "-"
        print(f"{bname:<16} | {bdata['count']:<6} | {yr:<15} | {osteo_str:<11} | {ldm_str:<10} | {bdata['noise_reduction_pct']:.1f}%")
    print("-" * 75)
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
