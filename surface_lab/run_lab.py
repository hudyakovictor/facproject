from __future__ import annotations
import argparse, sys
from pathlib import Path
SURFACE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SURFACE_DIR.parent
# surface_lab/ and uv_module/ are sibling folders in the project root.
sys.path.insert(0, str(PROJECT_ROOT))
from surface_lab.config import LabConfig
from surface_lab.backends import ClassicalRidgeBackend, FFHQWrinkleBackend
from surface_lab.pipeline import process_record, compare_records
from surface_lab.identity import compare_all

def main():
    p = argparse.ArgumentParser(description="Surface Evidence Lab")
    p.add_argument("--records", required=True, help="Stage-1 output folder containing record subfolders")
    p.add_argument("--output", required=True)
    p.add_argument("--backend", choices=["classical", "ffhq"], default="classical")
    p.add_argument("--ffhq-repo", default=str(SURFACE_DIR / "third_party" / "FFHQ-detect-face-wrinkles"))
    p.add_argument("--checkpoint")
    p.add_argument("--device", default="cpu")
    p.add_argument("--threshold", type=float, default=.5)
    p.add_argument("--analysis-region", choices=["full_face", "skin_only"], default="full_face")
    p.add_argument("--detail-mode", choices=["none", "gentle", "strong", "clahe"], default="none", help="optional model-input detail enhancement test")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--all-pairs", action="store_true", help="compare every processed record pair")
    a = p.parse_args()
    cfg = LabConfig(probability_threshold=a.threshold, analysis_region=a.analysis_region, detail_mode=a.detail_mode)
    if a.backend == "ffhq":
        if not a.checkpoint:
            p.error("--checkpoint is required for --backend ffhq")
        backend = FFHQWrinkleBackend(a.ffhq_repo, a.checkpoint, a.device, cfg.ffhq_input_size, detail_mode=a.detail_mode)
    else:
        backend = ClassicalRidgeBackend(detail_mode=a.detail_mode)
    records = [x for x in sorted(Path(a.records).iterdir()) if x.is_dir() and (x / "reconstruction.npz").exists()]
    if a.limit:
        records = records[:a.limit]
    out = Path(a.output)
    produced = []
    for i, r in enumerate(records, 1):
        print(f"[{i}/{len(records)}] {r.name}")
        od = out / r.name
        process_record(r, od, backend, cfg)
        produced.append(od)
    if len(produced) >= 2 and a.all_pairs:
        compare_all(produced, out / "identity_pairs")
    elif len(produced) >= 2:
        compare_records(produced[0], produced[1], out / "comparisons" / f"{produced[0].name}__{produced[1].name}")
    print(f"DONE records={len(produced)} backend={backend.name}")

if __name__ == "__main__":
    main()
