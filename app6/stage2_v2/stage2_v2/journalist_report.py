"""Journalist draft generator - the last stage before a human reader.

This writes the chronological walk-through: every dated observation in order,
what was measured between each pair of dates, what it means, and - given equal
weight - what it does not mean.

The house style is borrowed from the investigative tradition that earns trust
by being checkable rather than by sounding certain:

  * Plain words. If a sentence needs jargon, the jargon gets a definition on
    first use.
  * The method is described before the results, so a reader can judge the
    method independently of whether they like the conclusion.
  * Numbers appear inline with their uncertainty attached. Never a point
    estimate on its own.
  * Negative results get the same space as positive ones. A period where
    nothing was found is reported as a finding, not omitted.
  * Every counter-explanation is listed, including the ones this pipeline
    cannot rule out. Those are stated as prominently as the findings.
  * Every claim carries the pair IDs behind it, so any assertion can be walked
    back to the underlying rows.

The generator will not write a conclusion the data does not support, because
there is no code path that produces one. If the run found nothing, the draft
says so, at length, and that is the honest deliverable.

A note on identity claims: this pipeline measures facial geometry over time.
It cannot establish that two photographs show different people. That inference
needs a validated per-person discrimination threshold, measured on a reference
population with known ground truth. No such threshold exists here, so no such
sentence can be generated, and the draft says this explicitly so that nobody
fills the gap by assumption.
"""
from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import narrative
from .narrative import (
    COUNTER_EXPLANATIONS,
    Claim,
    build_periods,
    localized_zone_claims,
    period_claim,
    zone_claims,
)

REPORT_SCHEMA = "deeputin-stage2-journalist-draft-v1"


@dataclass
class DraftContext:
    """Everything the draft needs to know about provenance and status."""

    subject_label: str = "the subject"
    dataset_label: str = "the photo set"
    #: Set True for synthetic or demonstration data. Stamps an unmissable
    #: banner on every output format.
    synthetic: bool = False
    synthetic_note: str = ""
    analyst: str = ""


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------
def build_draft(result, context: DraftContext) -> dict:
    """Assemble the structured draft from a Stage 2 RunResult."""
    anatomical = result.zone_map.anatomical
    periods = build_periods(result.pairs)

    chapters = []
    for period in periods:
        headline = period_claim(period, anatomical=anatomical)
        chapters.append(
            {
                "period": period.label,
                "start": period.start,
                "end": period.end,
                "days": period.days,
                "years": round(period.years, 2) if period.years else None,
                "pair_count": len(period.pairs),
                "headline": headline.to_json(),
                # Two distinct cases, deliberately merged into one display
                # list: the zone breakdown of a significant whole-face result,
                # and zones that moved while the whole face looked quiet. The
                # second is the one the global statistic cannot see.
                "zones": [
                    c.to_json()
                    for c in (
                        zone_claims(period, anatomical=anatomical)
                        + localized_zone_claims(period, anatomical=anatomical)
                    )
                ],
                "pairs": [
                    {
                        "pair_id": p.pair_id,
                        "photo_a": p.photo_a,
                        "photo_b": p.photo_b,
                        "pose_bin": p.pose_bin,
                        "evidence_class": p.verdict.evidence_class,
                        "limits": sorted(p.verdict.limits),
                        "rmse_ioc": p.to_json()["rmse_ioc"],
                        "coherence": p.to_json()["coherence"],
                        "z_score": p.to_json()["z_score"],
                        "q_value": p.to_json()["q_value"],
                        "significant": p.significant,
                        "status": p.status,
                    }
                    for p in sorted(period.pairs, key=lambda p: p.pair_id)
                ],
            }
        )

    reportable = [c for c in chapters if c["headline"]["strength"] in {"moderate", "strong"}]
    negative = [c for c in chapters if c["headline"]["strength"] == "none"]
    unusable = [c for c in chapters if c["headline"]["strength"] == "insufficient"]
    localized = [c for c in chapters if c["headline"]["strength"] == "weak"]

    return {
        "schema": REPORT_SCHEMA,
        "context": {
            "subject_label": context.subject_label,
            "dataset_label": context.dataset_label,
            "synthetic": context.synthetic,
            "synthetic_note": context.synthetic_note,
            "analyst": context.analyst,
        },
        "manifest": result.manifest(),
        "bottom_line": _bottom_line(result, chapters, context),
        "chapters": chapters,
        "tally": {
            "periods": len(chapters),
            "reportable": len(reportable),
            "localized_or_weak": len(localized),
            "no_change": len(negative),
            "unusable": len(unusable),
        },
        "counter_explanations": [
            {
                "factor": name,
                "why_it_matters": why,
                "control": control,
                "how_handled": handled,
                "controlled": control != "not_controlled",
            }
            for name, why, control, handled in COUNTER_EXPLANATIONS
        ],
        "limitations": _limitations(result, context),
        "cannot_conclude": _cannot_conclude(),
        "method_plain": _method_plain(result),
    }


