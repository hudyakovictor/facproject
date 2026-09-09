"""Command-line entry point for Stage 2.

    python -m app6.stage2_v2.cli run \\
        --stage1 /path/to/stage1_out \\
        --output /path/to/stage2_out \\
        --profile default \\
        --report

The `--report` flag is what produces the journalist draft. It is opt-in rather
than automatic, because generating readable prose from a run is a decision a
person should make deliberately after looking at the numbers.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import journalist_report, pipeline
from .params import BUILTIN_PROFILES, Params, builtin


def _load_params(args: argparse.Namespace) -> Params:
    if args.params:
        return Params.load(Path(args.params))
    return builtin(args.profile)


def cmd_run(args: argparse.Namespace) -> int:
    params = _load_params(args)
    stage1_root = Path(args.stage1)
    output_dir = Path(args.output)

    project_root = Path(args.project_root) if args.project_root else None
    if project_root is None:
        # app6/stage2_v2/cli.py -> app6/
        project_root = Path(__file__).resolve().parent.parent

    print(f"stage 1 root : {stage1_root}")
    print(f"output       : {output_dir}")
    print(f"profile      : {args.profile if not args.params else args.params}")
    print(f"config hash  : {params.hash()}")
    print()

    result = pipeline.run(stage1_root, params, project_root=project_root)

    summary = result.load.summary()
    print(f"photos loaded    : {summary['loaded']}  (failed: {summary['failed']})")
    print(f"distinct dates   : {summary['distinct_dates']}")
    print(f"temporal axis    : {'ok' if result.axis.admitted else result.axis.skip_reason}")
    print(f"zone map         : {result.zone_map.source} ({len(result.zone_map.zones)} zones)")
    print(f"pairs measured   : {len(result.pairs)}  (skipped: {len(result.skipped)})")
    print(f"noise floor      : {result.noise.get('status')}")
    print(f"scored           : {len(result.scored)}")
    print(f"significant      : {len(result.significant)}")

    if result.warnings:
        print()
        print("warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    written = pipeline.write_artifacts(result, output_dir)

    if args.report:
        context = journalist_report.DraftContext(
            subject_label=args.subject,
            dataset_label=args.dataset,
            synthetic=args.synthetic,
            synthetic_note=args.synthetic_note,
            analyst=args.analyst,
        )
        written += journalist_report.write_draft(result, output_dir, context)

    print()
    print(f"wrote {len(written)} artifact(s) to {output_dir}")
    for path in written:
        print(f"  {path.name}")
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    for name in sorted(BUILTIN_PROFILES):
        params = builtin(name)
        changed = params.non_default()
        print(f"{name:<18} hash={params.hash()[:16]}  overrides={len(changed)}")
        for key, value in sorted(changed.items()):
            print(f"    {key} = {value!r}")
    return 0


def cmd_params(args: argparse.Namespace) -> int:
    params = _load_params(args)
    print(json.dumps(params.to_json(), indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stage2_v2", description="Stage 2 facial geometry analysis"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a full Stage 2 pass")
    run.add_argument("--stage1", required=True, help="Stage 1 output directory")
    run.add_argument("--output", required=True, help="Stage 2 output directory")
    run.add_argument("--profile", default="default", choices=sorted(BUILTIN_PROFILES))
    run.add_argument("--params", help="path to a saved params JSON (overrides --profile)")
    run.add_argument("--project-root", help="project root, for locating the zone atlas")
    run.add_argument("--report", action="store_true", help="also write the journalist draft")
    run.add_argument("--subject", default="the subject")
    run.add_argument("--dataset", default="the photo set")
    run.add_argument("--analyst", default="")
    run.add_argument(
        "--synthetic",
        action="store_true",
        help="stamp the draft as synthetic demonstration data",
    )
    run.add_argument("--synthetic-note", default="")
    run.set_defaults(func=cmd_run)

    profiles = sub.add_parser("profiles", help="list built-in parameter profiles")
    profiles.set_defaults(func=cmd_profiles)

    show = sub.add_parser("params", help="print resolved parameters as JSON")
    show.add_argument("--profile", default="default", choices=sorted(BUILTIN_PROFILES))
    show.add_argument("--params")
    show.set_defaults(func=cmd_params)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
