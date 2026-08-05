"""Deterministic multi-audience publication drafts built from Stage 2/3 artifacts.

The module does not use an LLM and does not infer identity. It creates an
editorial handoff in four synchronized layers:

1. plain-language method explainer for a general audience;
2. technical appendix for specialists and skeptical reviewers;
3. result-story draft with claim-to-artifact references;
4. machine-review packet for reproducible AI/static critique.

All outputs are drafts and require human editorial + forensic review.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from app6.stage1.utils import atomic_json, digest_file

PUBLICATION_SCHEMA = "deeputin-publication-drafts-v1.0"
MACHINE_PACKET_SCHEMA = "deeputin-machine-review-packet-v1.0"
CLAIMS_SCHEMA = "deeputin-publication-claims-v1.0"

ASSERTIVE_FORBIDDEN_PATTERNS = (
    "доказано, что",
    "мы доказали",
    "анализ доказал",
    "без сомнений",
    "точно установлено",
    "установлена подмена",
    "является двойником",
    "обнаружена маска",
    "proves that",
    "analysis proved",
    "definitely established",
    "is a body double",
)

GLOSSARY = {
    "3D-реконструкция": "Оценка формы лица параметрической моделью по фотографии; это не медицинское сканирование и не КТ.",
    "landmark": "Одна из заранее определённых соответствующих точек модели лица.",
    "pose bin": "Одна из девяти групп фотографий с близким поворотом головы.",
    "Kabsch alignment": "Жёсткое совмещение двух наборов точек поворотом и переносом без изменения масштаба.",
    "calibration noise": "Разброс измерений, наблюдаемый на фотографиях заведомо одного человека при разных условиях съёмки.",
    "p95": "Значение, ниже которого находится примерно 95% рассматриваемых наблюдений.",
    "FDR": "Контроль ожидаемой доли ложных находок при большом числе одновременных проверок.",
    "candidate": "Сигнал для проверки; не готовый вывод о личности или причине изменения.",
    "limited": "Результат, которому мешают качество, ракурс, видимость, датировка или слабая калибровка.",
    "provenance": "Цепочка происхождения файла: источник, архивная ссылка, дата, хеш и история получения.",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _integer(value: Any, default: int = 0) -> int:
    number = _number(value)
    return int(number) if number is not None else default


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text.rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)


def _pct(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "нет применимого знаменателя"
    return f"{100.0 * numerator / denominator:.1f}% ({numerator} из {denominator})"


def _claim(
    claim_id: str,
    kind: str,
    plain: str,
    technical: str,
    evidence_refs: list[str],
    *,
    limitations: list[str] | None = None,
    allowed_strength: str = "descriptive",
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "kind": kind,
        "plain_language": plain,
        "technical_language": technical,
        "allowed_strength": allowed_strength,
        "evidence_refs": evidence_refs,
        "limitations": limitations or [],
        "review_state": "unreviewed_draft",
        "reviewer": None,
        "adjudication": None,
    }


def _candidate_cards(report_data: dict[str, Any], handoff: dict[str, Any]) -> list[dict[str, Any]]:
    cards = handoff.get("candidate_cards")
    if isinstance(cards, list):
        return [card for card in cards if isinstance(card, dict)]
    changes = report_data.get("change_points")
    if not isinstance(changes, list):
        return []
    out = []
    for item in changes:
        if not isinstance(item, dict):
            continue
        pair_id = str(item.get("pair_id") or "")
        out.append({
            "pair_id": pair_id,
            "date": item.get("date"),
            "pose_bin": item.get("pose_bin"),
            "photo_a": item.get("photo_a"),
            "photo_b": item.get("photo_b"),
            "evidence_state": item.get("evidence_state") or item.get("status"),
            "p95_point_z": item.get("p95_point_z"),
            "days_delta": item.get("days_delta"),
            "alternative_explanations": [],
            "review_state": "unreviewed",
            "evidence_refs": [
                f"pair_metrics.csv#pair_id={pair_id}",
                f"change_points.json#pair_id={pair_id}",
            ],
        })
    return out


def build_publication_bundle(report_data: dict[str, Any], analysis_root: Path) -> dict[str, Any]:
    """Create a synchronized, evidence-linked publication draft bundle."""
    manifest = report_data.get("analysis_manifest")
    manifest = manifest if isinstance(manifest, dict) else {}
    summary = report_data.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    provenance = summary.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    handoff = _read_json(analysis_root / "journalist_handoff.json")
    technical_summary = _read_json(analysis_root / "technical_summary.json")
    degraded = _read_json(analysis_root / "degraded_modules.json")
    calibration_sensitivity = _read_json(analysis_root / "calibration_sensitivity.json")
    multiple_testing = _read_json(analysis_root / "multiple_testing.json")
    pose_leakage = _read_json(analysis_root / "pose_leakage_diagnostic.json")
    public_safety = _read_json(analysis_root / "public_safety_report.json")

    photo_count = _integer(manifest.get("main_record_count"))
    pair_count = _integer(summary.get("pair_count"))
    change_count = _integer(summary.get("change_count"))
    pose_counts = summary.get("pose_counts")
    pose_counts = pose_counts if isinstance(pose_counts, dict) else {}
    calibration_count = _integer(manifest.get("calibration_dataset_count"))
    candidate_cards = _candidate_cards(report_data, handoff)
    handoff_counts = handoff.get("counts")
    handoff_counts = handoff_counts if isinstance(handoff_counts, dict) else {}
    adjacent_count = _integer(handoff_counts.get("adjacent_pair_count"), pair_count)
    limited = handoff_counts.get("limited_adjacent_pairs")
    limited = limited if isinstance(limited, dict) else {}

    claims = [
        _claim(
            "METHOD-001",
            "method",
            f"В этом прогоне система обработала {photo_count} фотографий и не сравнивала все изображения без разбора.",
            f"Stage 2 manifest records main_record_count={photo_count}; pair planning is constrained by pose/applicability policy.",
            ["analysis_manifest.json", "pair_metrics.csv", "skipped_pairs.csv"],
            limitations=["Количество успешно извлечённых фото не описывает качество каждого отдельного кадра."],
        ),
        _claim(
            "METHOD-002",
            "method",
            f"Хронология разделена на {len(pose_counts)} фактически представленных ракурсных рядов из девяти предусмотренных групп.",
            "Primary comparisons are same-bin and use axis-specific residual-pose applicability before scoring.",
            ["analysis_manifest.json#pose_bins", "pair_metrics.csv#pose_bin", "app6/atlas/pose_gate_v2.csv"],
            limitations=["Слабое покрытие отдельного ракурса снижает применимость именно этого ряда."],
        ),
        _claim(
            "METHOD-003",
            "method",
            f"Измерения сопоставлялись с разбросом на {calibration_count} калибровочных наборах заведомо одного человека.",
            "Same-person references are used to estimate reconstruction/pose variability; calibration coverage remains pair-specific.",
            ["calibration_noise_model.json", "calibration_sensitivity.json", "analysis_manifest.json#calibration_dataset_count"],
            limitations=["Наличие калибровочных наборов не гарантирует полное покрытие каждой пары и каждого ракурса."],
        ),
        _claim(
            "RESULT-001",
            "result_summary",
            f"После проверок применимости в отчётном наборе сохранено {pair_count} сравнений, из них {adjacent_count} соседних по времени.",
            f"report_data.summary.pair_count={pair_count}; journalist_handoff adjacent_pair_count={adjacent_count}.",
            ["report_data.json#summary", "journalist_handoff.json#counts", "pair_metrics.csv"],
            limitations=["Число пар не равно числу независимых наблюдений; соседние кадры могут быть коррелированы."],
        ),
        _claim(
            "RESULT-002",
            "candidate_summary",
            (
                f"Система выделила {change_count} кандидатов устойчивых изменений для ручной проверки."
                if change_count
                else "В этом прогоне система не выделила кандидатов устойчивых изменений, прошедших публикационный gate."
            ),
            f"Stage 3 change_count={change_count}; only reportable adjacent evidence states are included.",
            ["change_points.json", "evidence_packets.json", "report_data.json#change_points"],
            limitations=[
                "Кандидат не устанавливает личность или причину изменения.",
                "Нулевое число кандидатов не доказывает отсутствие различий — оно относится только к данной конфигурации и данным.",
            ],
            allowed_strength="candidate_only",
        ),
        _claim(
            "LIMIT-001",
            "limitation",
            (
                "Часть соседних сравнений имела ограничения: качество — "
                f"{_pct(_integer(limited.get('quality')), adjacent_count)}, калибровка — "
                f"{_pct(_integer(limited.get('calibration')), adjacent_count)}, pose leakage — "
                f"{_pct(_integer(limited.get('pose_leakage')), adjacent_count)}."
            ),
            "Limitations are explicit evidence-state downgrades and must remain visible beside result counts.",
            ["journalist_handoff.json#counts", "degraded_modules.json", "pair_metrics.csv"],
            allowed_strength="limitation",
        ),
        _claim(
            "PROV-001",
            "provenance",
            (
                "Отчёт отдельно учитывает пары с конфликтами дат, near-duplicates и неполной цепочкой источника: "
                f"{_integer(provenance.get('date_conflict_pair_count'))}, "
                f"{_integer(provenance.get('near_duplicate_pair_count'))} и "
                f"{_integer(provenance.get('source_chain_incomplete_pair_count'))} соответственно."
            ),
            "Filename date remains authoritative; corroborating conflicts and dependent near-duplicates are not chronology evidence.",
            ["input_provenance.csv", "pair_metrics.csv", "report_data.json#summary.provenance"],
            limitations=["Неполный provenance ограничивает силу интерпретации даже при сильном геометрическом сигнале."],
        ),
    ]

    challenge_register = [
        {
            "challenge_id": "CH-001",
            "question": "Не объясняется ли сигнал просто другим поворотом головы?",
            "required_answer": "Показать pose bin, yaw/pitch/roll gaps, gate result и matched calibration references.",
            "evidence_refs": ["pair_metrics.csv", "app6/atlas/pose_gate_v2.csv", "calibration_noise_model.json"],
        },
        {
            "challenge_id": "CH-002",
            "question": "Не вызвано ли различие улыбкой, открытым ртом или мягкими тканями?",
            "required_answer": "Показать expression flags, visibility, identity-only channel и excluded/limited zones.",
            "evidence_refs": ["pair_metrics.csv", "evidence_packets.json", "point_motion/"],
        },
        {
            "challenge_id": "CH-003",
            "question": "Не является ли находка следствием плохого качества или старой фотографии?",
            "required_answer": "Показать quality status обоих кадров, degraded state и анализ по quality strata.",
            "evidence_refs": ["pair_metrics.csv", "degraded_modules.json", "quality_zone_pair_coverage.csv"],
        },
        {
            "challenge_id": "CH-004",
            "question": "Не выбраны ли пороги после просмотра результата?",
            "required_answer": "Показать frozen config/calibration version, LOPO/sensitivity и отсутствие main-data threshold tuning.",
            "evidence_refs": ["analysis_manifest.json", "calibration_sensitivity.json", "multiple_testing.json"],
        },
        {
            "challenge_id": "CH-005",
            "question": "Можно ли независимо воспроизвести вывод?",
            "required_answer": "Предоставить schema/config/code/model/dataset identifiers, exclusions и claim-to-artifact ledger.",
            "evidence_refs": ["analysis_manifest.json", "artifact_index.json", "report_validation.json"],
        },
        {
            "challenge_id": "CH-006",
            "question": "Какие наблюдения могли бы ослабить рабочую интерпретацию?",
            "required_answer": "Перечислить альтернативы, negative controls, cross-bin/source failures и reviewer disagreement.",
            "evidence_refs": ["evidence_packets.json", "cross_bin_corroboration.json", "manual_review_queue.csv"],
        },
    ]

    machine_packet = {
        "schema": MACHINE_PACKET_SCHEMA,
        "draft": True,
        "not_a_verdict": True,
        "instruction": "Audit each claim against evidence_refs; do not infer identity from candidate or cluster labels.",
        "claims": claims,
        "challenge_register": challenge_register,
        "source_artifacts": sorted({ref.split("#", 1)[0] for claim in claims for ref in claim["evidence_refs"]}),
        "method_assumptions": [
            "3D reconstruction is a model estimate, not direct anatomical measurement.",
            "Same-bin and pose-gap controls reduce but cannot prove complete removal of pose effects.",
            "Frame pairs are correlated; pair_count is not an independent-sample count.",
            "A reportable candidate still requires independent source/bin corroboration and human review.",
        ],
        "artifact_health": {
            "technical_summary_present": bool(technical_summary),
            "calibration_sensitivity_present": bool(calibration_sensitivity),
            "multiple_testing_present": bool(multiple_testing),
            "pose_leakage_diagnostic_present": bool(pose_leakage),
            "public_safety_status": public_safety.get("status") or "missing",
            "degraded_modules_present": bool(degraded),
        },
    }

    return {
        "schema": PUBLICATION_SCHEMA,
        "draft": True,
        "not_a_verdict": True,
        "human_review_required": True,
        "source_run": {
            "stage2_schema": manifest.get("schema_version"),
            "created_at_utc": manifest.get("created_at_utc"),
            "main_record_count": photo_count,
            "pair_count": pair_count,
            "change_count": change_count,
        },
        "audiences": {
            "general": "Plain language, examples and visual explanations without hiding limitations.",
            "technical": "Exact spaces, gates, calibration, statistics, versions and reproducibility.",
            "skeptical": "Strongest alternative explanations, falsification tests and missing evidence first.",
            "machine_review": "Structured claims, evidence pointers, assumptions and challenge register.",
        },
        "claims": claims,
        "candidate_cards": candidate_cards,
        "challenge_register": challenge_register,
        "glossary": GLOSSARY,
        "machine_review_packet": machine_packet,
        "editorial_voice_contract": {
            "narrator": "investigative_journalist_first_person",
            "preferred_pattern": "Мы собрали/проверили источник; система измерила; эксперт интерпретировал; рецензент проверил.",
            "forbidden_pattern": "Мы доказали — если evidence state остаётся candidate/limited/inconclusive.",
            "technical_partner_role": "Adds exact numbers, contracts, evidence refs and limitations without ghost-writing a verdict.",
        },
        "editorial_boundary": [
            "Method series is independent of the investigation result and may use separate demonstration data.",
            "Result story must not silently strengthen a candidate after editorial rewriting.",
            "External reporting/quotes are labeled separately from system measurements.",
            "Every published numerical sentence retains denominator and evidence references.",
        ],
    }


def _header(title: str, subtitle: str) -> list[str]:
    return [f"# {title}", "", f"> {subtitle}", "", "**Статус:** редакционный черновик; требуется техническая, юридическая и журналистская проверка.", ""]


def _render_public_method(bundle: dict[str, Any]) -> str:
    lines = _header(
        "Как проверять многолетний фотоархив и не обмануться качеством, ракурсом и мимикой",
        "Независимый от итогов расследования материал о методе.",
    )
    lines += [
        "## Короткий ответ",
        "",
        "Одна фотография не может надёжно ответить на сложный вопрос о многолетней истории лица. Поэтому метод строится не вокруг одного «процента сходства», а вокруг цепочки проверок: происхождение файла, дата, ракурс, качество, 3D-реконструкция, сопоставимость пары, калибровочный шум, хронология и независимая ручная проверка.",
        "",
        "## 1. Сначала проверяется не лицо, а фотография",
        "",
        "Для каждого файла фиксируются имя, хеш, источник, архивная ссылка, заявленная дата и возможные дубликаты. Дата из имени является осью исследования; EXIF и публикация могут её подтвердить или создать конфликт, но не переписывают её молча.",
        "",
        "## 2. Фотография превращается в повторно используемый набор измерений",
        "",
        "Модель оценивает трёхмерную поверхность и соответствующие точки лица. Это не КТ и не прямое измерение кости: результат зависит от изображения и модели. Поэтому исходная реконструкция сохраняется один раз вместе с проверками качества, а последующие сравнения используют сохранённые данные.",
        "",
        "## 3. Похожие ракурсы сравниваются отдельно",
        "",
        "Архив делится на девять групп поворота головы. Фронтальный кадр не становится прямым эталоном для профиля. Даже внутри одной группы проверяется разница yaw, pitch и roll; неподходящая пара исключается или получает ограниченный статус.",
        "",
        "## 4. Измеряется только то, что видно на обоих кадрах",
        "",
        "Если часть лица скрыта поворотом, волосами или границей кадра, она не должна давать число. Для пары используется пересечение видимых точек. Мимика, открытый рот и качество показываются как возможные объяснения различий.",
        "",
        "## 5. Шум оценивается на фотографиях заведомо одного человека",
        "",
        "Калибровочный набор показывает, насколько сама система меняет измерение из-за света, разрешения и небольшого различия углов. Сигнал в основном архиве сравнивается не с идеальным нулём, а с этим наблюдаемым разбросом. Отдельно проверяется, не зависит ли порог от одного человека или одной серии.",
        "",
        "## 6. Хронология важнее одиночного скачка",
        "",
        "Система различает соседние кадры, устойчивое изменение, постепенный дрейф и возврат к прежнему состоянию. Короткий временной интервал может сделать сигнал приоритетным для проверки, но не объясняет его причину автоматически.",
        "",
        "## 7. Большое число проверок требует статистической дисциплины",
        "",
        "Когда одновременно проверяются сотни пар и точек, отдельные высокие значения возникают случайно. Поэтому применяется контроль множественных сравнений, а количество пар не выдаётся за количество независимых наблюдений.",
        "",
        "## 8. Что демонстрировать на независимых примерах",
        "",
        "Метод можно показывать на отдельном наборе лицензированных фотографий заведомо одного публичного человека — например, Дональда Трампа или Илона Маска — исключительно для демонстрации влияния ракурса, качества и времени. Такой пример не должен содержать выводов об этих людях и не используется для настройки порогов основного расследования.",
        "",
        "## 9. Что метод принципиально не доказывает",
        "",
        "3D-реконструкция не является медицинским сканированием. Порог не называет причину изменения. Cluster не является именем человека. Даже сильный кандидат требует проверки оригиналов, источников, альтернативных объяснений, независимого ракурса и внешнего рецензента.",
        "",
        "## Термины",
        "",
    ]
    for key, value in bundle["glossary"].items():
        lines.append(f"- **{key}:** {value}")
    return "\n".join(lines)


def _render_technical(bundle: dict[str, Any]) -> str:
    source = bundle["source_run"]
    lines = _header(
        "Техническое приложение: воспроизводимость и границы применимости",
        "Материал для специалистов по computer vision, статистике и forensic comparison.",
    )
    lines += [
        "## Зафиксированный контекст прогона",
        "",
        f"- Stage 2 schema: `{source.get('stage2_schema') or 'нет данных'}`",
        f"- Создан: `{source.get('created_at_utc') or 'нет данных'}`",
        f"- Фото: {source.get('main_record_count', 0)}",
        f"- Сохранённых pair rows: {source.get('pair_count', 0)}",
        f"- Reportable change candidates: {source.get('change_count', 0)}",
        "",
        "## Контракт измерения",
        "",
        "- Primary coordinates: raw object-normalized LDM106/LDM134.",
        "- Pair alignment: iteratively trimmed Kabsch, no scale.",
        "- Pair applicability: same pose bin, axis-specific pose gaps, common visibility.",
        "- Calibration: same-person references, person-balanced interpretation, sensitivity/LOPO required.",
        "- Multiple testing: versioned FDR report; p95 point statistic retains calibrated point count.",
        "- Provenance: filename date authority; EXIF/source claim corroboration; conflicts and near-duplicates cannot silently enter chronology evidence.",
        "",
        "## Claims ledger",
        "",
    ]
    for claim in bundle["claims"]:
        lines += [
            f"### {claim['claim_id']} — {claim['kind']}",
            "",
            claim["technical_language"],
            "",
            f"**Допустимая сила формулировки:** `{claim['allowed_strength']}`",
            "",
            "**Evidence:** " + ", ".join(f"`{ref}`" for ref in claim["evidence_refs"]),
            "",
            "**Ограничения:** " + ("; ".join(claim["limitations"]) or "не указаны"),
            "",
        ]
    lines += ["## Обязательные независимые проверки", ""]
    for challenge in bundle["challenge_register"]:
        lines += [
            f"- **{challenge['challenge_id']}: {challenge['question']}**",
            f"  - Требуемый ответ: {challenge['required_answer']}",
            "  - Evidence: " + ", ".join(f"`{ref}`" for ref in challenge["evidence_refs"]),
        ]
    return "\n".join(lines)


def _render_results(bundle: dict[str, Any]) -> str:
    lines = _header(
        "Черновик рассказа о результатах",
        "Тезисы для совместной работы журналиста и технического специалиста; не готовая публикация.",
    )
    lines += [
        "## Лид — заполнить после редакционной проверки",
        "",
        "Мы начали это исследование не с заранее выбранного ответа, а с проверки того, что вообще можно надёжно измерить на фотографиях разных лет. Мы собрали и датировали архив; система выполнила измерения; технические специалисты проверили применимость метода; интерпретация каждого приоритетного эпизода остаётся отдельным журналистским и экспертным шагом.",
        "",
        "[Дополнить двумя предложениями о происхождении архива и редакционном вопросе. Не начинать с самого тревожного числа и не называть candidate доказанным фактом.]",
        "",
        "## Кто за что отвечает в тексте",
        "",
        "- **Журналист:** источник, контекст, вопросы, внешние публикации и понятный рассказ.",
        "- **Система:** воспроизводимые измерения и автоматические статусы.",
        "- **Технический специалист:** применимость, calibration, статистика и ограничения.",
        "- **Независимый рецензент:** проверка оригиналов, альтернатив и disagreement.",
        "",
        "## Что было сделано",
        "",
    ]
    for claim in bundle["claims"]:
        if claim["kind"] == "method":
            lines += [f"- {claim['plain_language']}  ", f"  Evidence: `{claim['evidence_refs'][0]}`"]
    lines += ["", "## Что получилось в этом прогоне", ""]
    for claim in bundle["claims"]:
        if claim["kind"] in {"result_summary", "candidate_summary", "provenance"}:
            lines += [f"- {claim['plain_language']}  ", "  Evidence: " + ", ".join(f"`{ref}`" for ref in claim["evidence_refs"])]
    lines += ["", "## Ограничения, которые должны остаться в основном тексте", ""]
    for claim in bundle["claims"]:
        if claim["kind"] == "limitation":
            lines.append(f"- {claim['plain_language']}")
        for limitation in claim["limitations"]:
            lines.append(f"- {limitation}")
    lines += ["", "## Карточки кандидатов для ручного разбора", ""]
    cards = bundle["candidate_cards"]
    if not cards:
        lines.append("В текущем publication gate нет карточек кандидатов. Это не доказывает отсутствие различий и относится только к данному прогону.")
    for card in cards[:25]:
        lines += [
            f"### {card.get('date') or 'дата не указана'} · {card.get('pose_bin') or 'pose unknown'}",
            "",
            f"- Пара: `{card.get('photo_a')}` → `{card.get('photo_b')}`",
            f"- Статус: `{card.get('evidence_state')}`",
            f"- P95 point z: `{card.get('p95_point_z')}`",
            f"- Дней: `{card.get('days_delta')}`",
            f"- Review: `{card.get('review_state') or 'unreviewed'}`",
            "- Альтернативы: " + (", ".join(card.get("alternative_explanations") or []) or "требуют заполнения reviewer"),
            "- Evidence: " + ", ".join(f"`{ref}`" for ref in card.get("evidence_refs") or []),
            "",
            "[Журналистская часть: проверить оригиналы, источник, соседние даты, независимый ракурс и только затем описывать наблюдение понятным языком.]",
            "",
        ]
    return "\n".join(lines)


def _render_skeptic_qa(bundle: dict[str, Any]) -> str:
    lines = _header(
        "Вопросы скептического рецензента",
        "Этот документ должен усиливать проверяемость, а не защищать заранее выбранную версию.",
    )
    lines += [
        "## Принцип",
        "",
        "Самый сильный текст не тот, который избегает неудобных вопросов, а тот, который заранее формулирует их в проверяемом виде и показывает, где лежит ответ.",
        "",
    ]
    for challenge in bundle["challenge_register"]:
        lines += [
            f"## {challenge['challenge_id']}. {challenge['question']}",
            "",
            challenge["required_answer"],
            "",
            "Проверить: " + ", ".join(f"`{ref}`" for ref in challenge["evidence_refs"]),
            "",
        ]
    lines += [
        "## Что должно привести к ослаблению или отзыву тезиса",
        "",
        "- конфликт даты или неподтверждённый источник;",
        "- воспроизведение того же сигнала на same-person negative control;",
        "- исчезновение эффекта после корректного pose/quality matching;",
        "- отсутствие эффекта в независимом ракурсе или источнике при заявленной устойчивости;",
        "- сильная зависимость результата от одного порога, одной серии или одной calibration person;",
        "- ошибка detector/crop/reconstruction, видимая на overlay;",
        "- несогласие независимых reviewers без разрешённой adjudication.",
    ]
    return "\n".join(lines)


def _render_demo_protocol() -> str:
    lines = _header(
        "Протокол независимой демонстрации метода",
        "Примеры для объяснения алгоритма не должны зависеть от результатов основного расследования.",
    )
    lines += [
        "## Цель",
        "",
        "Показать аудитории, как ракурс, разрешение, компрессия, мимика и временной интервал влияют на измерения, не делая выводов о человеке из демонстрационного набора.",
        "",
        "## Допустимый набор",
        "",
        "- лицензированные фотографии одного заведомо известного публичного человека;",
        "- либо фотографии автора/участника с информированным согласием;",
        "- несколько лет, источников, качеств и все доступные pose bins;",
        "- отдельный manifest и provenance;",
        "- никакого смешивания с calibration/main investigation thresholds.",
        "",
        "Публичные фигуры вроде Дональда Трампа или Илона Маска могут использоваться только как понятный same-person demonstration set при наличии законного источника. Демонстрация не должна содержать утверждений об их здоровье, личности или использовании каких-либо средств изменения внешности.",
        "",
        "## Серия демонстраций",
        "",
        "1. Один человек, близкие углы и хорошее качество — ожидаемый baseline.",
        "2. Тот же человек, различный yaw/pitch/roll — зачем нужен pose gate.",
        "3. Тот же человек, улыбка/открытый рот — какие зоны становятся limited.",
        "4. Оригинал и повторно сжатая копия — влияние source quality.",
        "5. Два соседних кадра одного события — зависимость наблюдений.",
        "6. Искусственно переставленная A-B-A последовательность из разрешённого test set — проверка return detector.",
        "7. Blind review: даты/имена скрыты до фиксации наблюдения.",
        "",
        "## Что публиковать рядом с каждым примером",
        "",
        "- исходные изображения и права использования;",
        "- pose/quality/provenance;",
        "- что сравнивалось и что было исключено;",
        "- raw measurement, calibration range и uncertainty;",
        "- expected result до запуска;",
        "- фактический result;",
        "- объяснение расхождения;",
        "- ссылка на machine-readable artifact.",
    ]
    return "\n".join(lines)


def _lint_drafts(payloads: dict[str, str]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    for name, text in payloads.items():
        lowered = text.lower()
        for pattern in ASSERTIVE_FORBIDDEN_PATTERNS:
            if pattern in lowered:
                violations.append({"file": name, "pattern": pattern})
    return {
        "schema": "deeputin-publication-draft-lint-v1.0",
        "status": "pass" if not violations else "fail",
        "violation_count": len(violations),
        "violations": violations,
        "policy": "Topic terms are allowed in neutral context; unsupported assertive conclusions are blocked.",
    }


def write_publication_drafts(out: Path, report_data: dict[str, Any], analysis_root: Path) -> dict[str, Any]:
    """Write publication drafts and return a compact manifest for report_data."""
    drafts = out / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    bundle = build_publication_bundle(report_data, analysis_root)
    markdown = {
        "01_METHOD_EXPLAINER_PUBLIC.md": _render_public_method(bundle),
        "02_METHOD_TECHNICAL_APPENDIX.md": _render_technical(bundle),
        "03_RESULTS_STORY_DRAFT.md": _render_results(bundle),
        "04_SKEPTIC_QA.md": _render_skeptic_qa(bundle),
        "05_EXAMPLE_DEMONSTRATION_PROTOCOL.md": _render_demo_protocol(),
    }
    lint = _lint_drafts(markdown)
    if lint["status"] != "pass":
        raise RuntimeError(f"publication draft lint failed: {lint['violations']}")

    atomic_json(drafts / "publication_bundle.json", bundle)
    atomic_json(drafts / "claims_ledger.json", {"schema": CLAIMS_SCHEMA, "claims": bundle["claims"]})
    atomic_json(drafts / "machine_review_packet.json", bundle["machine_review_packet"])
    atomic_json(drafts / "glossary.json", {"schema": "deeputin-publication-glossary-v1.0", "terms": GLOSSARY})
    atomic_json(drafts / "draft_lint.json", lint)
    for name, text in markdown.items():
        _atomic_text(drafts / name, text)

    readme = """# Publication drafts