def _bottom_line(result, chapters: list[dict], context: DraftContext) -> dict:
    """The one paragraph an editor reads first. Written last, deliberately."""
    strong = [c for c in chapters if c["headline"]["strength"] == "strong"]
    moderate = [c for c in chapters if c["headline"]["strength"] == "moderate"]
    scored = len(result.scored)

    if result.noise.get("status") != "ok":
        text = (
            "This run produced no publishable finding. The noise floor could "
            "not be established, which means there is no baseline to judge any "
            "measurement against. Every number below is uncalibrated and none "
            "of it supports a claim in either direction."
        )
        verdict = "no_baseline"
    elif not scored:
        text = (
            "This run produced no publishable finding. No photo pair survived "
            "the gates, so nothing was measured. This is a statement about the "
            "photo set, not about the subject."
        )
        verdict = "nothing_measured"
    elif strong:
        text = (
            f"Across {len(chapters)} intervals, {len(strong)} show a clear "
            f"measurable change in facial geometry and {len(moderate)} show a "
            "change with wider uncertainty. Ageing, weight change, and health "
            "are ordinary explanations that this analysis does not rule out."
        )
        verdict = "change_detected"
    elif moderate:
        text = (
            f"Across {len(chapters)} intervals, {len(moderate)} show a "
            "measurable change with meaningful uncertainty, and none rise to a "
            "clear finding. This is suggestive at most and would need more "
            "photographs before it carried weight."
        )
        verdict = "weak_signal"
    elif [c for c in chapters if c["headline"]["strength"] == "weak"]:
        count = len([c for c in chapters if c["headline"]["strength"] == "weak"])
        text = (
            f"Across {len(chapters)} intervals, the face as a whole stayed "
            f"inside the measurement noise everywhere, but in {count} interval"
            f"{'s' if count != 1 else ''} an individual region exceeded its "
            "own noise floor. That pattern is what a localised change looks "
            "like, and it is invisible to a whole-face average. It is also "
            "what correlated noise in one region looks like. This pipeline "
            "cannot tell those apart, and in testing it identified the date of "
            "such a change correctly while naming the wrong region. Treat this "
            "as a pointer for manual inspection, not a finding."
        )
        verdict = "localized_candidate"
    else:
        text = (
            f"Across {len(chapters)} intervals covering {scored} scored "
            "comparisons, no change exceeded the measurement noise of the "
            "method. The honest summary is that nothing was found."
        )
        verdict = "no_change_detected"

    if context.synthetic:
        text = (
            "SYNTHETIC DEMONSTRATION DATA - NOT A FINDING ABOUT ANY REAL "
            "PERSON. " + text
        )

    return {"verdict": verdict, "text": text}


