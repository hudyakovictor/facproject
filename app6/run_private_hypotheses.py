"""🚪 ENTRY POINT → Изолированный прогон private-hypothesis слоя (retest гипотез).
🔗 DEPENDS ON: stage2.private_hypothesis.run()
🚨 WARNING: результаты НЕ входят в публичный отчёт — только quarantine-zone.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app6.stage2.private_hypothesis import PrivateHypothesisConfig, PrivateHypothesisEngine


# 🚪 ENTRY POINT → argparse + private_hypothesis.run()
def main() -> None:
    parser = argparse.ArgumentParser(description="Run the isolated private hypothesis retest layer.")
    parser.add_argument("analysis", type=Path, help="Current Stage-2 output made with the current alignment")
    parser.add_argument("legacy_archive", type=Path, help="Unpacked legacy hypothesis archive")
    parser.add_argument("output", type=Path, help="Private output directory; never use as public Stage-3 input")
    parser.add_argument("--minimum-import-coverage", type=float, default=0.95)
    args = parser.parse_args()
    manifest = PrivateHypothesisEngine(PrivateHypothesisConfig(
        analysis_root=args.analysis.resolve(), legacy_archive_root=args.legacy_archive.resolve(),
        output_dir=args.output.resolve(), minimum_import_coverage=args.minimum_import_coverage,
    )).run()
    print(f"status={manifest['status']} coverage={manifest['import_coverage_fraction']:.4f} imported={manifest['imported_record_count']} retested={manifest['retested_with_current_alignment_count']} pending={manifest['pending_missing_current_data_count']}")


if __name__ == "__main__":
    main()