These files are deterministic editorial drafts generated from Stage 2/3 artifacts.
They are not final articles and not identity/material/medical verdicts.

Reading order:

1. `01_METHOD_EXPLAINER_PUBLIC.md` — plain-language method series seed;
2. `02_METHOD_TECHNICAL_APPENDIX.md` — specialist/reproducibility layer;
3. `03_RESULTS_STORY_DRAFT.md` — journalist + technical editor handoff;
4. `04_SKEPTIC_QA.md` — adversarial questions and falsification checks;
5. `05_EXAMPLE_DEMONSTRATION_PROTOCOL.md` — independent examples;
6. `claims_ledger.json` — claim-to-evidence map;
7. `machine_review_packet.json` — structured input for AI/static review.

No draft may be published before provenance, technical, legal and editorial review.
"""
    _atomic_text(drafts / "README.md", readme)

    names = sorted(path.name for path in drafts.iterdir() if path.is_file())
    artifacts = [
        {"name": name, "size_bytes": (drafts / name).stat().st_size, "digest": digest_file(drafts / name)}
        for name in names
    ]
    manifest = {
        "schema": PUBLICATION_SCHEMA,
        "draft": True,
        "not_a_verdict": True,
        "human_review_required": True,
        "directory": "drafts",
        "file_count": len(artifacts),
        "files": artifacts,
        "audiences": list(bundle["audiences"]),
        "claim_count": len(bundle["claims"]),
        "candidate_card_count": len(bundle["candidate_cards"]),
        "lint_status": lint["status"],
    }
    atomic_json(out / "publication_drafts_manifest.json", manifest)
    return manifest


__all__ = [
    "ASSERTIVE_FORBIDDEN_PATTERNS",
    "PUBLICATION_SCHEMA",
    "build_publication_bundle",
    "write_publication_drafts",
]