def _limitations(result, context: DraftContext) -> list[str]:
    """Everything a critic would raise, raised first."""
    items: list[str] = []

    if context.synthetic:
        items.append(
            "This draft was generated from synthetic data produced by the "
            "project's own fixture generator. It demonstrates the report "
            "format. It is not evidence about any person."
        )

    if not result.zone_map.anatomical:
        items.append(
            "No measured anatomical atlas was available, so zones are neutral "
            "index blocks. Zone-level results carry no anatomical meaning and "
            "are deliberately not described in anatomical language."
        )

    noise = result.noise
    if noise.get("status") == "ok":
        items.append(
            f"The noise floor comes from {noise.get('same_day_pairs', 0)} "
            "same-day photo pairs. Same-day pairs contain no real change by "
            "construction, so they measure the method's own error. If the "
            "photo set has few same-day pairs, this floor is poorly estimated "
            "and every significance claim inherits that weakness."
        )
    else:
        items.append(
            "No noise floor could be built, so nothing in this run is "
            "calibrated and no significance claim is possible."
        )

    summary = result.load.summary()
    if summary.get("failed"):
        items.append(
            f"{summary['failed']} photo(s) failed to load and were excluded. "
            "Systematic exclusion (for example, if older photos fail more "
            "often) would bias the chronology."
        )

    if summary.get("distinct_dates", 0) < 5:
        items.append(
            f"Only {summary.get('distinct_dates', 0)} distinct dates are "
            "present. A chronology this sparse cannot locate when a change "
            "happened, only that it happened somewhere in a wide interval."
        )

    limited = sum(1 for p in result.pairs if p.verdict.evidence_class == "limited")
    if limited:
        items.append(
            f"{limited} of {len(result.pairs)} measured pairs carry quality or "
            "provenance limits. They may corroborate a finding but may not "
            "lead one."
        )

    items.extend(result.warnings)

    items.append(
        "Photographs are compressed, retouched, and reproduced at different "
        "resolutions. This pipeline measures what is in the file it was given, "
        "and cannot distinguish a change in a face from a change in how that "
        "face was photographed or processed."
    )

    # Surface the power precondition with the actual numbers behind it, since
    # this is the failure mode that produced a false positive in testing.
    zone_noise = getattr(result, "zone_noise", {}) or {}
    if zone_noise.get("status") == "ok":
        counts = [
            reference.get("n", 0)
            for zones in zone_noise.get("per_pose_bin", {}).values()
            for reference in zones.values()
            if reference.get("status") == "ok"
        ]
        if counts:
            items.append(
                f"Zone-level nulls rest on between {min(counts)} and "
                f"{max(counts)} same-day pairs. Below roughly 20, this method "
                "has been observed to manufacture significant-looking results "
                "from pure noise, so these counts, not the q-values, set the "
                "real confidence."
            )
    elif zone_noise:
        items.append(
            "No zone-level null could be built, so no localised change was "
            "testable. Since the whole-face residual averages a local change "
            "away, this run could not have detected a regional change even if "
            "one were present."
        )

    return items


def _cannot_conclude() -> list[str]:
    """Statements this pipeline is structurally unable to support.

    Printed in every draft. These are the inferences a reader is most likely to
    make unprompted, so leaving them unaddressed is not neutrality.
    """
    return [
        "That two photographs show different people. That requires a validated "
        "discrimination threshold measured on a reference population with "
        "known ground truth. No such threshold exists in this pipeline, and a "
        "large residual is not a substitute for one.",
        "That any change was caused by surgery, illness, or any specific "
        "intervention. The method measures geometry, not causes.",
        "That an absence of detected change means no change occurred. It means "
        "no change was detected above this method's noise, with these photos.",
        "Anything at all about a photograph that was excluded by the gates. An "
        "excluded photo was not measured and carries no information.",
        # The two entries below are not caution for its own sake. They are
        # what the fixture experiments in VALIDATION.md actually measured.
        "Which part of the face changed. Tested on synthetic data with a "
        "change injected at a known location, this pipeline dated the change "
        "correctly but named an adjoining zone rather than the one containing "
        "it. Alignment is global, so a local displacement leaks residual into "
        "neighbouring zones. Zone labels here indicate roughly where to look, "
        "never where a change is.",
        "Anything from a run whose noise floor rests on few same-day pairs. On "
        "the same signal, this code produced a confident false positive at two "
        "photos per day and a correct result at eight. A small q-value from an "
        "under-powered null is not weak evidence, it is an artefact.",
    ]


