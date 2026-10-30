"""Chart-score harness: что рисует Timeline и как ведёт себя ряд.

B1: сейчас Timeline рисует per-photo значения реестра метрик в сыром
пространстве (`vertices`/`landmarks_render`), без center+IOD, normal,
калибровки и временного фильтра.

B2-B5: шаг хронологии считается через `server.chart` (тот же helper
`compute_heat_values`, что у heatmap): четыре режима, band/significance/z,
медианное окно только для отображения. Реальные события мимики ищутся по
ldm68-прокси (рот/улыбка/брови) при почти постоянной позе.

    python scripts/chart_score.py

Пишет reports/calibration/chart-sequences.json, reports/calibration-v4-chart.md
и reports/figures/v4-chart-raw-vs-filter.png. В приложение ничего не подключает.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import select_frames  # noqa: E402
from calibration_v3 import (  # noqa: E402
    family_of,
    index_rows,
    load_frames,
    topology,
)
from server import chart, storage  # noqa: E402

MODES = ("euclid", "normal", "weighted_euclid", "weighted_normal")
# z_mean — не отдельный расчёт: берётся из тех же строк chart.step, чтобы
# в таблице «raw / normal / weighted / z» z не отделялся от helper'а.
REPORT_MODES = MODES + ("z",)
FILTERS = (("raw", None), ("median3", 3), ("median5", 5))
# Поза считается постоянной, если yaw/pitch/roll не сдвинулись больше чем на это.
QUIET_POSE = 3.0
EVENT_POSE = 4.0
# Порог прокси мимики: доля от медианного шага по корпусу.
QUIET_EXPR = 1.5
EVENT_EXPR = 2.0
# События, проверенные глазами по кадрам: между ними меняется только мимика.
CONFIRMED_EVENTS = (
    ("person_04", 97, 102, "глаза закрыты (визуальная проверка)"),
    ("person_01", 318, 322, "глаза закрыты (визуальная проверка)"),
)
# Прокси-кандидаты, которые при визуальной проверке оказались не событиями.
REJECTED = {
    ("person_03", 128, 131): "кадры почти идентичны: прокси сработал на позе",
}


def ids_into(selected):
    known = {(p["group"], p["name"]): p
             for p in storage.read_db()["photos"] if not p.get("deleted_at")}
    for person, rows in selected.items():
        for row in rows:
            row["id"] = known[(person, row["path"].name)]["id"]
    return selected


def expression(frame, lm):
    """Прокси мимики по ldm68: раскрытие рта, улыбка, расстояние бровь-глаз."""
    p = frame["vertices"][lm]
    mouth = float(np.mean([np.linalg.norm(p[61] - p[67]),
                           np.linalg.norm(p[62] - p[66]),
                           np.linalg.norm(p[63] - p[65])]))
    smile = float(np.linalg.norm(p[60] - p[64]))
    brow = float(np.mean([np.linalg.norm(p[17 + i] - p[36 + i]) for i in range(5)]))
    return mouth, smile, brow


def pose_delta(a, b):
    return max(abs(b["yaw"] - a["yaw"]),
               abs(b["pitch"] - a["pitch"]),
               abs(b["roll"] - a["roll"]))


def person_sequences(frames):
    out = {}
    for frame in frames:
        out.setdefault(frame["person"], []).append(frame)
    for rows in out.values():
        rows.sort(key=lambda f: f["order"])
    return out


def person_pairs(per_person):
    """Соседние кадры человека; мост через невалидный кадр не строим."""
    return {person: [(a, b) for a, b in zip(rows, rows[1:], strict=False)
                     if a["order"] + 1 == b["order"]]
            for person, rows in per_person.items()}


def build_steps(per_person, pairs):
    """Шаги хронологии с прокси мимики и позой; score — доля от медианы корпуса."""
    steps = []
    for person, pr in pairs.items():
        for i, (a, b) in enumerate(pr):
            dm, ds, db = (abs(x - y) for x, y in
                          zip(a["expr"], b["expr"], strict=True))
            steps.append({"person": person, "index": i, "a": a, "b": b,
                          "dm": dm, "ds": ds, "db": db, "pose": pose_delta(a, b)})
    if not steps:
        return steps
    scale = np.maximum([np.median([s["dm"] for s in steps]),
                        np.median([s["ds"] for s in steps]),
                        np.median([s["db"] for s in steps])], 1e-6)
    for step in steps:
        step["score"] = max(step["dm"] / scale[0], step["ds"] / scale[1],
                            step["db"] / scale[2])
    return steps


def split_steps(steps):
    quiet = [s for s in steps if s["pose"] <= QUIET_POSE and s["score"] < QUIET_EXPR]
    events = [s for s in steps if s["pose"] <= EVENT_POSE and s["score"] >= EVENT_EXPR]
    events.sort(key=lambda s: s["score"], reverse=True)
    return quiet, events


def calm_sequence(per_person, pairs):
    """Самый ровный фронтальный участок: поза и мимика почти не меняются."""
    best = None
    for person in per_person:
        pr = pairs[person]
        for start in range(len(pr)):
            run = [pr[start]]
            for nxt in pr[start + 1:]:
                prev = run[-1]
                if prev[1] is not nxt[0]:
                    break
                if nxt[1]["bin"] != "frontal":
                    break
                if pose_delta(*nxt) > QUIET_POSE:
                    break
                dm, ds, _db = (abs(x - y) for x, y in
                               zip(nxt[0]["expr"], nxt[1]["expr"], strict=True))
                if dm > 0.008 or ds > 0.02:
                    break
                run.append(nxt)
            if len(run) >= 5:
                frames = [run[0][0]] + [pair[1] for pair in run]
                score = float(np.mean([pose_delta(*pair) for pair in run]))
                if best is None or score < best[0]:
                    best = (score, person, frames)
    if best is None:
        return None
    return {"type": "calm", "person": best[1], "frames": best[2],
            "note": "фронтальный участок, поза и мимика почти постоянны"}


def pose_sequence(per_person, pairs):
    """Смена ракурса без смены лица: профиль → фронтал → другой профиль."""
    best = None
    for person, rows in per_person.items():
        bins = {f["bin"] for f in rows}
        if not ({"left_profile", "right_profile"} & bins) or "frontal" not in bins:
            continue
        pr = pairs[person]
        if len(pr) < 10:
            continue
        score = float(np.median([pose_delta(*pair) for pair in pr]))
        if best is None or score > best[0]:
            best = (score, person)
    if best is None:
        return None
    rows = per_person[best[1]]
    return {"type": "pose_sweep", "person": best[1], "frames": rows,
            "note": "профиль → фронтал → противоположный профиль; обратного "
                    "фронтал → профиль → фронтал в корпусе нет"}


def confirmed_events(per_person, pairs):
    """События из CONFIRMED_EVENTS: окно 4 кадра, шаг события внутри окна."""
    out = []
    for person, fa, fb, note in CONFIRMED_EVENTS:
        rows = per_person.get(person) or []
        pos = {f["frame"]: k for k, f in enumerate(rows)}
        if fa not in pos or fb not in pos:
            continue
        i = pos[fa]
        start = max(0, i - 1)
        window = rows[start: i + 3]
        if len(window) < 3:
            continue
        step = next((s for s in range(len(pairs[person]))
                     if pairs[person][s][0]["frame"] == fa
                     and pairs[person][s][1]["frame"] == fb), None)
        if step is None:
            continue
        out.append({"type": "real_event", "person": person, "frames": window,
                    "event_step": i - start, "step_index": step,
                    "pose_delta": round(pose_delta(rows[i], rows[i + 1]), 2),
                    "note": note})
    return out


def rows_for(frames, tri, mode_name):
    cfg = chart.mode(mode_name)
    rows = []
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        row = chart.step(a["vertices"], b["vertices"], tri, cfg)
        row.update({
            "from": a["frame"],
            "to": b["frame"],
            "pose_transition": family_of(a["bin"], b["bin"]),
            "yaw_delta": round(float(b["yaw"] - a["yaw"]), 2),
            "pose_delta": round(pose_delta(a, b), 2),
        })
        rows.append(row)
    return cfg, rows


def full_series(per_person, pairs, tri, mode_name):
    """Полный ряд человека по всем соседним кадрам — для порогов и фильтра."""
    cfg = chart.mode(mode_name)
    out = {}
    for person, pr in pairs.items():
        out[person] = [chart.step(a["vertices"], b["vertices"], tri, cfg)
                       for a, b in pr]
    return out


def filtered(raw, window):
    values = [r["value_raw"] for r in raw]
    return values if window is None else chart.median_window(values, window)


def displays(rows):
    out = {"raw": [r["value_raw"] for r in rows]}
    for name, window in FILTERS:
        if window is None:
            continue
        out[name] = chart.median_window(out["raw"], window)
    return out


def autocorr(values):
    v = np.asarray(values, np.float64)
    if v.size < 3 or np.std(v) == 0:
        return None
    return round(float(np.corrcoef(v[:-1], v[1:])[0, 1]), 3)


def robust(values):
    v = np.asarray(values, np.float64)
    median = float(np.median(v))
    mad = float(np.median(np.abs(v - median)))
    return {"n": int(v.size), "median": round(median, 6), "mad": round(mad, 6),
            "std": round(float(v.std()), 6),
            "threshold": round(median + 3 * mad, 6),
            "autocorr_lag1": autocorr(v)}


def quiet_stats(series, quiet, mode):
    """Фоновые шаги: порог и ложные пики для каждого варианта фильтра."""
    out = {}
    for name, window in FILTERS:
        values = []
        for step in quiet:
            filtered_values = filtered(series[(step["person"], mode)], window)
            values.append(filtered_values[step["index"]])
        stats = robust(values)
        stats["false_peaks"] = int(sum(1 for v in values if v > stats["threshold"]))
        stats["false_peak_rate"] = round(stats["false_peaks"] / max(stats["n"], 1), 3)
        out[name] = stats
    return out


def sequence_stats(computed, quiet_stats_by_mode, events):
    """Свойства ряда по серии: спокойствие, реакция на ракурс, события."""
    stats = {}
    for name, data in computed.items():
        if name.startswith("_"):
            continue
        stats[name] = {}
        kind = data["seq"]["type"]
        for mode in REPORT_MODES:
            stats[name][mode] = {}
            for filt, _window in FILTERS:
                values = data["variants"][mode][filt]
                threshold = quiet_stats_by_mode[mode][filt]["threshold"]
                row = {}
                if kind == "calm":
                    row.update({"std": round(float(np.std(values)), 6),
                                "false_peaks": int(sum(1 for v in values if v > threshold))})
                elif kind == "pose_sweep":
                    pure = [v for v, s in zip(values, data["steps"], strict=True)
                            if s["pose"] >= 5.0]
                    row["peak_ratio"] = round(
                        float(max(pure) / max(quiet_stats_by_mode[mode][filt]["median"], 1e-9)), 3
                    ) if pure else None
                    row["above"] = int(sum(1 for v in pure if v > threshold)) if pure else None
                elif kind == "real_event":
                    step = data["seq"]["event_step"]
                    row["event_value"] = round(float(values[step]), 6)
                    row["above"] = bool(values[step] > threshold)
                stats[name][mode][filt] = row
    # Событие считается «взятым», если его шаг в полном ряду выше фонового порога.
    events_summary = {}
    for mode in REPORT_MODES:
        events_summary[mode] = {}
        for filt, _window in FILTERS:
            hits = []
            for step in events:
                values = filtered(computed["_series"][(step["person"], mode)], _window)
                hits.append(bool(values[step["index"]] >
                                 quiet_stats_by_mode[mode][filt]["threshold"]))
            events_summary[mode][filt] = {
                "n": len(hits), "above": int(sum(hits)),
                "sensitivity": round(float(np.mean(hits)), 3) if hits else None}
    return stats, events_summary


def spike_test(raw, threshold):
    """Одиночный пик размером с событие: сохраняет ли его медианное окно."""
    values = list(raw)
    index = len(values) // 2
    amplitude = max(3 * threshold, 0.02)
    values[index] = values[index] + amplitude
    out = {"index": index, "amplitude": round(amplitude, 6),
           "raw_spike": round(values[index], 6), "threshold": round(threshold, 6)}
    for name, window in FILTERS:
        if window is None:
            out[name] = round(values[index], 6)
            continue
        result = chart.median_window(values, window)
        out[name] = round(result[index], 6)
        out[f"{name}_above"] = bool(result[index] > threshold)
    return out


def figure(series, thresholds, out_dir: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    names = [name for name in ("calm", "pose_sweep", "real_event", "real_event_2")
             if name in series]
    if not names:
        return []
    fig, axes = plt.subplots(len(names), 1, figsize=(11.5, 2.7 * len(names)), dpi=130)
    if len(names) == 1:
        axes = [axes]
    for ax, name in zip(axes, names, strict=True):
        seq = series[name]
        x = np.arange(len(seq["rows"]["euclid"]))
        ax.plot(x, seq["rows"]["euclid"], color="#9aa7b0", lw=0.9,
                label="euclid raw")
        ax.plot(x, seq["rows"]["weighted_euclid"], color="#2f7fb0", lw=1.5,
                label="weighted_euclid raw")
        ax.plot(x, seq["rows"]["weighted_euclid_median3"], color="#e05c5c", lw=1.3,
                label="weighted_euclid median3")
        ax.axhline(thresholds["weighted_euclid"], color="#e05c5c", lw=0.8,
                   ls="--", label="порог фон + 3·MAD")
        ax.fill_between(x, np.asarray(seq["rows"]["weighted_euclid"]) - np.asarray(seq["band"]),
                        np.asarray(seq["rows"]["weighted_euclid"]) + np.asarray(seq["band"]),
                        color="#2f7fb0", alpha=0.12, label="band")
        for k in range(len(x)):
            ax.axvline(k, color="#20303e", lw=0.3, alpha=0.2)
        ax.set_title(f"{name}: {seq['person']} · {seq['note']}", fontsize=9)
        ax.set_ylabel("value", fontsize=8)
        ax.legend(fontsize=7, ncol=2)
    axes[-1].set_xlabel("шаг хронологии", fontsize=8)
    fig.tight_layout()
    path = out_dir / "v4-chart-raw-vs-filter.png"
    fig.savefig(path)
    plt.close(fig)
    return [{"file": str(path.relative_to(ROOT)),
             "caption": "Ряд графика: euclid raw, weighted_euclid raw и median3, "
                        "band и фоновый порог"}]


def write_report(path: Path, payload: dict):
    lines = ["# Chart-score: что рисует Timeline", ""]
    lines += [
        "B1. Сейчас `Timeline.tsx` рисует **per-photo значения реестра метрик**",
        "(`rows[].metrics[id].value`) в сыром пространстве `vertices`/`landmarks_render`,",
        "без center+IOD, без normal, без калибровки и без временного фильтра.",
        "Режимы `value` / `z` (MAD z внутри группы и позы) / `delta` — три",
        "представления одного и того же сырого ряда. `variant=\"morph\"`",
        "переиспользует те же дорожки, добавляя ключевые кадры и скраббер.",
        "",
        "Ниже — шаг хронологии через `server.heat.compute_heat_values` (center+IOD)",
        "и агрегаты `server/chart.py`. Новых формул нет; фильтр только для отображения.",
        "",
        "## Тестовые серии",
        "",
        "| тип | персона | кадров | поза | примечание |",
        "|---|---|---|---|---|",
    ]
    for name, seq in payload["sequences"].items():
        frames = seq["frames"]
        yaw = f"{min(f['yaw'] for f in frames):.0f}…{max(f['yaw'] for f in frames):.0f}°"
        pose = seq.get("pose_delta")
        if pose is not None:
            yaw = f"Δ {pose}°"
        lines.append(f"| {name} | {seq['person']} | {len(seq['rows']) + 1} | {yaw} "
                     f"| {seq['note']} |")
    lines += ["", "## Фон: спокойные шаги всего корпуса", "",
              f"Шаги с |Δyaw|, |Δpitch|, |Δroll| ≤ {payload['constants']['quiet_pose']}° "
              f"и прокси мимики < {payload['constants']['quiet_expr']}·медианы.", "",
              "| режим | фильтр | шагов | медиана | MAD | порог | ложные пики | доля |",
              "|---|---|---|---|---|---|---|---|"]
    for mode in REPORT_MODES:
        for filt, _window in FILTERS:
            row = payload["quiet"][mode][filt]
            lines.append(
                f"| {mode} | {filt} | {row['n']} | {row['median']} | {row['mad']} "
                f"| {row['threshold']} | {row['false_peaks']} "
                f"| {row['false_peak_rate']:.1%} |")
    pose = payload["stats"].get("pose_sweep") or {}
    calm0 = payload["stats"].get("calm") or {}
    lines += ["", "## Свод: raw / normal / weighted / z", "",
              "Все колонки — без фильтра (raw-ряд); z — агрегат в единицах шума.", "",
              "| ряд | фон медиана | фон MAD | ложные пики | calm std | пик/фон | чувствительность |",
              "|---|---|---|---|---|---|---|"]
    for mode in REPORT_MODES:
        quiet = payload["quiet"][mode]["raw"]
        calm_std = (calm0.get(mode) or {}).get("raw", {}).get("std")
        peak = (pose.get(mode) or {}).get("raw", {}).get("peak_ratio")
        sens = payload["events"]["summary"][mode]["raw"]["sensitivity"]
        lines.append(f"| {mode} | {quiet['median']} | {quiet['mad']} "
                     f"| {quiet['false_peaks']} | {calm_std} | {peak} | {sens} |")
    lines += ["", "## Спокойный участок", "",
              "| серия | режим | фильтр | std | ложные пики | автокорр |",
              "|---|---|---|---|---|---|"]
    calm = payload["stats"].get("calm") or {}
    for mode in REPORT_MODES:
        for filt, _window in FILTERS:
            st = calm.get(mode, {}).get(filt, {})
            lines.append(f"| calm | {mode} | {filt} | {st.get('std')} "
                         f"| {st.get('false_peaks')} | "
                         f"{payload['quiet'][mode][filt]['autocorr_lag1']} |")
    pose = payload["stats"].get("pose_sweep") or {}
    lines += ["", "## Смена ракурса", "",
              "| режим | фильтр | пик/фон | шагов выше порога |",
              "|---|---|---|---|"]
    for mode in REPORT_MODES:
        for filt, _window in FILTERS:
            st = pose.get(mode, {}).get(filt, {})
            lines.append(f"| {mode} | {filt} | {st.get('peak_ratio')} "
                         f"| {st.get('above')} |")
    lines += ["", "## Реальные события мимики", "",
              "Два события подтверждены визуально по кадрам (глаза закрываются при "
              "почти постоянной позе). Именно они используются для чувствительности.",
              "",
              "| событие | кадры | Δ позы | euclid raw | w-euclid raw | w-euclid median3 | w-euclid median5 |",
              "|---|---|---|---|---|---|---|"]
    for event in payload["events"]["list"]:
        lines.append(
            f"| {event['person']} | {event['from']}→{event['to']} "
            f"| {event['pose_delta']} | {event['euclid']} | {event['weighted_euclid']} "
            f"| {event['weighted_euclid_median3']} | {event['weighted_euclid_median5']} |")
    lines += ["", "| режим | фильтр | событий | выше порога | чувствительность |",
              "|---|---|---|---|---|"]
    for mode in REPORT_MODES:
        for filt, _window in FILTERS:
            row = payload["events"]["summary"][mode][filt]
            lines.append(f"| {mode} | {filt} | {row['n']} | {row['above']} "
                         f"| {row['sensitivity']} |")
    proxy = payload["events"].get("proxy") or {}
    if proxy.get("list"):
        lines += ["", "### Автоматические кандидаты (прокси, не подтверждены)", "",
                  f"Кандидатов {proxy['n']}: поза ≤ {payload['constants']['event_pose']}°, "
                  f"прокси ≥ {payload['constants']['event_expr']}·медианы. Прокси зависит от "
                  "позы, поэтому список содержит ложные срабатывания; для гейта он не используется.",
                  "",
                  "| событие | Δ позы | score | euclid raw | w-euclid raw | визуальная проверка |",
                  "|---|---|---|---|---|---|"]
        for event in proxy["list"]:
            lines.append(
                f"| {event['person']} {event['from']}→{event['to']} | {event['pose_delta']} "
                f"| {event['score']} | {event['euclid']} | {event['weighted_euclid']} "
                f"| {event.get('visual', 'не проверялось')} |")
        lines += ["", "| режим | фильтр | кандидатов | выше порога | доля |",
                  "|---|---|---|---|---|"]
        for mode in REPORT_MODES:
            for filt, _window in FILTERS:
                row = proxy["summary"][mode][filt]
                lines.append(f"| {mode} | {filt} | {row['n']} | {row['above']} "
                             f"| {row['sensitivity']} |")
    lines += ["", "## Одиночный синтетический пик", "",
              "Пик размером max(3·порог, 0.02) добавлен в спокойную серию;",
              "медианное окно — медиана соседей, поэтому одиночный шаг оно убирает.", "",
              "| режим | амплитуда | raw | median3 | median5 | median3 выше порога |",
              "|---|---|---|---|---|---|"]
    for mode, spike in payload["spikes"].items():
        lines.append(f"| {mode} | {spike['amplitude']} | {spike['raw']} "
                     f"| {spike['median3']} | {spike['median5']} "
                     f"| {spike['median3_above']} |")
    lines += ["", "## Вывод", ""]
    lines += [f"- {line}" for line in payload["conclusion"]]
    lines += ["", "## Файлы", ""]
    for item in payload["files"]:
        lines.append(f"- `{item['file']}` — {item['caption']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def conclusion(payload):
    lines = []
    quiet = payload["quiet"]
    base = quiet["euclid"]["raw"]
    lines.append(
        f"Фон ({base['n']} шагов, euclid): медиана {base['median']}, MAD {base['mad']}, "
        f"порог {base['threshold']}; ложных пиков raw {base['false_peaks']}.")
    best = min(MODES, key=lambda m: quiet[m]["raw"]["false_peaks"])
    lines.append(f"Меньше всего ложных пиков на фоне: {best} "
                 f"({quiet[best]['raw']['false_peaks']} из {quiet[best]['raw']['n']}).")
    med3 = {m: quiet[m]["median3"]["false_peaks"] for m in MODES}
    lines.append("median3 снижает ложные пики до " +
                 ", ".join(f"{m} {v}" for m, v in med3.items()) +
                 ", но съедает одиночный шаг: " +
                 ", ".join(f"{m} {payload['spikes'][m]['median3_above']}" for m in MODES) + ".")
    ev = payload["events"]["summary"]
    lines.append("Чувствительность на 2 подтверждённых событиях, raw: " +
                 ", ".join(f"{m} {ev[m]['raw']['sensitivity']}" for m in MODES) +
                 "; median3: " +
                 ", ".join(f"{m} {ev[m]['median3']['sensitivity']}" for m in MODES) + ".")
    proxy = payload["events"].get("proxy") or {}
    if proxy.get("summary"):
        lines.append(
            f"Прокси-кандидатов {proxy['n']}, но минимум один при проверке оказался не "
            f"событием: прокси зависит от позы. Для гейта используется только "
            f"подтверждённая пара.")
    pose = payload["stats"].get("pose_sweep") or {}
    ratio = {m: (pose.get(m, {}).get("raw") or {}).get("peak_ratio") for m in MODES}
    lines.append("Пик/фон на смене ракурса (raw): " +
                 ", ".join(f"{m} {v}" for m, v in ratio.items()) +
                 ". Смена ракурса остаётся самым большим пиком графика.")
    lines.append("Рекомендация: рисовать raw-ряд (weighted_euclid как кандидат), "
                 "показывать band/significance из профиля и не включать median-фильтр: "
                 "он удаляет реальные одношаговые события (моргание, смена мимики).")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--out", type=Path, default=ROOT / "reports/calibration-v4-chart.md")
    ap.add_argument("--json", type=Path,
                    default=ROOT / "reports/calibration/chart-sequences.json")
    ap.add_argument("--figures", type=Path, default=ROOT / "reports/figures")
    ap.add_argument("--write-band", action="store_true",
                    help="Записать chart_band в профиль калибровки")
    args = ap.parse_args()

    index_path = args.calibration_root / "all_calibration_index.csv"
    index = index_rows(index_path)
    selected = ids_into(select_frames(index_path, args.photos_root, args.per_person))
    tri, lm = topology()
    frames = [f for f in load_frames(selected, index, tri, lm, {}) if f["valid"]]
    for frame in frames:
        frame["expr"] = expression(frame, lm)
    per_person = person_sequences(frames)
    pairs = person_pairs(per_person)
    steps = build_steps(per_person, pairs)
    quiet, events = split_steps(steps)
    if not quiet:
        raise SystemExit("нет спокойных шагов для фонового порога")

    series_source = {mode: full_series(per_person, pairs, tri, mode) for mode in MODES}
    # z-ряд: тот же шаг, но агрегат в единицах шума (z_mean).
    series_source["z"] = {
        person: [{"value_raw": row["z_mean"]} for row in rows]
        for person, rows in series_source["euclid"].items()
    }
    quiet_values = {mode: quiet_stats({(person, mode): rows
                                       for person, rows in series_source[mode].items()},
                                      quiet, mode)
                    for mode in REPORT_MODES}
    if args.write_band:
        profile = Path(chart.settings()["calibration_profile"])
        profile = profile if profile.is_absolute() else ROOT / profile
        doc = json.loads(profile.read_text(encoding="utf-8"))
        doc["chart_band"] = {mode: round(quiet_values[mode]["raw"]["median"], 8)
                             for mode in MODES}
        profile.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print("chart_band", doc["chart_band"])

    sequences = [s for s in (calm_sequence(per_person, pairs),
                             pose_sequence(per_person, pairs)) if s]
    confirmed = confirmed_events(per_person, pairs)
    sequences.extend(confirmed)
    if not sequences:
        raise SystemExit("не удалось собрать ни одной серии")
    lookup = {(s["person"], s["index"]): s for s in steps}
    confirmed_steps = [lookup[(seq["person"], seq["step_index"])] for seq in confirmed]

    payload = {"dataset": {"frames": len(frames), "people": len(per_person),
                           "steps": len(steps), "quiet": len(quiet),
                           "events": len(confirmed_steps), "proxy_events": len(events)},
               "constants": {"quiet_pose": QUIET_POSE, "quiet_expr": QUIET_EXPR,
                             "event_pose": EVENT_POSE, "event_expr": EVENT_EXPR},
               "sequences": {}, "stats": {}, "quiet": quiet_values,
               "events": {"list": [], "summary": {}, "proxy": {}},
               "spikes": {}, "files": []}
    computed = {"_series": {(person, mode): rows
                            for mode, by_person in series_source.items()
                            for person, rows in by_person.items()}}
    for seq in sequences:
        name = seq["type"]
        if name in computed:
            name = f"real_event_{len([k for k in computed if k.startswith('real_event')]) + 1}"
        cfg_by_mode, rows_by_mode, variants = {}, {}, {}
        for mode in MODES:
            cfg, rows = rows_for(seq["frames"], tri, mode)
            cfg_by_mode[mode] = {"metric": cfg["metric"], "weighting": cfg["weighting"]}
            rows_by_mode[mode] = rows
            variants[mode] = displays(rows)
        rows_by_mode["z"] = [{"value_raw": row["z_mean"]}
                             for row in rows_by_mode["euclid"]]
        variants["z"] = displays(rows_by_mode["z"])
        entries = [s for s in steps if s["person"] == seq["person"]
                   and any(s["a"]["frame"] == a["frame"] and s["b"]["frame"] == b["frame"]
                           for a, b in zip(seq["frames"], seq["frames"][1:], strict=False))]
        computed[name] = {"seq": seq, "rows": rows_by_mode, "variants": variants,
                          "steps": entries}
        entry = {"type": seq["type"], "person": seq["person"], "note": seq.get("note", ""),
                 "pose_delta": seq.get("pose_delta"),
                 "proxy_delta": seq.get("proxy_delta"), "event_step": seq.get("event_step"),
                 "frames": [{"frame": f["frame"], "bin": f["bin"],
                             "yaw": round(f["yaw"], 2)} for f in seq["frames"]],
                 "modes": cfg_by_mode, "rows": [], "stats": {}}
        for i, row in enumerate(rows_by_mode["euclid"]):
            entry["rows"].append({
                "from": row["from"], "to": row["to"],
                "pose_transition": row["pose_transition"],
                "yaw_delta": row["yaw_delta"], "pose_delta": row["pose_delta"],
                "by_mode": {m: {k: rows_by_mode[m][i][k] for k in
                                ("value_raw", "band", "significance", "z_mean",
                                 "z_p95", "frac_z_gt3", "low_confidence_fraction")}
                            for m in MODES},
            })
        payload["sequences"][name] = entry

    stats, event_summary = sequence_stats(computed, quiet_values, confirmed_steps)
    payload["stats"] = stats
    payload["events"]["summary"] = event_summary
    for seq, step in zip(confirmed, confirmed_steps, strict=True):
        values = {(mode, filt): filtered(computed["_series"][(step["person"], mode)],
                                         _window)[step["index"]]
                  for mode in MODES for filt, _window in FILTERS}
        payload["events"]["list"].append({
            "person": step["person"], "from": step["a"]["frame"],
            "to": step["b"]["frame"], "pose_delta": round(step["pose"], 2),
            "note": seq["note"], "score": None,
            "euclid": round(values[("euclid", "raw")], 6),
            "weighted_euclid": round(values[("weighted_euclid", "raw")], 6),
            "weighted_euclid_median3": round(values[("weighted_euclid", "median3")], 6),
            "weighted_euclid_median5": round(values[("weighted_euclid", "median5")], 6),
        })
    proxy_hits = []
    for step in events:
        values = {(mode, filt): filtered(computed["_series"][(step["person"], mode)],
                                         _window)[step["index"]]
                  for mode in MODES for filt, _window in FILTERS}
        entry = {"person": step["person"], "from": step["a"]["frame"],
                 "to": step["b"]["frame"], "pose_delta": round(step["pose"], 2),
                 "score": round(float(step["score"]), 2),
                 "euclid": round(values[("euclid", "raw")], 6),
                 "weighted_euclid": round(values[("weighted_euclid", "raw")], 6)}
        rejected = REJECTED.get((step["person"], step["a"]["frame"], step["b"]["frame"]))
        if rejected:
            entry["visual"] = rejected
        proxy_hits.append(entry)
    proxy_summary = {}
    for mode in REPORT_MODES:
        proxy_summary[mode] = {}
        for filt, _window in FILTERS:
            hits = [bool(filtered(computed["_series"][(step["person"], mode)],
                                  _window)[step["index"]] >
                        quiet_values[mode][filt]["threshold"]) for step in events]
            proxy_summary[mode][filt] = {
                "n": len(hits), "above": int(sum(hits)),
                "sensitivity": round(float(np.mean(hits)), 3) if hits else None}
    payload["events"]["proxy"] = {"n": len(proxy_hits), "list": proxy_hits[:8],
                                   "summary": proxy_summary}

    calm = computed.get("calm")
    for mode in REPORT_MODES:
        if not calm:
            break
        raw = [r["value_raw"] for r in calm["rows"][mode]]
        payload["spikes"][mode] = spike_test(
            raw, quiet_values[mode]["raw"]["threshold"])

    series_for_figure = {}
    for name in ("calm", "pose_sweep", "real_event", "real_event_2"):
        if name not in computed:
            continue
        rows = computed[name]["rows"]
        series_for_figure[name] = {
            "person": computed[name]["seq"]["person"],
            "note": computed[name]["seq"].get("note", ""),
            "rows": {"euclid": [r["value_raw"] for r in rows["euclid"]],
                     "weighted_euclid": [r["value_raw"] for r in rows["weighted_euclid"]],
                     "weighted_euclid_median3":
                         computed[name]["variants"]["weighted_euclid"]["median3"]},
            "band": [r["band"] or 0 for r in rows["weighted_euclid"]],
        }
    thresholds = {mode: quiet_values[mode]["raw"]["threshold"] for mode in MODES}
    payload["files"] = figure(series_for_figure, thresholds, args.figures)
    payload.pop("_series", None)
    payload["conclusion"] = conclusion(payload)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str),
                         encoding="utf-8")
    write_report(args.out, payload)
    print("sequences", {k: len(v["rows"]) for k, v in payload["sequences"].items()})
    print("events", len(events), "quiet", len(quiet))
    print("report", args.out)


if __name__ == "__main__":
    main()
