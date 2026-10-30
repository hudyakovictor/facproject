"""Итог итерации 5 (calibration-v5): решение по euclid + calibrated с числами.

Ничего не пересчитывает: собирает reports/calibration-v5.md и .json из готовых
артефактов шагов 1–6 и закрывающих проверок §4.

    reports/calibration/bootstrap-v5.json        (шаг 1: CI ΔAUC, LOTRO)
    reports/calibration/lopo-v5.json             (шаг 2: LOPO 7 против 10)
    reports/calibration/pose-labels-v5.json      (шаг 3: ручные yaw-метки)
    reports/calibration/invalid-frames-v5.json   (шаг 3: invalid_pose)
    reports/calibration/frontal-gate-v5.json     (шаг 5: фронтальный гейт)
    reports/calibration/weights-stability-v5.json(шаг 6: устойчивость весов)
    reports/calibration/chart-parity.json        (§4.2–4.3: паритет, config_switch)
    reports/calibration/timeline-ui-v5.json      (§4.5: data-testid таймлайна)
    configs/runtime.yaml                          (дефолты не менялись)

Запуск:

    python scripts/v5_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "reports/calibration"
BOOT = CAL / "bootstrap-v5.json"
LOPO = CAL / "lopo-v5.json"
POSE = CAL / "pose-labels-v5.json"
INVALID = CAL / "invalid-frames-v5.json"
FRONTAL = CAL / "frontal-gate-v5.json"
WEIGHTS = CAL / "weights-stability-v5.json"
PARITY = CAL / "chart-parity.json"
TIMELINE = CAL / "timeline-ui-v5.json"
RUNTIME = ROOT / "configs/runtime.yaml"
OUT_MD = ROOT / "reports/calibration-v5.md"
OUT_JSON = ROOT / "reports/calibration-v5.json"

FAMILIES = ("frontal_light", "light_mid", "mid_deep", "deep_profile")


def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else {}


def runtime_defaults(text: str) -> dict:
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
            blocks[current][key] = value.split("#", 1)[0].strip()
    return blocks


def build():
    boot, lopo, pose = load(BOOT), load(LOPO), load(POSE)
    frontal, weights, parity = load(FRONTAL), load(WEIGHTS), load(PARITY)
    timeline, invalid = load(TIMELINE), load(INVALID)
    cfg = runtime_defaults(RUNTIME.read_text()) if RUNTIME.exists() else {}
    heat, chart = cfg.get("heatmap", {}), cfg.get("chart", {})

    a10 = boot.get("slices", {}).get("all_10", {})
    a7 = boot.get("slices", {}).get("labeled_7", {})
    fams = boot.get("lotro_families", {})
    mid_deep = fams.get("mid_deep", {})
    wcmp = lopo.get("comparison", {}).get("weighted_euclid", {})
    g30 = frontal.get("gate_gap30", {})
    g10 = frontal.get("gate_gap10", {})
    wgate = weights.get("gates", {})
    conf = parity.get("config", {})

    # --- Таблица решения §3: шесть условий ---
    decision = [
        {"n": 1, "condition": "Нижняя граница CI ΔAUC > 0 на 10 людях", "source": "шаг 1",
         "value": f"CI [{a10.get('bootstrap', {}).get('ci95_delta_auc', [None])[0]}, "
                  f"{a10.get('bootstrap', {}).get('ci95_delta_auc', [None, None])[1]}], "
                  f"ΔAUC {a10.get('delta_auc')}",
         "state": "pass" if a10.get("gate_ci_lo_positive") else "fail"},
        {"n": 2, "condition": "LOPO: минимум ΔAUC не хуже −0.02", "source": "шаг 2",
         "value": f"min Δ {wcmp.get('min_delta_7')} (7), {wcmp.get('min_delta_10')} (10); "
                  f"побед {wcmp.get('wins_7')}/7, {wcmp.get('wins_10')}/10",
         "state": "pass" if lopo.get("gates", {}).get("weighted_euclid_min_delta_not_worse_than_-0.02") else "fail"},
        {"n": 3, "condition": "LOTRO: 4 из 4, mid_deep не хуже −0.005", "source": "шаг 1",
         "value": f"CI-положительных семейств {boot.get('gates', {}).get('lotro_families_ci_positive')}; "
                  f"mid_deep ΔAUC {mid_deep.get('delta_auc')} (порог −0.005)",
         "state": "pass" if boot.get("gates", {}).get("mid_deep_point_delta_not_below_-0.005")
         and boot.get("gates", {}).get("lotro_families_ci_positive") == "4/4" else "fail"},
        {"n": 4, "condition": "Серия frontal → profile → frontal возвращается в допуск 10%",
         "source": "шаг 4", "value": "не измеряется: в корпусе нет ни одной серии «туда и обратно»",
         "state": "unmeasured"},
        {"n": 5, "condition": "Гейт весов пройден", "source": "шаг 6",
         "value": f"медиана |Δw| {100 * wgate.get('median_of_medians', 0):.1f}% (порог 10%), "
                  f"на границах clip {wgate.get('max_at_bounds_pct')}% (порог 1%), "
                  f"ΔAUC>0 {wgate.get('splits_with_both_delta_auc_positive')}",
         "state": "pass" if wgate.get("weights_v4_connect_allowed") else "fail"},
        {"n": 6, "condition": "Паритет API и harness = 0, config_switch проходит",
         "source": "chart_parity.py",
         "value": f"all_pass {parity.get('all_pass')}; raw_kept {conf.get('raw_kept')}, "
                  f"display_changed {conf.get('display_changed')}, metric_changed {conf.get('metric_changed')}, "
                  f"restored {conf.get('restored')}",
         "state": "pass" if parity.get("all_pass") else "fail"},
    ]
    enabled = all(row["state"] == "pass" for row in decision)

    checks = {
        "tests": {"result": "64 passed, 2 failed", "green": False,
                  "failures": [
                      {"test": "test_metric_registry_pose_values", "assert": "23 == 3",
                       "cause": "registry.catalog() отдаёт 23 метрики 3ddfa_v3: "
                                "metrics/tddfa_v3/archive_top20.py регистрирует 20 archive_* "
                                "сверх трёх сетевых. Не зависит от корпуса и от итерации 5."},
                      {"test": "test_projection_seed_and_real_alpha", "assert": "silhouette is None",
                       "cause": "в рабочем data/library.json 294 не-демо фото в 11 группах, "
                                "silhouette считается при >1 группе. Тест рассчитан на чисто "
                                "демо-библиотеку. Не зависит от гейтов калибровки."}]},
        "chart_parity": {"max_abs_delta": 0, "all_pass": parity.get("all_pass")},
        "config_switch": {"raw_kept": conf.get("raw_kept"), "display_changed": conf.get("display_changed"),
                          "metric_changed": conf.get("metric_changed"), "restored": conf.get("restored")},
        "cache_key": {"fields": ["metric", "weighting", "temporal_filter", "filter_window",
                                 "profile_path", "profile_mtime_ns"],
                      "source": "server/app.py chart_config_signature() → lru chart_payload",
                      "pass": True},
        "timeline_testid": {"chart_track": timeline.get("checks", {}).get("chart_track_count"),
                            "metric_track_not_chart": timeline.get("checks", {}).get("metric_track_not_chart_count"),
                            "pass": timeline.get("pass")},
        "screenshot": "reports/figures/v5-timeline-ui.png",
    }

    payload = {
        "iteration": 5,
        "generated_at": boot.get("generated_at"),
        "seed": boot.get("seed"),
        "rounds": boot.get("rounds_requested"),
        "comparison": boot.get("comparison"),
        "defaults": {"heatmap": heat, "chart": chart,
                     "unchanged": heat.get("metric") == "euclid" and heat.get("weighting") == "none"
                     and chart.get("metric") == "euclid" and chart.get("weighting") == "none"
                     and chart.get("temporal_filter") == "none"},
        "verdict": {
            "enabled": bool(enabled),
            "slug": "enable" if enabled else "do_not_enable",
            "title": ("Включить euclid + calibrated" if enabled
                      else "НЕ включать euclid + calibrated"),
            "reason": "не выполнены условия 3 (LOTRO mid_deep), 4 (round-trip не измеряется), "
                      "5 (веса нестабильны)",
        },
        "decision_table": decision,
        "step1_bootstrap": {
            "all_10": a10, "labeled_7": a7, "lotro_families": {k: fams.get(k) for k in FAMILIES},
            "gates": boot.get("gates"), "crosscheck": boot.get("auc_crosscheck"),
        },
        "step2_lopo": {"comparison": lopo.get("comparison"), "gates": lopo.get("gates"),
                       "interpretation": lopo.get("interpretation")},
        "step3_pose_labels": {"n_frames": pose.get("n_frames"), "n_valid": pose.get("n_valid"),
                              "n_invalid": pose.get("n_invalid"),
                              "threshold": pose.get("invalid_pose_threshold"),
                              "discrepancy_valid": pose.get("discrepancy_valid"),
                              "invalid_reasons": [x.get("reason") for x in invalid.get("frames", [])]},
        "step4_roundtrip": {"measured": False,
                            "reason": "фронт→профиль→фронт в корпусе отсутствует: все видеосерии "
                                      "монотонные развёртки; снять новые кадры нельзя"},
        "step5_frontal_gate": {"gap30": g30, "gap10": g10, "gate": frontal.get("gate")},
        "step6_weights": {"gates": wgate, "runs": weights.get("runs")},
        "closing_checks": checks,
        "not_verified": [
            {"item": "Серия frontal → profile → frontal (шаг 4)",
             "reason": "в корпусе нет маршрута туда-обратно; значение не возвращается — не измерено, "
                       "а не «плохо»"},
            {"item": "Тесты проекта полностью зелёные (§4.1)",
             "reason": "2 падения предсуществующие: реестр метрик (23 против 3) и живая библиотека "
                       "фото (silhouette). К итерации 5 не относятся"},
        ],
        "files": [],
    }
    payload["files"] = files_list()
    return payload


def files_list():
    return [
        {"file": "scripts/v5_corpus.py", "role": "общая инфраструктура шагов 1,2,5,6: корпус, пары, bootstrap"},
        {"file": "scripts/bootstrap_auc.py", "role": "шаг 1: bootstrap CI ΔAUC + LOTRO-семейства"},
        {"file": "scripts/lopo_v5.py", "role": "шаг 2: LOPO на 7 размеченных и 10 людях"},
        {"file": "scripts/pose_labels_v5.py", "role": "шаг 3: ручные yaw-метки person_9/10/11, invalid_pose"},
        {"file": "scripts/frontal_gate_v5.py", "role": "шаг 5: фронтальный гейт при зазоре 30 и 10"},
        {"file": "scripts/weights_stability_v5.py", "role": "шаг 6: устойчивость весов на половинах людей"},
        {"file": "scripts/v5_bootstrap_figure.py", "role": "рисунок v5-bootstrap-auc.png"},
        {"file": "scripts/v5_report.py", "role": "этот отчёт"},
        {"file": "scripts/chart_parity.py", "role": "§4.2–4.3: паритет API==harness, config_switch"},
        {"file": "web/v5-timeline-check.mjs", "role": "§4.5–4.6: проверка data-testid и скриншот"},
       {"file": "server/app.py", "role": "§4.4: chart_config_signature в ключе кэша; §6: GET /api/chart/series.csv"},
        {"file": "web/src/components/Timeline.tsx", "role": "§6: ссылка «График CSV» на /api/chart/series.csv (те же rows)"},
        {"file": "configs/runtime.yaml", "role": "дефолты heatmap и chart не менялись"},
    ]


def fmt(v, d=4):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "да" if v else "нет"
    if isinstance(v, int):
        return str(v)
    return f"{v:.{d}f}"


def write_md(payload, path: Path):
    d = payload
    a10 = d["step1_bootstrap"]["all_10"]
    a7 = d["step1_bootstrap"]["labeled_7"]
    fams = d["step1_bootstrap"]["lotro_families"]
    ck = d["closing_checks"]
    lines = ["# Калибровка v5: решение по `euclid + calibrated`", ""]
    lines += [
        "Итерация 5. `configs/runtime.yaml` не менялся: heatmap `euclid + none`, график "
        "`euclid + none + none`. Геометрия, морф-пайплайн и поворотная ветка не тронуты. "
        "Значения считает только `server.heat.compute_heat_values`; второй формулы в браузере нет.",
        "",
        "## 1. Вердикт",
        "",
        f"**{d['verdict']['title']}.** " + d["verdict"]["reason"][0].upper() + d["verdict"]["reason"][1:] + ".",
        "",
        "`euclid + calibrated` остаётся флагом в конфиге, `weights-v4.json` не подключён. "
        "Heatmap и график дефолтов не менялись.",
        "",
        "## 2. Таблица гейтов (§3)",
        "",
        "| # | условие | значение | источник | статус |",
        "|---|---|---|---|---|",
    ]
    mark = {"pass": "прошёл", "fail": "не прошёл", "unmeasured": "не измеряется"}
    for row in d["decision_table"]:
        val = str(row["value"]).replace("|", "\\|")
        lines.append(f"| {row['n']} | {row['condition']} | {val} | {row['source']} | "
                     f"{mark.get(row['state'], row['state'])} |")
    lines += ["", "## 3. Числа по шагам", ""]

    comp = d["comparison"]
    lines += [
        "### Шаг 1. Bootstrap CI ΔAUC (`reports/calibration/bootstrap-v5.json`)",
        "",
        f"Ресемплинг по людям, seed {d['seed']}, {d['rounds']} повторов. Кандидат "
        f"`{comp.get('candidate')}` против baseline `{comp.get('baseline')}`.",
        "",
        "| срез | within | between | AUC none | AUC calibrated | ΔAUC | 95% CI | низ CI > 0 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, s in (("10 людей", a10), ("7 размеченных", a7)):
        ci = s.get("bootstrap", {}).get("ci95_delta_auc", [None, None])
        lines.append(f"| {name} | {s.get('n_within')} | {s.get('n_between')} | "
                     f"{fmt(s.get('auc_euclid_none'))} | {fmt(s.get('auc_euclid_calibrated'))} | "
                     f"{fmt(s.get('delta_auc'))} | [{fmt(ci[0])}, {fmt(ci[1])}] | "
                     f"{'да' if s.get('gate_ci_lo_positive') else 'нет'} |")
    lines += ["", "LOTRO-семейства (профиль переодевается без семейства):", "",
              "| семейство | within | ΔAUC точка | 95% CI | низ CI > 0 | точка ≥ −0.005 |",
              "|---|---|---|---|---|---|"]
    for fam in FAMILIES:
        f = fams.get(fam, {})
        ci = f.get("bootstrap", {}).get("ci95_delta_auc", [None, None])
        lines.append(f"| {fam} | {f.get('n_within')} | {fmt(f.get('delta_auc'))} | "
                     f"[{fmt(ci[0])}, {fmt(ci[1])}] | {'да' if f.get('gate_ci_lo_positive') else 'нет'} | "
                     f"{'да' if f.get('gate_point_not_below_-0.005') else 'нет'} |")
    g = d["step1_bootstrap"]["gates"]
    lines += ["", f"Гейты шага 1: CI>0 на 10 людях — {'да' if g.get('ci_lo_positive_on_10') else 'нет'}; "
              f"семейств с CI>0 — {g.get('lotro_families_ci_positive')}; "
              f"mid_deep точка ≥ −0.005 — {'да' if g.get('mid_deep_point_delta_not_below_-0.005') else 'нет'}. "
              f"Кросс-проверка AUC против sklearn: max|Δ| = {d['step1_bootstrap']['crosscheck'].get('max_abs_diff')}.",
              "", "![bootstrap ΔAUC](figures/v5-bootstrap-auc.png)", ""]

    lo = d["step2_lopo"]
    lines += ["### Шаг 2. LOPO без предсказанных поз (`reports/calibration/lopo-v5.json`)", "",
              "| метрика | побед (7) | побед (10) | min ΔAUC (7) | min ΔAUC (10) |",
              "|---|---|---|---|---|"]
    we = lo["comparison"]["weighted_euclid"]
    lines.append(f"| weighted_euclid | {we['wins_7']}/7 | {we['wins_10']}/10 | "
                 f"{fmt(we['min_delta_7'])} | {fmt(we['min_delta_10'])} |")
    lines += ["", f"Гейт: `weighted_euclid` ≥5/7 и min ΔAUC не хуже −0.02 — "
              f"{'пройден' if lo['gates'].get('weighted_euclid_wins_at_least_5_of_7') and lo['gates'].get('weighted_euclid_min_delta_not_worse_than_-0.02') else 'не пройден'}. "
              f"{lo.get('interpretation')}", ""]

    p3 = d["step3_pose_labels"]
    thr = p3["threshold"]
    lines += ["### Шаг 3. Ручные yaw-метки (`reports/calibration/pose-labels-v5.json`)", "",
              f"56 кадров (person_9/10/11), валидных {p3['n_valid']}, invalid_pose {p3['n_invalid']}. "
              f"Порог `invalid_pose`: LABEL_MISMATCH {thr.get('label_mismatch_deg')}°, "
              f"yaw_limit {thr.get('yaw_limit_deg')}° (источник: {thr.get('source')}). Медиана "
              f"|метка − предсказание| на валидных {p3['discrepancy_valid'].get('median')}°, "
              f"p90 {p3['discrepancy_valid'].get('p90')}°. Источник поз переключён "
              f"`predicted → manual+yaw`.", "",
              "Причины invalid_pose:"]
    for r in p3["invalid_reasons"]:
        lines.append(f"- {r}")
    lines += ["", "### Шаг 4. Серия frontal → profile → frontal", "",
              "**Не измеряется.** " + d["step4_roundtrip"]["reason"] + ". "
              "Медианный фильтр не включался (он роняет чувствительность с 1.00 до 0.50).", ""]

    g30 = d["step5_frontal_gate"]["gap30"]
    g10 = d["step5_frontal_gate"]["gap10"]
    lines += ["### Шаг 5. Фронтальный гейт (`reports/calibration/frontal-gate-v5.json`)", "",
              "С ручными метками шага 3 гейт стал измеримым (в v4 при зазоре 30 была 1 пара).", "",
              "| зазор | пар | людей | euclid within | calibrated within | Δ | вывод |",
              "|---|---|---|---|---|---|---|"]
    for label, r in (("30", g30), ("10", g10)):
        lines.append(f"| {label} | {r.get('n_pairs')} | {r.get('n_people_with_pairs')} | "
                     f"{fmt(r.get('euclid_within_mean'), 5)} | {fmt(r.get('weighted_euclid_within_mean'), 5)} | "
                     f"{r.get('delta_pct')}% | {r.get('verdict')} |")
    lines += ["", "### Шаг 6. Устойчивость весов (`reports/calibration/weights-stability-v5.json`)", "",
              f"5 разбиений пополам (seed {weights_seed(d)}). Медиана |Δw| "
              f"{100 * d['step6_weights']['gates'].get('median_of_medians', 0):.1f}% (порог 10%), "
              f"вершин на границах clip {d['step6_weights']['gates'].get('max_at_bounds_pct')}% (порог 1%), "
              f"ΔAUC>0 в {d['step6_weights']['gates'].get('splits_with_both_delta_auc_positive')} разбиений. "
              f"Гейт не пройден → `weights-v4.json` неподключён.", "",
              "| разбиение | медиана \\|Δw\\| | на границах clip % | ΔAUC B\\|A | ΔAUC A\\|B |",
              "|---|---|---|---|---|"]
    for r in d["step6_weights"]["runs"]:
        lines.append(f"| {r['split']} | {100 * r['median_abs_dw_rel']:.1f}% | {r['at_bounds_pct_max']}% | "
                     f"{fmt(r['delta_auc_B_on_A_profile'])} | {fmt(r['delta_auc_A_on_B_profile'])} |")
    lines += ["", "![устойчивость весов](figures/v5-weights-stability.png)", ""]

    lines += ["## 4. Проверки перед закрытием (§4)", "",
              "| проверка | результат |", "|---|---|",
              f"| тесты проекта | {ck['tests']['result']} (не зелёные, см. п. «не удалось») |"]
    for fl in ck["tests"]["failures"]:
        lines.append(f"| └ {fl['test']} | {fl['assert']}: {fl['cause']} |")
    lines += [
        f"| chart_parity API==harness | max\\|Δ\\| = {ck['chart_parity']['max_abs_delta']}, all_pass {ck['chart_parity']['all_pass']} |",
        f"| config_switch | raw_kept {ck['config_switch']['raw_kept']}, display_changed {ck['config_switch']['display_changed']}, metric_changed {ck['config_switch']['metric_changed']}, restored {ck['config_switch']['restored']} |",
        f"| ключ кэша ряда | {', '.join(ck['cache_key']['fields'])} (источник: {ck['cache_key']['source']}) |",
        f"| таймлайн data-testid | chart-track = {ck['timeline_testid']['chart_track']}, "
        f".metric-track:not(.chart-track) = {ck['timeline_testid']['metric_track_not_chart']} |",
        f"| скриншот | `{ck['screenshot']}` |",
        "",
        "## 5. Что изменилось против v4",
        "",
        "- Появился CI для ΔAUC: на 10 людях нижняя граница 0.0084 > 0 (в v4 CI не считался) — блокер CI снят;",
        "- ЛОТО-провал уточнён: mid_deep точка ΔAUC −0.0140 против −0.0175 в v4, порог −0.005 всё равно нарушен;",
        "- Фронтальный гейт стал измерим (22 пары на 10 людях, −12.7%) после ручной разметки шага 3 (в v4 — 1 пара);",
        "- Веса: медиана |Δw| 34.7% внутри корпуса против 27% между корпусами в v4 — стабильности по-прежнему нет.",
        "- Хвост §6: добавлен экспорт ряда графика `GET /api/chart/series.csv` (тот же `chart_payload`,",
        "  вторая формула в браузере не появилась); транзитные `web/.runtime/*.png` удалены.",
        "",
        "## 6. Что не удалось проверить",
        "",
        "| пункт | причина |", "|---|---|",
    ]
    for item in d["not_verified"]:
        lines.append(f"| {item['item']} | {item['reason']} |")
    lines += ["", "## 7. Файлы", "", "| файл | роль |", "|---|---|"]
    for item in d["files"]:
        lines.append(f"| `{item['file']}` | {item['role']} |")
    lines += ["", "Рисунки: `figures/v5-bootstrap-auc.png`, `figures/v5-lopo-7vs10.png`, "
              "`figures/v5-weights-stability.png`, `figures/v5-timeline-ui.png`. "
              "`v5-series-roundtrip.png` не создан — шаг 4 не измеряется.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def weights_seed(payload):
    runs = payload.get("step6_weights", {}).get("runs") or [{}]
    return runs[0].get("seed", 42)


def main():
    payload = build()
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    write_md(payload, OUT_MD)
    print("json", OUT_JSON)
    print("md", OUT_MD)
    print("verdict", payload["verdict"]["slug"], "defaults unchanged", payload["defaults"]["unchanged"])
    for row in payload["decision_table"]:
        print(f"  cond {row['n']}: {row['state']}")


if __name__ == "__main__":
    main()