def _method_plain(result) -> list[dict]:
    """The method in plain language, for a reader with no background."""
    noise = result.noise
    floor = "could not be established in this run"
    if noise.get("status") == "ok":
        floor = (
            f"was built from {noise.get('same_day_pairs', 0)} same-day pairs "
            f"across {noise.get('usable_bins', 0)} head-angle group(s)"
        )

    return [
        {
            "step": "Reconstruct",
            "text": (
                "Each photograph is turned into a 3D model of the face. This "
                "is an estimate, and it differs slightly every time - which is "
                "why the next steps exist."
            ),
        },
        {
            "step": "Group by head angle",
            "text": (
                "Photos are sorted by which way the head is turned. Comparing "
                "a face turned 30 degrees to one facing forward produces a "
                "difference that looks exactly like a change in the face "
                "itself, so only similar angles are compared."
            ),
        },
        {
            "step": "Align",
            "text": (
                "Two faces are rotated into a common position. The alignment "
                "deliberately ignores the worst-matching points, so that one "
                "changed region cannot drag the whole fit and hide itself. "
                "Size is never adjusted, because a change in size is one of "
                "the things being measured."
            ),
        },
        {
            "step": "Measure the noise floor",
            "text": (
                "Photos taken on the same day contain no real change, so "
                "whatever difference they show is the method's own error. "
                f"That floor {floor}. Anything smaller than it is not "
                "evidence of anything."
            ),
        },
        {
            "step": "Compare and correct",
            "text": (
                "Each cross-date pair is compared against that floor. Because "
                "many comparisons are run at once, the results are corrected "
                "for multiple testing: without that correction, testing "
                "thousands of points guarantees false hits."
            ),
        },
    ]


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------
def render_markdown(draft: dict) -> str:
    """Render the draft as Markdown for an editor."""
    ctx = draft["context"]
    out: list[str] = []
    add = out.append

    if ctx["synthetic"]:
        add("> **SYNTHETIC DEMONSTRATION DATA**")
        add(">")
        add(
            "> This draft was generated from artificially created data to show "
            "the report format. Every number is invented by a fixture "
            "generator. It is not evidence about any real person."
        )
        if ctx["synthetic_note"]:
            add(">")
            add(f"> {ctx['synthetic_note']}")
        add("")

    add(f"# Facial geometry over time: {ctx['dataset_label']}")
    add("")
    add("**Working draft. Not for publication.**")
    add("")

    # Bottom line first.
    add("## The short version")
    add("")
    add(draft["bottom_line"]["text"])
    add("")

    tally = draft["tally"]
    # Every interval must land in exactly one bucket. A tally that does not sum
    # to the number of intervals hides the cases that fell between categories,
    # which are usually the interesting ones.
    add(
        f"Intervals examined: **{tally['periods']}**. "
        f"With a measurable change: **{tally['reportable']}**. "
        f"Localised or weak signal only: **{tally['localized_or_weak']}**. "
        f"With no change above noise: **{tally['no_change']}**. "
        f"Not assessable: **{tally['unusable']}**."
    )
    add("")

    # Method before results.
    add("## How this was measured")
    add("")
    add(
        "The method is described before the results so it can be judged on "
        "its own terms."
    )
    add("")
    for i, step in enumerate(draft["method_plain"], 1):
        add(f"{i}. **{step['step']}.** {step['text']}")
    add("")

    # Chronology.
    add("## The chronology")
    add("")
    if not draft["chapters"]:
        add(
            "No interval could be assembled from this photo set. Either there "
            "are too few dated photographs, or none survived the gates."
        )
        add("")
    for chapter in draft["chapters"]:
        headline = chapter["headline"]
        span = f" ({chapter['years']} years)" if chapter.get("years") else ""
        add(f"### {chapter['start']} to {chapter['end']}{span}")
        add("")
        add(f"**{headline['sentence']}**")
        add("")
        add(f"*Evidence: {headline['strength']} - {headline['usage']}.*")
        add("")
        add("Why this reading:")
        for reason in headline["reasons"]:
            add(f"- {reason}")
        add("")

        if chapter["zones"]:
            add("Where the movement sits:")
            add("")
            for zone in chapter["zones"]:
                add(f"- {zone['sentence']} *({zone['strength']})*")
            add("")

        add("| Pair | Angle group | Size (IOC) | Coherence | q | Class | Status |")
        add("|---|---|---|---|---|---|---|")
        for pair in chapter["pairs"]:
            add(
                f"| `{pair['pair_id']}` | {pair['pose_bin']} | "
                f"{_fmt(pair['rmse_ioc'], 5)} | {_fmt(pair['coherence'], 2)} | "
                f"{_fmt(pair['q_value'], 4)} | {pair['evidence_class']} | "
                f"{pair['status']} |"
            )
        add("")

    # Counter-explanations.
    add("## What else could explain this")
    add("")
    add(
        "Every alternative explanation for a measured difference, and what "
        "was done about it. The uncontrolled ones are listed with the same "
        "prominence as the controlled ones."
    )
    add("")
    add("| Factor | Why it matters | How it was handled |")
    add("|---|---|---|")
    for item in draft["counter_explanations"]:
        mark = "" if item["controlled"] else "**NOT CONTROLLED.** "
        add(
            f"| {item['factor']} | {item['why_it_matters']} | "
            f"{mark}{item['how_handled']} |"
        )
    add("")

    # Limits.
    add("## Limitations")
    add("")
    for item in draft["limitations"]:
        add(f"- {item}")
    add("")

    add("## What this analysis cannot establish")
    add("")
    add(
        "These are the conclusions a reader is most likely to reach on their "
        "own. None of them follow from this method."
    )
    add("")
    for item in draft["cannot_conclude"]:
        add(f"- {item}")
    add("")

    # Provenance.
    manifest = draft["manifest"]
    add("## Provenance")
    add("")
    add(f"- Pipeline schema: `{manifest['schema']}`")
    add(f"- Configuration hash: `{manifest['config_hash']}`")
    add(f"- Generated: {manifest['generated_at']}")
    add(f"- Photos loaded: {manifest['stage1']['loaded']}")
    add(f"- Photos failed: {manifest['stage1']['failed']}")
    add(f"- Pairs measured: {manifest['pairs']['measured']}")
    add(f"- Pairs skipped: {manifest['pairs']['skipped']}")
    add(
        "- Every claim above lists the pair IDs behind it in the machine-"
        "readable draft (`journalist_draft.json`)."
    )
    add("")

    return "\n".join(out)


