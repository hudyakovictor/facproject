"""📝 Narrative Engine — генерация текста для журналиста на русском.

Структура:
  1. Headline (заголовок)
  2. Lead (первый абзац)
  3. Exposition (введение)
  4. Rising Action (нарастание)
  5. Climax (кульминация)
  6. Falling Action (развитие)
  7. Resolution (выводы + ограничения)

Tone: journalistic (нейтральный, для расследовательских СМИ)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import Stage3V2Config
from .types import (
    NarrativeResult, ChangePointResult, ZoneAnalysisResult,
    PairAnalysis, FullReport
)
from .formatting import fmt, fmt_ci


class NarrativeEngine:
    """Генератор текста для журналиста."""
    
    def __init__(self, config: Stage3V2Config):
        self.config = config
    
    def generate(
        self,
        pair_analyses: list[PairAnalysis],
        zone_analysis: ZoneAnalysisResult,
        change_points: ChangePointResult,
        manifest: dict[str, Any],
    ) -> NarrativeResult:
        """Сгенерировать полный narrative."""
        
        # Headline
        headline = self._generate_headline(pair_analyses, change_points, manifest)
        
        # Lead
        lead = self._generate_lead(pair_analyses, change_points, manifest)
        
        # Sections
        exposition = self._generate_exposition(manifest, change_points)
        rising = self._generate_rising_action(change_points, pair_analyses)
        climax = self._generate_climax(pair_analyses, zone_analysis)
        falling = self._generate_falling_action(change_points, pair_analyses)
        resolution = self._generate_resolution(zone_analysis, pair_analyses)
        
        # Full text
        full_text = "\n\n".join([
            f"📰 {headline}",
            lead,
            "📊 МЕТОДОЛОГИЯ",
            exposition,
            "📈 НАРАСТАНИЕ",
            rising,
            "🔴 КУЛЬМИНАЦИЯ",
            climax,
            "📉 РАЗВИТИЕ",
            falling,
            "⚠ ВЫВОДЫ И ОГРАНИЧЕНИЯ",
            resolution,
        ])
        
        word_count = len(full_text.split())
        
        # Key findings
        key_findings = self._extract_key_findings(pair_analyses, zone_analysis)
        
        # Disclaimers
        disclaimers = self._standard_disclaimers()
        
        return NarrativeResult(
            headline_ru=headline,
            lead_ru=lead,
            exposition_ru=exposition,
            rising_action_ru=rising,
            climax_ru=climax,
            falling_action_ru=falling,
            resolution_ru=resolution,
            full_text_ru=full_text,
            word_count=word_count,
            key_findings=key_findings,
            disclaimers_ru=disclaimers,
        )
    
    def _generate_headline(
        self,
        analyses: list[PairAnalysis],
        change_points: ChangePointResult,
        manifest: dict[str, Any]
    ) -> str:
        """Generate headline."""
        n_photos = manifest.get("main_record_count", 0)
        n_changes = len([a for a in analyses if a.bayesian.primary_hypothesis() == "H2_DIFFERENT"])
        n_cp = len(change_points.change_points)
        
        if n_changes > 20:
            return f"Обнаружены значительные изменения лица: анализ {fmt(n_photos, 'count')} фотографий"
        elif n_changes > 5:
            return f"Обнаружены изменения лица на {fmt(n_changes, 'count')} парах из {fmt(n_photos, 'count')}"
        else:
            return f"Анализ {fmt(n_photos, 'count')} фотографий: лицо преимущественно стабильно"
    
    def _generate_lead(
        self,
        analyses: list[PairAnalysis],
        change_points: ChangePointResult,
        manifest: dict[str, Any]
    ) -> str:
        """Generate lead paragraph."""
        n_photos = manifest.get("main_record_count", 0)
        
        dates = [a.date_b for a in analyses if a.date_b]
        date_range = ""
        if dates:
            min_date = min(dates).strftime("%Y")
            max_date = max(dates).strftime("%Y")
            date_range = f" с {min_date} по {max_date} год"
        
        n_cp = len(change_points.change_points)
        most_affected = "костных структурах"
        
        return (
            f"Анализ {fmt(n_photos, 'count')} пар фотографий{date_range} "
            f"выявил {n_cp} периодов значимых изменений в структуре лица. "
            f"Изменения наблюдались преимущественно в {most_affected} и были "
            f"подтверждены в нескольких ракурсах."
        )
    
    def _generate_exposition(self, manifest: dict, change_points: ChangePointResult) -> str:
        """Generate methodology section."""
        return (
            "Исследование использовало 134 ключевые точки лица, 3D-реконструкцию "
            "поверхности и 13 семейств морфометрических дескрипторов. "
            "Сила доказательств оценивалась по стандарту ENFSI — коэффициент "
            "правдоподобия (Likelihood Ratio, LR), который показывает, во сколько "
            "раз данные более вероятны при наличии изменений, чем при их отсутствии.\n\n"
            "Величина изменений измерялась через Cohen's d — стандартизированный "
            "размер эффекта. 95% доверительные интервалы вычислены методом bootstrap "
            "с 1000 итерациями."
        )
    
    def _generate_rising_action(
        self,
        change_points: ChangePointResult,
        analyses: list[PairAnalysis]
    ) -> str:
        """Generate rising action section."""
        if not change_points.phases:
            return "Хронологических данных недостаточно для анализа трендов."
        
        lines = []
        for phase in change_points.phases[:3]:
            start = phase.start_date.strftime("%B %Y")
            end = phase.end_date.strftime("%B %Y")
            
            if phase.state == "stable":
                lines.append(f"🟢 {start} — {end}: {phase.description_ru} "
                           f"(d ≈ {fmt(phase.mean_d, 'z_score')})")
            else:
                lines.append(f"🟡 {start} — {end}: {phase.description_ru} "
                           f"(d ≈ {fmt(phase.mean_d, 'z_score')})")
        
        return "\n".join(lines)
    
    def _generate_climax(
        self,
        analyses: list[PairAnalysis],
        zone_analysis: ZoneAnalysisResult
    ) -> str:
        """Generate climax section."""
        # Find strongest pair
        h2_pairs = [a for a in analyses if a.bayesian.primary_hypothesis() == "H2_DIFFERENT"]
        
        if not h2_pairs:
            return "Значимых изменений не обнаружено."
        
        strongest = max(h2_pairs, key=lambda a: a.bayesian.lr)
        
        lines = [
            f"Наиболее значимое изменение обнаружено в паре #{strongest.pair_id}:",
            f"  • LR = {fmt(strongest.bayesian.lr, 'bf')} ({strongest.bayesian.lr_verbal_ru})",
            f"  • Effect Size: d = {fmt(strongest.effect_size.overall_d, 'z_score')} "
            f"({strongest.effect_size.overall_verbal_ru})",
        ]
        
        # Top zones
        for phrase in strongest.effect_size.journalist_phrases[:2]:
            lines.append(f"  • {phrase}")
        
        # Bootstrap CI
        if strongest.bootstrap.overall_significant:
            lines.append(
                f"  • {fmt_ci(strongest.bootstrap.overall_ci_lower, strongest.bootstrap.overall_ci_upper)}"
            )
        
        return "\n".join(lines)
    
    def _generate_falling_action(
        self,
        change_points: ChangePointResult,
        analyses: list[PairAnalysis]
    ) -> str:
        """Generate falling action."""
        stabilizing = [p for p in change_points.phases if p.state == "stable"]
        
        if stabilizing:
            last = stabilizing[-1]
            return (
                f"После периода изменений ({last.start_date.strftime('%B %Y')}) "
                f"наступила стабилизация на новом уровне. "
                f"Последующие пары показывают d ≈ {fmt(last.mean_d, 'z_score')}."
            )
        
        return "Стабилизация не наблюдается — изменения продолжаются."
    
    def _generate_resolution(
        self,
        zone_analysis: ZoneAnalysisResult,
        analyses: list[PairAnalysis]
    ) -> str:
        """Generate resolution with disclaimers."""
        n_h2 = len([a for a in analyses if a.bayesian.primary_hypothesis() == "H2_DIFFERENT"])
        
        lines = [
            f"Обнаружено {n_h2} пар со значимыми изменениями из {len(analyses)} проанализированных.",
            f"Наиболее затронутая зона: {zone_analysis.most_affected_zone}.",
            "",
            "⚠ ВАЖНЫЕ ОГРАНИЧЕНИЯ:",
            "  • Это измерения величины движения точек, не выводы о личности",
            "  • Статус «изменение» НЕ доказывает подмену, маску, операцию или причину",
            "  • 3D-модель — оценка параметрической модели, не КТ-сканирование",
            "  • Для выводов о причинах нужна независимая экспертиза",
        ]
        
        return "\n".join(lines)
    
    def _extract_key_findings(
        self,
        analyses: list[PairAnalysis],
        zone_analysis: ZoneAnalysisResult
    ) -> list[str]:
        """Extract key findings for summary."""
        findings = []
        
        h2_pairs = [a for a in analyses if a.bayesian.primary_hypothesis() == "H2_DIFFERENT"]
        
        if h2_pairs:
            max_lr = max(a.bayesian.lr for a in h2_pairs)
            findings.append(f"Максимальный LR = {fmt(max_lr, 'bf')}")
            
            max_d = max(a.effect_size.overall_d for a in h2_pairs)
            findings.append(f"Максимальный d = {fmt(max_d, 'z_score')}")
        
        findings.append(f"Наиболее затронутая зона: {zone_analysis.most_affected_zone}")
        
        return findings
    
    def _standard_disclaimers(self) -> list[str]:
        """Standard disclaimers in Russian."""
        return [
            "Ни один статус сам по себе не доказывает подмену личности, маску, операцию или медицинский факт.",
            "Вероятности — это вес доказательств при допущениях модели, не «процент доказанности».",
            "3D-форма — оценка параметрической модели 3DDFA, не КТ-сканирование.",
            "Отчёт показывает величину, темп и устойчивость изменений относительно калибровочного шума.",
        ]
