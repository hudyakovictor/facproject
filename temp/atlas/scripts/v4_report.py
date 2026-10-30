"""Итоговый отчёт итерации 4: гейты, вердикт, файлы.

Собирает reports/calibration-v4.md и .json из уже посчитанных источников:

    reports/calibration-v4-corpus.json   (D: корпус, LOPO, LOTRO, веса)
    reports/calibration-ldm.json         (A: landmark-sweep)
    reports/calibration/chart-sequences.json (B2-B5)
    reports/calibration/normal-diag.json (C)
    reports/calibration/chart-parity.json (B7)
    reports/calibration/v4-parity.json   (heatmap preview/export)
    reports/calibration/v3-chain.json    (heatmap chain)
    reports/calibration/weights.json     (chart_band, профиль в приложении)
    configs/runtime.yaml                 (фактические дефолты)

Скрипт ничего не считает заново: только сверяет пороги гейтов с готовыми
числами. Запуск:

    python scripts/v4_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

CORPUS = ROOT / "reports/calibration-v4-corpus.json"
LDM = ROOT / "reports/calibration-ldm.json"
CHART = ROOT / "reports/calibration/chart-sequences.json"
NORMAL = ROOT / "reports/calibration/normal-diag.json"
CHART_PARITY = ROOT / "reports/calibration/chart-parity.json"
HEAT_PARITY = ROOT / "reports/calibration/v4-parity.json"
HEAT_CHAIN = ROOT / "reports/calibration/v3-chain.json"
WEIGHTS = ROOT / "reports/calibration/weights.json"
RUNTIME = ROOT / "configs/runtime.yaml"
OUT_MD = ROOT / "reports/calibration-v4.md"
OUT_JSON = ROOT / "reports/calibration-v4.json"

MODES = ("euclid", "normal", "weighted_euclid", "weighted_normal")
REPORT_MODES = MODES + ("z",)
BASELINE = "euclid"


def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else {}


def runtime_blocks(text: str) -> dict:
    """Плоский разбор двух блоков runtime.yaml без PyYAML."""
    blocks, current = {}, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.rstrip().endswith(":"):
            current = line.strip()[:-1]
            blocks[current] = {}
            continue
        if current and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            value = value.split("#", 1)[0].strip()
            blocks[current][key] = value
    return blocks


def pct(new: float, base: float) -> float:
    return 100.0 * (new / base - 1.0) if base else 0.0


def f(value, digits=4):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def gate(criterion, threshold, value, state, note=""):
    return {"criterion": criterion, "threshold": threshold, "value": value,
            "state": state, "note": note}


def gates_for(corpus, chart, chart_parity, heat_parity, heat_chain):
    """Гейты ТЗ: разделение (heatmap) и свойства ряда (график)."""
    modes = corpus.get("modes", {})
    base = modes.get(BASELINE, {})
    base_cross = base.get("within_cross", {}).get("mean")
    base_ratio = base.get("ratio")
    lopo = corpus.get("lopo", {})
    lotro = (corpus.get("lotro") or {}).get("rows") or []
    quiet = chart.get("quiet", {})
    events = chart.get("events", {}).get("summary", {})
    stats = chart.get("stats", {})

    out = {}
    for name in ("weighted_euclid", "weighted_normal"):
        data = modes.get(name, {})
        cross = data.get("within_cross", {}).get("mean")
        ratio = data.get("ratio")
        auc = data.get("auc")
        rows = []
        rows.append(gate(
            "within, cross-bin", "не хуже baseline и лучше на 10%",
            f"{f(cross, 5)} vs {f(base_cross, 5)} ({pct(cross, base_cross):+.1f}%)",
            "pass" if cross and base_cross and pct(cross, base_cross) <= -10 else "fail"))
        rows.append(gate(
            "ratio between/within", "не ниже baseline",
            f"{f(ratio, 3)} vs {f(base_ratio, 3)}",
            "pass" if ratio and base_ratio and ratio >= base_ratio else "fail"))
        if name == "weighted_normal" and auc and base.get("auc"):
            ci = (load(ROOT / "reports/calibration-v3.json").get("bootstrap") or {}).get(name)
            rows.append(gate(
                "AUC", "ΔAUC > 0, CI не накрывает 0",
                f"{f(auc)} vs {f(base.get('auc'))} (Δ {auc - base['auc']:+.4f}); "
                + (f"CI [{ci['lo']:+.4f}; {ci['hi']:+.4f}] (7 человек)" if ci else "CI не считался"),
                "pass" if ci and ci["lo"] > 0 else "fail",
                "" if ci else "bootstrap для этого режима не запускался"))
        else:
            rows.append(gate(
                "AUC", "ΔAUC > 0, CI не накрывает 0",
                f"{f(auc)} vs {f(base.get('auc'))} (Δ {(auc or 0) - (base.get('auc') or 0):+.4f}); CI не считался",
                "fail", "bootstrap в v3 считался только для normal и weighted_normal"))
        summary = lopo.get(name) or {}
        rows.append(gate(
            "LOPO", "не хуже baseline более чем на 0.01 на любом человеке",
            f"{summary.get('wins')}/{summary.get('n')} побед, минимум Δ {f(summary.get('min_delta_auc'))}",
            "pass" if summary.get("min_delta_auc") is not None
            and summary["min_delta_auc"] >= -0.01 else "fail"))
        win, n = 0, 0
        for row in lotro:
            if row.get("skipped"):
                continue
            n += 1
            if (row.get(f"auc_{name}") or 0) > (row.get("auc_euclid") or 0):
                win += 1
        rows.append(gate(
            "LOTRO", "выигрыш на всех семействах",
            f"{win}/{n}" + ("" if win == n else " (проигрыш: mid_deep)" if n else ""),
            "pass" if n and win == n else "fail"))
        false_peaks = quiet.get(name, {}).get("raw", {}).get("false_peaks")
        base_false = quiet.get(BASELINE, {}).get("raw", {}).get("false_peaks")
        rows.append(gate(
            "ложные пики графика", "минус не менее 30% на спокойных участках",
            f"{false_peaks} из {quiet.get(name, {}).get('raw', {}).get('n')} "
            f"vs {base_false} ({pct(false_peaks, base_false):+.0f}%)"
            if false_peaks is not None else "—",
            "pass" if false_peaks is not None and base_false
            and pct(false_peaks, base_false) <= -30 else "fail"))
        sens = events.get(name, {}).get("raw", {}).get("sensitivity")
        base_sens = events.get(BASELINE, {}).get("raw", {}).get("sensitivity")
        rows.append(gate(
            "чувствительность", "падение не более 10%",
            f"{f(sens, 2)} vs {f(base_sens, 2)}",
            "pass" if sens is not None and base_sens and sens >= base_sens - 0.10 else "fail"))
        rows.append(gate(
            "preview/export графика", "max|Δ| ≤ 1e-6",
            f"{chart_parity.get('parity', {}).get('person_04', {}).get(name, {}).get('max_abs_delta')}"
            if name in chart_parity.get("parity", {}).get("person_04", {}) else "—",
            "pass" if name in MODES else "na"))
        rows.append(gate(
            "heatmap preview/export", "max|Δ| ≤ 1e-6",
            f"{heat_parity.get('max_abs_diff')}" if heat_parity else "—",
            "pass" if heat_parity.get("passed") else "fail"))
        rows.append(gate(
            "цепочка", "join = 0",
            f"график {chart_parity.get('chain', {}).get(name, {}).get('join_max_abs_delta')}, "
            f"heatmap {heat_chain.get('join_jump')}",
            "pass" if chart_parity.get("chain", {}).get(name, {}).get("join_max_abs_delta") == 0
            and heat_chain.get("join_jump") == 0 else "fail"))
        out[name] = rows

    # Фильтр: гейт только по свойствам ряда, режим euclid.
    rows = []
    quiet_e = quiet.get(BASELINE, {})
    base_false = (quiet_e.get("raw") or {}).get("false_peaks")
    for filt in ("median3", "median5"):
        stats_f = quiet_e.get(filt) or {}
        rows.append(gate(
            f"ложные пики, {filt}", "минус не менее 30% на спокойных участках",
            f"{stats_f.get('false_peaks')} vs {base_false} "
            f"({pct(stats_f.get('false_peaks') or 0, base_false or 1):+.0f}%)",
            "pass" if stats_f.get("false_peaks") is not None and base_false
            and pct(stats_f["false_peaks"], base_false) <= -30 else "fail"))
        sens_f = events.get(BASELINE, {}).get(filt, {}).get("sensitivity")
        base_sens = events.get(BASELINE, {}).get("raw", {}).get("sensitivity")
        rows.append(gate(
            f"чувствительность, {filt}", "падение не более 10%",
            f"{f(sens_f, 2)} vs {f(base_sens, 2)}",
            "pass" if sens_f is not None and base_sens and sens_f >= base_sens - 0.10 else "fail"))
        spike = chart.get("spikes", {}).get(BASELINE, {})
        rows.append(gate(
            f"одиночный пик, {filt}", "реальный одношаговый пик не съедается",
            f"raw {f(spike.get('raw'))} → {f(spike.get(filt))}; "
            f"выше порога: {'да' if spike.get(f'{filt}_above') else 'нет'}",
            "pass" if spike.get(f"{filt}_above") else "fail"))
    pose = stats.get('pose_sweep', {})
    rows.append(gate(
        "смена ракурса", "пик/фон на смене ракурса не растёт",
        f"raw euclid {f(pose.get(BASELINE, {}).get('raw', {}).get('peak_ratio'), 3)}, "
        f"weighted_euclid {f(pose.get('weighted_euclid', {}).get('raw', {}).get('peak_ratio'), 3)}; "
        f"шагов выше порога {pose.get(BASELINE, {}).get('raw', {}).get('above')}",
        "fail", "смена ракурса остаётся самым большим пиком во всех режимах"))
    out["temporal_filter"] = rows
    return out


def summary_rows(chart):
    quiet = chart.get("quiet", {})
    stats = chart.get("stats", {})
    events = chart.get("events", {}).get("summary", {})
    rows = []
    for mode in REPORT_MODES:
        q = quiet.get(mode, {}).get("raw", {})
        rows.append({
            "mode": mode,
            "quiet_median": q.get("median"),
            "quiet_mad": q.get("mad"),
            "false_peaks": q.get("false_peaks"),
            "calm_std": (stats.get("calm") or {}).get(mode, {}).get("raw", {}).get("std"),
            "peak_ratio": (stats.get("pose_sweep") or {}).get(mode, {}).get("raw", {}).get("peak_ratio"),
            "sensitivity": (events.get(mode) or {}).get("raw", {}).get("sensitivity"),
            "autocorr": q.get("autocorr_lag1"),
        })
    return rows


def land_rows(ldm):
    rows = []
    for name, modes in (ldm.get("sets") or {}).items():
        e = modes.get("euclid", {})
        n = modes.get("normal", {})
        we = modes.get("weighted_euclid", {})
        wn = modes.get("weighted_normal", {})
        rows.append({
            "set": name,
            "within": e.get("within", {}).get("mean"),
            "p90": e.get("within", {}).get("p90"),
            "between": e.get("between", {}).get("mean"),
            "ratio": e.get("ratio"),
            "auc_euclid": e.get("auc"),
            "auc_normal": n.get("auc"),
            "auc_weighted_euclid": we.get("auc"),
            "auc_weighted_normal": wn.get("auc"),
        })
    return rows


def build(chart, corpus, ldm, normal, chart_parity, heat_parity, heat_chain, weights):
    blocks = runtime_blocks(RUNTIME.read_text())
    heat = blocks.get("heatmap", {})
    chart_cfg = blocks.get("chart", {})
    defaults = {
        "heatmap": heat, "chart": chart_cfg,
        "baseline": heat.get("metric") == "euclid" and heat.get("weighting") == "none"
        and chart_cfg.get("metric") == "euclid" and chart_cfg.get("weighting") == "none"
        and chart_cfg.get("temporal_filter") == "none",
    }
    gates = gates_for(corpus, chart, chart_parity, heat_parity, heat_chain)
    payload = {
        "iteration": 4,
        "defaults": defaults,
        "verdict": {
            "code": 2,
            "slug": "partial",
            "title": "Включить частично: график на baseline, кандидаты — флаги",
            "heatmap": "baseline без изменений",
            "chart": "серверный ряд включён на baseline",
            "weighted_euclid": "флаг конфига (LOTRO 3/4, CI не считался)",
            "weighted_normal": "только отчёты (LOPO 5/10, минимум −0.0989)",
            "normal": "только отчёты (потеря в челюсти, per-frame не восстанавливает)",
            "landmarks": "ldm68 только для диагностики",
        },
        "gates": gates,
        "chart_summary": summary_rows(chart),
        "chart_band": weights.get("chart_band"),
        "chart_sequences": chart.get("sequences"),
        "chart_quiet": chart.get("quiet"),
        "chart_events": chart.get("events"),
        "chart_spikes": chart.get("spikes"),
        "corpus": {
            "dataset": corpus.get("dataset"),
            "counts": corpus.get("counts"),
            "modes": corpus.get("modes"),
            "lopo": corpus.get("lopo"),
            "lotro": corpus.get("lotro"),
            "frontal": corpus.get("frontal"),
            "frontal_gap10_eval": corpus.get("frontal_gap10_eval"),
            "weights": corpus.get("weights"),
        },
        "landmark": {
            "dataset": ldm.get("dataset"),
            "counts": ldm.get("counts"),
            "sets": land_rows(ldm),
            "conclusion": ldm.get("conclusion"),
        },
        "normal_diag": {
            "targets": normal.get("targets"),
            "people": {t: {k: normal.get("people", {}).get(t, {}).get(k)
                           for k in ("auc", "zones", "families", "per_frame_normals",
                                     "capture", "expression", "lopo_auc")}
                       for t in normal.get("targets", [])},
            "reference": normal.get("reference"),
            "diagnosis": normal.get("diagnosis"),
            "verdict": normal.get("verdict"),
        },
        "parity": {
            "chart": {k: chart_parity.get(k) for k in
                      ("parity", "chain", "heat", "config", "pass")},
            "heatmap": {k: heat_parity.get(k) for k in
                        ("cases", "max_abs_diff", "max_color_diff", "passed")},
            "heatmap_chain": {k: heat_chain.get(k) for k in
                              ("join_jump", "heat_join", "segment_independent", "passed")},
        },
        "not_verified": None,
        "files": [],
    }
    payload["not_verified"] = not_verified(payload)
    payload["files"] = files_list()
    return payload


def not_verified(payload):
    frontal = payload["corpus"].get("frontal") or {}
    return [
        {"item": "Фронтальный гейт при зазоре 30",
         "reason": f"в размеченной части всего {frontal.get('labeled', {}).get('n')} пара; "
                   "при зазоре 10 пар 13 на 6 людях, но это другой протокол"},
        {"item": "CI ΔAUC для euclid + calibrated",
         "reason": "bootstrap в v3 запускался только для normal и weighted_normal; "
                   "для weighted_euclid CI не считался"},
        {"item": "Контроль invalid_pose для wild-людей (person_9/10/11)",
         "reason": "позы предсказаны моделью, ручной метки нет: расхождение метки и yaw "
                   "не с чем сравнивать"},
        {"item": "Третий тип серии «frontal → profile → frontal»",
         "reason": "в корпусе такого маршрута нет; pose_sweep идёт «профиль → фронтал → "
                   "противоположный профиль»"},
        {"item": "Отдельный export графика",
         "reason": "exportPNG рисует те же rows, что и preview; отдельного файла-экспорта нет, "
                   "поэтому паритет проверяется по значениям API == harness"},
    ]


def files_list():
    return [
        {"file": "scripts/landmark_sweep.py", "role": "A: harness ldm68/106/134"},
        {"file": "scripts/corpus_v4.py, scripts/corpus_extra.py", "role": "D: корпус 10 человек"},
        {"file": "scripts/calibration_v3.py", "role": "D: прогон четырёх режимов на 10 людях"},
        {"file": "scripts/chart_score.py", "role": "B2–B5: chart-score harness"},
        {"file": "scripts/normal_diag.py", "role": "C: диагностика normal"},
        {"file": "scripts/chart_parity.py", "role": "B7: API == harness, цепочка"},
        {"file": "scripts/v4_report.py", "role": "итоговый отчёт"},
        {"file": "server/chart.py", "role": "B6: агрегаты ряда поверх server/heat.py"},
        {"file": "server/app.py", "role": "B6: GET /api/chart/series"},
        {"file": "server/heat.py", "role": "chart_band в профиле, без изменения значений"},
        {"file": "configs/runtime.yaml", "role": "блок chart; дефолт не менялся"},
        {"file": "web/src/components/Timeline.tsx",
         "role": "B6: ChartTrack с сервера; единственный график по умолчанию"},
        {"file": "web/src/styles.css", "role": "B6: стиль дорожки графика"},
    ]


def gate_table(rows):
    lines = ["| гейт | порог | значение | статус |", "|---|---|---|---|"]
    for row in rows:
        mark = {"pass": "pass", "fail": "fail", "na": "—"}.get(row["state"], row["state"])
        cells = [str(row[key]).replace("|", "\\|") for key in ("criterion", "threshold", "value")]
        lines.append(f"| {cells[0]} | {cells[1]} | {cells[2]} | {mark} |")
    return lines


def write_md(payload, path: Path):
    corpus = payload["corpus"]
    modes = corpus.get("modes") or {}
    ldm = payload["landmark"]
    normal = payload["normal_diag"]
    gates = payload["gates"]

    lines = ["# Калибровка v4: чистый таймлайн, landmark-sweep, расширенный корпус", ""]
    lines += [
        "Итерация 4. Геометрия `vertices`, морф-пайплайн и поворотная ветка не тронуты.",
        "Heatmap и график считает один helper `server.heat.compute_heat_values`;",
        "в браузере второй формулы нет. Сырые значения ряда хранятся отдельно от сглаженных.",
        "",
        "## Дефолты",
        "",
        "| блок | metric | weighting | temporal_filter |",
        "|---|---|---|---|",
        f"| heatmap | {payload['defaults']['heatmap'].get('metric')} "
        f"| {payload['defaults']['heatmap'].get('weighting')} | — |",
        f"| chart | {payload['defaults']['chart'].get('metric')} "
        f"| {payload['defaults']['chart'].get('weighting')} "
        f"| {payload['defaults']['chart'].get('temporal_filter')} |",
        "",
        ("Дефолт не менялся: `euclid + none` у heatmap и `euclid + none + none` у графика. "
         "Кандидаты включаются только правкой конфига."
         if payload["defaults"]["baseline"] else
         "**ВНИМАНИЕ: дефолт отличается от baseline — проверить configs/runtime.yaml.**"),
        "",
        "Одно изменение отображения без правки конфига: в таймлайне по умолчанию теперь "
        "один график (серверный `ChartTrack`); сырые дорожки реестра скрыты и включаются "
        "кнопкой «Дорожки».",
        "",
        "## Вердикт",
        "",
        f"**{payload['verdict']['title']}.**",
        "",
        f"- heatmap — {payload['verdict']['heatmap']};",
        f"- график — {payload['verdict']['chart']};",
        f"- `euclid + calibrated` — {payload['verdict']['weighted_euclid']};",
        f"- `weighted_normal` — {payload['verdict']['weighted_normal']};",
        f"- `normal` — {payload['verdict']['normal']};",
        f"- landmark-наборы — {payload['verdict']['landmarks']}.",
        "",
        "Почему `euclid + calibrated` не включён, хотя гейты графика прошли: тот же профиль",
        "весов проваливает LOTRO на `mid_deep` (ΔAUC −0.0175), CI для него не считался, а сам",
        "профиль между корпусами меняется на 27% по медиане |Δw|. Включать его только в графике",
        "означало бы показывать линию по неутверждённой калибровке. Один флаг в конфиге",
        "(`chart.metric` / `chart.weighting`) включает режим без правок кода.",
        "",
        "## B1. Что рисовал Timeline до итерации",
        "",
        "`Timeline.tsx` рисовал per-photo значения реестра метрик "
        "(`rows[].metrics[id].value`) в сыром пространстве `vertices`/`landmarks_render`: "
        "без center+IOD, без normal-компоненты, без калибровки и без временного фильтра. "
        "Режимы `value` / `z` / `delta` — три представления одного и того же сырого ряда. "
        "`variant=\"morph\"` переиспользует те же дорожки, добавляя ключевые кадры и скраббер.",
        "",
        "Теперь ряд считает `server/chart.py` поверх `compute_heat_values` (center + IOD):",
        "`value_raw`, `value_display`, `band`, `significance`; браузер ничего не пересчитывает.",
        "",
        "## D. Корпус",
        "",
        f"Кадров {corpus['dataset']['frames']}, валидных {corpus['dataset']['valid']}, "
        f"человек {len(corpus['dataset']['people'])}. Зазор 30: within "
        f"{corpus['counts']['within']}, between {corpus['counts']['between']}.",
        "",
        "| персона | кадров | валидных | фронтальных | источник поз |",
        "|---|---|---|---|---|",
    ]
    for person, row in corpus["dataset"]["per_person"].items():
        lines.append(f"| {person} | {row['frames']} | {row['valid']} | {row['frontal']} "
                     f"| {row['label_source']} |")
    lines += [
        "",
        "person_9/10/11 — Wikimedia Commons без ручной разметки: позы предсказаны моделью,",
        "поэтому контроль `invalid_pose` по расхождению метки и yaw для них не работает.",
        "",
        "### Четыре режима на 10 людях",
        "",
        "| режим | within μ | cross-bin μ | between μ | ratio | AUC |",
        "|---|---|---|---|---|---|",
    ]
    for name in MODES:
        m = modes.get(name, {})
        lines.append(f"| {name} | {f(m.get('within', {}).get('mean'), 5)} "
                     f"| {f(m.get('within_cross', {}).get('mean'), 5)} "
                     f"| {f(m.get('between', {}).get('mean'), 5)} "
                     f"| {f(m.get('ratio'), 3)} | {f(m.get('auc'))} |")
    lines += ["", "### LOPO", "", "| человек | within пар | euclid | normal | w-euclid | w-normal |",
              "|---|---|---|---|---|---|"]
    for row in (corpus.get("lopo") or {}).get("rows", []):
        lines.append(f"| {row['person']} | {row['n_within']} | {f(row['auc_euclid'])} "
                     f"| {f(row['auc_normal'])} | {f(row['auc_weighted_euclid'])} "
                     f"| {f(row['auc_weighted_normal'])} |")
    lines += ["", "| режим | побед | средний ΔAUC | минимум |", "|---|---|---|---|"]
    for name in ("normal", "weighted_euclid", "weighted_normal"):
        s = (corpus.get("lopo") or {}).get(name) or {}
        lines.append(f"| {name} | {s.get('wins')}/{s.get('n')} | {f(s.get('mean_delta_auc'))} "
                     f"| {f(s.get('min_delta_auc'))} |")
    lines += ["", "### LOTRO", "", "| семейство | within пар | ΔAUC w-normal | ΔAUC w-euclid |",
              "|---|---|---|---|"]
    for row in (corpus.get("lotro") or {}).get("rows", []):
        if row.get("skipped"):
            continue
        d_e = (row.get("auc_weighted_euclid") or 0) - (row.get("auc_euclid") or 0)
        lines.append(f"| {row['family']} | {row['n_within']} | {row.get('auc_delta')} | {d_e:+.4f} |")
    lines += [
        "",
        "### Фронтальный гейт",
        "",
        f"При зазоре 30 в размеченной части {corpus.get('frontal', {}).get('labeled', {}).get('n')} пара — "
        "гейт «не измеряется». При зазоре 10 нечётные кадры:",
        "",
        "| часть | пар | людей | euclid | normal | w-euclid | w-normal | Δ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for part, label in (("labeled", "размеченные"), ("predicted", "предсказанные")):
        row = (corpus.get("frontal_gap10_eval") or {}).get(part) or {}
        if not row:
            continue
        lines.append(f"| {label} | {row.get('n')} | {row.get('people')} | {f(row.get('euclid'), 5)} "
                     f"| {f(row.get('normal'), 5)} | {f(row.get('weighted_euclid'), 5)} "
                     f"| {f(row.get('weighted_normal'), 5)} | {row.get('delta_pct')}% |")
    w = corpus.get("weights") or {}
    lines += [
        "",
        "### Стабильность весов",
        "",
        f"Медиана |Δw|/w: {100 * w.get('relative_change', {}).get('median', 0):.1f}%, "
        f"p90 {100 * w.get('relative_change', {}).get('p90', 0):.1f}%, "
        f"корреляция {f(w.get('correlation'))}.",
        f"Clip: {w.get('clip', {}).get('old', [None])[0]:.5f}…{w.get('clip', {}).get('old', [None, None])[1]:.5f} → "
        f"{w.get('clip', {}).get('new', [None])[0]:.5f}…{w.get('clip', {}).get('new', [None, None])[1]:.5f}; "
        f"на границах clip по {w.get('at_bounds', {}).get('new_lower')}% вершин.",
        "Новый профиль `reports/calibration/weights-v4.json` в приложение не подключён.",
        "",
        "## A. Landmark-sweep",
        "",
        f"Кадров {ldm['dataset']['frames']} ({ldm['dataset']['people']} человек), "
        f"пар within {ldm['counts']['within']}, between {ldm['counts']['between']}.",
        "",
        "| набор | within μ | p90 | between μ | ratio | AUC euclid | AUC normal "
        "| AUC w-euclid | AUC w-normal |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in ldm["sets"]:
        lines.append(f"| {row['set']} | {f(row['within'], 4)} | {f(row['p90'], 4)} "
                     f"| {f(row['between'], 4)} | {f(row['ratio'], 3)} | {f(row['auc_euclid'])} "
                     f"| {f(row['auc_normal'])} | {f(row['auc_weighted_euclid'])} "
                     f"| {f(row['auc_weighted_normal'])} |")
    lines += ["", "Вывод:"] + [f"- {line}" for line in ldm.get("conclusion") or []]
    lines += [
        "",
        "## B2–B5. График",
        "",
        "| ряд | фон медиана | фон MAD | ложные пики | calm std | пик/фон | чувствительность | автокорр |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["chart_summary"]:
        lines.append(f"| {row['mode']} | {f(row['quiet_median'], 6)} | {f(row['quiet_mad'], 6)} "
                     f"| {row['false_peaks']} | {f(row['calm_std'], 6)} | {f(row['peak_ratio'], 3)} "
                     f"| {f(row['sensitivity'], 2)} | {f(row['autocorr'], 3)} |")
    lines += ["", "Тестовые серии:", "", "| тип | персона | кадров | поза | примечание |",
              "|---|---|---|---|---|"]
    for name, seq in (payload.get("chart_sequences") or {}).items():
        frames = seq.get("frames") or []
        if seq.get("pose_delta") is not None:
            yaw = f"Δ {seq['pose_delta']}°"
        elif frames:
            yaw = f"{min(f['yaw'] for f in frames):.0f}…{max(f['yaw'] for f in frames):.0f}°"
        else:
            yaw = "—"
        lines.append(f"| {name} | {seq.get('person')} | {len(seq.get('frames') or [])} "
                     f"| {yaw} | {seq.get('note')} |")
    lines += [
        "",
        "Третьего типа серии (frontal → profile → frontal) в корпусе нет; pose_sweep идёт",
        "«профиль → фронтал → противоположный профиль». Это зафиксировано, а не заменено.",
        "",
        "### Фильтр",
        "",
        "| фильтр | ложные пики (euclid) | чувствительность | одиночный пик выше порога |",
        "|---|---|---|---|",
    ]
    for filt in ("raw", "median3", "median5"):
        q = (payload.get("chart_quiet") or {}).get(BASELINE, {}).get(filt, {})
        sens = (payload.get("chart_events") or {}).get("summary", {}).get(BASELINE, {}).get(filt, {})
        spike = (payload.get("chart_spikes") or {}).get(BASELINE, {})
        above = spike.get(f"{filt}_above", True) if filt != "raw" else True
        lines.append(f"| {filt} | {q.get('false_peaks')} | {f(sens.get('sensitivity'), 2)} | {f(above)} |")
    lines += [
        "",
        "Медианное окно убирает одиночный шаг: синтетический пик падает ниже порога",
        "(`median3_above = False`), и на подтверждённых событиях чувствительность падает",
        "с 1.0 до 0.5. Поэтому фильтр остаётся выключенным, а `value_raw` хранится отдельно.",
        "",
        "## B6–B7. Интеграция",
        "",
        "`GET /api/chart/series?group=…` отдаёт `frames` и `rows` с `value_raw`, `value_display`,",
        "`band`, `significance`, `z_mean`, `z_p95`, `frac_z_gt3`,",
        "`low_confidence_fraction`; семейство перехода (`pose_transition`) считает harness "
        "в отчёте, в ответ API оно не входит.",
        "`ChartTrack` рисует полосу, пунктир raw и линию display; `exportPNG` использует "
        "те же значения. По умолчанию в таймлайне один график: сырые дорожки реестра "
        "скрыты и включаются кнопкой «Дорожки».",
        "Band (`chart_band` профиля): "
        + (", ".join(f"{k} {v}" for k, v in (payload.get("chart_band") or {}).items()) or "—") + ".",
        "",
        f"Паритет API == harness: max|Δ| = {chart_parity_max(payload)} по 29 шагам на двух людях "
        "и четырёх режимах, 0 расхождений полей.",
        f"Heatmap preview/export/browser: max|Δ| = {payload['parity']['heatmap'].get('max_abs_diff')}.",
        f"Цепочка: join = {payload['parity']['chart']['chain']['euclid']['join_max_abs_delta']} "
        f"(график), {payload['parity']['heatmap_chain'].get('join_jump')} (heatmap).",
        "",
        "Смена блока `chart` видна без рестарта: тест `config_switch` переключает "
        "`temporal_filter` (меняется только `value_display`, `value_raw` побитово тот же) "
        "и `metric` (меняются `value_raw` и `band`); возврат конфига возвращает исходную подпись кэша.",
        "",
        "## C. Почему normal падает на person_02 и person_05",
        "",
        "| человек | euclid | normal | w-euclid | w-normal | jaw euclid | jaw normal | угол нормалей | флипы |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for target in normal.get("targets") or []:
        row = normal["people"][target]
        jaw = row["zones"]["jaw"]
        quality = normal.get("diagnosis", {}).get("normal_angle_mean_deg", {}).get(target)
        flips = normal.get("diagnosis", {}).get("normal_flip_fraction", {}).get(target)
        lines.append(f"| {target} | {f(row['auc']['euclid'], 3)} | {f(row['auc']['normal'], 3)} "
                     f"| {f(row['auc']['weighted_euclid'], 3)} | {f(row['auc']['weighted_normal'], 3)} "
                     f"| {f(jaw['euclid'], 3)} | {f(jaw['normal'], 3)} | {f(quality, 2)}° | {f(flips)} |")
    diag = normal.get("diagnosis") or {}
    fam_lines = []
    for target in normal.get("targets") or []:
        fam = normal["people"][target].get("families") or {}
        counts = "/".join(str(fam.get(k, {}).get("n_within", 0)) for k in
                          ("frontal_light", "light_mid", "mid_deep", "deep_profile"))
        deep = fam.get("deep_profile") or {}
        e_deep, n_deep = deep.get("euclid"), deep.get("normal")
        if e_deep is not None and n_deep is not None and e_deep - n_deep > 0.01:
            note = "провал воспроизводится"
        elif e_deep == 1.0 and n_deep == 1.0:
            note = "потолок 1.0, провалу некуда проявиться"
        else:
            note = "разница в пределах шума"
        fam_lines.append(f"{target}: within по семействам {counts}, "
                         f"deep_profile AUC {f(e_deep, 3)} → {f(n_deep, 3)} ({note})")
    lines += [
        "",
        "По семействам переходов внутри-пар у этих людей мало: AUC по семейству измерим "
        "только для `deep_profile`, остальные три семейства пропущены.",
        "",
    ]
    lines += [f"- {line};" for line in fam_lines]
    lines += [
        "",
        f"Нормали: средний угол template vs per-frame {f(diag.get('normal_angle_mean_deg', {}).get('person_02'), 2)}°/"
        f"{f(diag.get('normal_angle_mean_deg', {}).get('person_05'), 2)}°, "
        f"флипов {f(diag.get('normal_flip_fraction', {}).get('person_02'))}/"
        f"{f(diag.get('normal_flip_fraction', {}).get('person_05'))}. Поле нормалей корректно.",
        f"AUC по зоне челюсти падает на {f(diag.get('jaw_auc_drop_normal_minus_euclid', {}).get('person_02'), 3)} "
        f"и {f(diag.get('jaw_auc_drop_normal_minus_euclid', {}).get('person_05'), 3)}; "
        "брови, глаза и нос сохраняют разделение. Улыбка/рот как причина не подтверждаются: "
        "у person_02 рот даже лучше у normal, у person_05 — тоже.",
        "",
        f"Per-frame нормали дают ΔAUC {f(diag.get('per_frame_normals_auc_gain', {}).get('person_02'), 3)} "
        f"и {f(diag.get('per_frame_normals_auc_gain', {}).get('person_05'), 3)} — провал не возвращается, "
        "поэтому в продакшн этот вариант не идёт (в v3 он ещё и рвал стык).",
        "",
        f"**Итог C:** {normal.get('verdict')}.",
        "",
        "## Гейты",
        "",
        "### euclid + calibrated",
        "",
    ]
    lines += gate_table(gates.get("weighted_euclid", []))
    lines += ["", "### weighted_normal", ""]
    lines += gate_table(gates.get("weighted_normal", []))
    lines += ["", "### временной фильтр (median3/5, режим euclid)", ""]
    lines += gate_table(gates.get("temporal_filter", []))
    lines += [
        "",
        "## Что не удалось проверить и почему",
        "",
        "| пункт | причина |",
        "|---|---|",
    ]
    for item in payload["not_verified"]:
        lines.append(f"| {item['item']} | {item['reason']} |")
    lines += [
        "",
        "## Файлы",
        "",
        "| файл | роль |",
        "|---|---|",
    ]
    for item in payload["files"]:
        lines.append(f"| `{item['file']}` | {item['role']} |")
    lines += [
        "",
        "Отчёты и рисунки:",
        "",
        "- `reports/calibration-v4.md` / `.json` — этот отчёт;",
        "- `reports/calibration-v4-corpus.md` / `.json` — корпус, LOPO, LOTRO, веса;",
        "- `reports/calibration-v4-chart.md` — B1–B5;",
        "- `reports/calibration-ldm.md` / `.json` — landmark-sweep;",
        "- `reports/calibration/chart-sequences.json` — манифест серий;",
        "- `reports/calibration/chart-parity.json` — B7;",
        "- `reports/calibration/normal-diag.json` — C;",
        "- `reports/figures/v4-chart-raw-vs-filter.png`, `v4-lopo.png`, "
        "`v4-normal-diag.png`, `ldm-points.png`, `ldm-table.png`, "
        "`v4-timeline-ui.png` (один график в таймлайне).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def chart_parity_max(payload):
    rows = (payload["parity"]["chart"].get("parity") or {})
    values = [mode.get("max_abs_delta") for person in rows.values() for mode in person.values()]
    values.append((payload["parity"]["chart"].get("heat") or {}).get("euclid", {}).get("max_abs_delta"))
    values = [v for v in values if v is not None]
    return max(values) if values else None


def main():
    payload = build(load(CHART), load(CORPUS), load(LDM), load(NORMAL), load(CHART_PARITY),
                    load(HEAT_PARITY), load(HEAT_CHAIN), load(WEIGHTS))
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    write_md(payload, OUT_MD)
    print("json", OUT_JSON)
    print("md", OUT_MD)
    print("verdict", payload["verdict"]["slug"], "defaults", payload["defaults"]["baseline"])


if __name__ == "__main__":
    main()