def _fmt(value, digits: int) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "--"


# --------------------------------------------------------------------------
# HTML rendering
# --------------------------------------------------------------------------
def render_html(draft: dict) -> str:
    """Render the draft as a standalone HTML page."""
    ctx = draft["context"]
    esc = html.escape

    banner = ""
    if ctx["synthetic"]:
        banner = (
            '<div class="banner"><strong>SYNTHETIC DEMONSTRATION DATA</strong>'
            "<p>Generated from artificial data to show the report format. "
            "Every number is invented. This is not evidence about any real "
            f"person.</p><p>{esc(ctx['synthetic_note'])}</p></div>"
        )

    chapters_html: list[str] = []
    for chapter in draft["chapters"]:
        headline = chapter["headline"]
        rows = "".join(
            "<tr><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td>"
            "<td>{}</td><td><span class='cls cls-{}'>{}</span></td>"
            "<td>{}</td></tr>".format(
                esc(p["pair_id"]),
                esc(p["pose_bin"]),
                _fmt(p["rmse_ioc"], 5),
                _fmt(p["coherence"], 2),
                _fmt(p["q_value"], 4),
                esc(p["evidence_class"]),
                esc(p["evidence_class"]),
                esc(p["status"]),
            )
            for p in chapter["pairs"]
        )
        zones = "".join(
            f"<li>{esc(z['sentence'])} <em>({esc(z['strength'])})</em></li>"
            for z in chapter["zones"]
        )
        reasons = "".join(f"<li>{esc(r)}</li>" for r in headline["reasons"])
        span = f" &middot; {chapter['years']} years" if chapter.get("years") else ""
        chapters_html.append(
            f"""<section class="chapter">
  <h3>{esc(chapter['start'])} &rarr; {esc(chapter['end'])}<span class="span">{span}</span></h3>
  <p class="headline s-{esc(headline['strength'])}">{esc(headline['sentence'])}</p>
  <p class="grade">Evidence: <strong>{esc(headline['strength'])}</strong> &mdash; {esc(headline['usage'])}</p>
  <details open><summary>Why this reading</summary><ul>{reasons}</ul></details>
  {f'<details open><summary>Where the movement sits</summary><ul>{zones}</ul></details>' if zones else ''}
  <details><summary>Underlying pairs ({len(chapter['pairs'])})</summary>
  <table><thead><tr><th>Pair</th><th>Angle group</th><th>Size (IOC)</th>
  <th>Coherence</th><th>q</th><th>Class</th><th>Status</th></tr></thead>
  <tbody>{rows}</tbody></table></details>
</section>"""
        )

    counters = "".join(
        "<tr class='{}'><td>{}</td><td>{}</td><td>{}{}</td></tr>".format(
            "" if c["controlled"] else "uncontrolled",
            esc(c["factor"]),
            esc(c["why_it_matters"]),
            "" if c["controlled"] else "<strong>NOT CONTROLLED. </strong>",
            esc(c["how_handled"]),
        )
        for c in draft["counter_explanations"]
    )
    limits = "".join(f"<li>{esc(x)}</li>" for x in draft["limitations"])
    cannot = "".join(f"<li>{esc(x)}</li>" for x in draft["cannot_conclude"])
    method = "".join(
        f"<li><strong>{esc(s['step'])}.</strong> {esc(s['text'])}</li>"
        for s in draft["method_plain"]
    )
    manifest = draft["manifest"]

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Facial geometry over time &mdash; working draft</title>
<style>
 :root {{ --bg:#faf9f7; --ink:#1a1a1a; --muted:#6b6b6b; --line:#e0ddd8;
         --strong:#8b2020; --moderate:#8a6d1f; --weak:#5a5a5a; --none:#2c6b45; }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; background:var(--bg); color:var(--ink);
        font:16px/1.65 Georgia,'Times New Roman',serif; }}
 .wrap {{ max-width:820px; margin:0 auto; padding:48px 24px 96px; }}
 h1 {{ font-size:2.1rem; line-height:1.2; margin:0 0 8px; }}
 h2 {{ font-size:1.4rem; margin:48px 0 16px; padding-bottom:8px;
       border-bottom:2px solid var(--line); }}
 h3 {{ font-size:1.15rem; margin:0 0 12px; }}
 .draft-tag {{ display:inline-block; font-family:ui-monospace,monospace;
   font-size:.72rem; letter-spacing:.08em; text-transform:uppercase;
   background:#1a1a1a; color:#fff; padding:4px 10px; border-radius:3px; }}
 .banner {{ background:#fff4e5; border:2px solid #d68910; border-radius:6px;
   padding:16px 20px; margin:0 0 32px; }}
 .banner strong {{ color:#a04000; letter-spacing:.05em; }}
 .banner p {{ margin:8px 0 0; font-size:.92rem; }}
 .lede {{ font-size:1.12rem; background:#fff; border-left:4px solid var(--ink);
   padding:18px 22px; margin:0 0 20px; }}
 .tally {{ font-size:.92rem; color:var(--muted); }}
 .chapter {{ background:#fff; border:1px solid var(--line); border-radius:6px;
   padding:22px 24px; margin:0 0 20px; }}
 .span {{ color:var(--muted); font-weight:400; font-size:.85rem; }}
 .headline {{ font-size:1.06rem; margin:0 0 8px; padding-left:12px;
   border-left:3px solid var(--weak); }}
 .headline.s-strong {{ border-color:var(--strong); }}
 .headline.s-moderate {{ border-color:var(--moderate); }}
 .headline.s-none {{ border-color:var(--none); }}
 .grade {{ font-size:.85rem; color:var(--muted); margin:0 0 14px; }}
 details {{ margin:10px 0; }}
 summary {{ cursor:pointer; font-size:.88rem; color:var(--muted);
   font-family:system-ui,sans-serif; }}
 table {{ width:100%; border-collapse:collapse; margin:12px 0;
   font:13px/1.5 ui-monospace,monospace; }}
 th,td {{ text-align:left; padding:7px 9px; border-bottom:1px solid var(--line); }}
 th {{ font-family:system-ui,sans-serif; font-size:.72rem; text-transform:uppercase;
   letter-spacing:.05em; color:var(--muted); }}
 .cls {{ padding:2px 7px; border-radius:3px; font-size:.72rem; }}
 .cls-primary {{ background:#e8f4ea; color:#1e5c38; }}
 .cls-limited {{ background:#fdf3e0; color:#8a6d1f; }}
 tr.uncontrolled {{ background:#fdf0f0; }}
 code {{ font-size:.85em; background:#f0eeea; padding:1px 5px; border-radius:3px; }}
 ul {{ padding-left:22px; }}
 li {{ margin:6px 0; }}
 .prov {{ font:13px/1.7 ui-monospace,monospace; color:var(--muted); }}
</style></head><body><div class="wrap">
{banner}
<span class="draft-tag">Working draft &mdash; not for publication</span>
<h1>Facial geometry over time: {esc(ctx['dataset_label'])}</h1>

<h2>The short version</h2>
<p class="lede">{esc(draft['bottom_line']['text'])}</p>
<p class="tally">Intervals examined: <strong>{draft['tally']['periods']}</strong> &middot;
 with a measurable change: <strong>{draft['tally']['reportable']}</strong> &middot;
 localised or weak only: <strong>{draft['tally']['localized_or_weak']}</strong> &middot;
 no change above noise: <strong>{draft['tally']['no_change']}</strong> &middot;
 not assessable: <strong>{draft['tally']['unusable']}</strong></p>

<h2>How this was measured</h2>
<ol>{method}</ol>

<h2>The chronology</h2>
{''.join(chapters_html) or '<p>No interval could be assembled from this photo set.</p>'}

<h2>What else could explain this</h2>
<table><thead><tr><th>Factor</th><th>Why it matters</th><th>How it was handled</th></tr></thead>
<tbody>{counters}</tbody></table>

<h2>Limitations</h2>
<ul>{limits}</ul>

<h2>What this analysis cannot establish</h2>
<ul>{cannot}</ul>

<h2>Provenance</h2>
<p class="prov">
schema: {esc(manifest['schema'])}<br>
config hash: {esc(str(manifest['config_hash']))}<br>
generated: {esc(str(manifest['generated_at']))}<br>
photos loaded: {manifest['stage1']['loaded']} &middot; failed: {manifest['stage1']['failed']}<br>
pairs measured: {manifest['pairs']['measured']} &middot; skipped: {manifest['pairs']['skipped']}
</p>
</div></body></html>"""


def write_draft(result, output_dir: Path, context: DraftContext) -> list[Path]:
    """Build and write the draft in all three formats."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    draft = build_draft(result, context)

    paths: list[Path] = []
    json_path = output_dir / "journalist_draft.json"
    json_path.write_text(
        json.dumps(draft, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    paths.append(json_path)

    md_path = output_dir / "journalist_draft.md"
    md_path.write_text(render_markdown(draft), encoding="utf-8")
    paths.append(md_path)

    html_path = output_dir / "journalist_draft.html"
    html_path.write_text(render_html(draft), encoding="utf-8")
    paths.append(html_path)

    return paths
