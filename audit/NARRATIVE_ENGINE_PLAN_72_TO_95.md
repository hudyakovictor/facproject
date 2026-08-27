# 🎯 ПЛАН: 72 → 95+ (СИСТЕМА ГЕНЕРАЦИИ ТЕКСТОВ ДЛЯ ЖУРНАЛИСТА)

**Дата:** 2026-08-27  
**Текущий балл:** 72/100  
**Целевой балл:** 95+/100  
**Timeline:** 8-10 дней реализации

---

## 📊 ТЕКУЩЕЕ СОСТОЯНИЕ (72/100)

```
✅ СИЛЬНОЕ (88-100):                    ❌ СЛАБОЕ (35-59):
  Русский язык: 100                       Narrative Arc: 40
  Анатомические описания: 95              Timeline: 35
  Journalist phrases: 92                  Cross-reference: 45
  Number formatting: 95                   Variability: 50
  Disclaimers: 90                         Tone adaptation: 40
                                          Audience adaptation: 35
⚠ СРЕДНЕЕ (60-84):
  Контекст: 75                            ⚠ НУЖДАЕТСЯ В КОДЕ:
  Evidence summary: 80                    Template engine: 75 (концепт)
  Шаблоны: 75 (концепт)                   Generation: 65 (концепт)
  Контроль качества: 65                   Multi-pair: 55
```

---

## 🎯 ПЛАН: 7 ШАГОВ К 95+

```
ШАГ 1: Narrative Engine          (+18 баллов)  ← 3 дня
ШАГ 2: Cross-Reference System    (+8 баллов)   ← 1 день
ШАГ 3: Template Variations       (+5 баллов)   ← 1 день
ШАГ 4: Tone/Audience Adaptation  (+5 баллов)   ← 1 день
ШАГ 5: Executive Summary         (+3 балла)    ← 0.5 дня
ШАГ 6: Quality Control           (+2 балла)    ← 0.5 дня
ШАГ 7: Export Pipeline           (+2 балла)    ← 0.5 дня

ИТОГО: +43 балла → 72 + 43 = 115 (capping at 95+)
```

---

## ШАГ 1: NARRATIVE ENGINE (3 дня, +18 баллов)

### 1.1 Timeline Builder (1 день)

**Что:** Строит хронологическую линию из всех пар

```python
class TimelineBuilder:
    """Строит timeline из всех обработанных пар"""
    
    def build(self, pairs_with_results: list) -> Timeline:
        """
        Вход: список пар с результатами Stage 3
        Выход: хронологическая линия с событиями
        """
        
        # 1. Сортировка по дате
        sorted_pairs = sorted(pairs_with_results, 
                              key=lambda p: p.date_a)
        
        # 2. Обнаружение событий (значимых изменений)
        events = []
        for pair in sorted_pairs:
            if self._is_significant_event(pair):
                events.append(TimelineEvent(
                    date=pair.date_b,
                    pair_id=pair.id,
                    event_type=self._classify_event(pair),
                    zones_affected=pair.significant_zones,
                    magnitude=pair.overall_magnitude,
                    confidence=pair.confidence_score,
                    description=self._describe_event(pair)
                ))
        
        # 3. Кластеризация событий (близкие по времени = один кластер)
        clusters = self._cluster_events(events, max_gap_days=14)
        
        # 4. Определение фаз (стабильность → изменение → стабилизация)
        phases = self._identify_phases(sorted_pairs, events)
        
        return Timeline(
            start_date=sorted_pairs[0].date_a,
            end_date=sorted_pairs[-1].date_b,
            total_pairs=len(sorted_pairs),
            events=events,
            clusters=clusters,
            phases=phases,
            overall_trend=self._calculate_trend(sorted_pairs)
        )
    
    def _is_significant_event(self, pair) -> bool:
        """Является ли пара значимым событием"""
        return (
            pair.primary_hypothesis == "H2_DIFFERENT" and
            pair.confidence_score >= 5 and
            pair.p95_z > 3.0
        )
    
    def _classify_event(self, pair) -> str:
        """Классифицировать тип события"""
        if pair.coherent_motion > 0.5:
            return "structural_change"
        elif pair.mesh_rmse > 0.003:
            return "surface_change"
        elif pair.descriptor_p95_z > 4.0:
            return "texture_change"
        else:
            return "subtle_change"
    
    def _cluster_events(self, events, max_gap_days=14):
        """Кластеризовать близкие события"""
        clusters = []
        current_cluster = [events[0]]
        
        for event in events[1:]:
            gap = (event.date - current_cluster[-1].date).days
            if gap <= max_gap_days:
                current_cluster.append(event)
            else:
                clusters.append(EventCluster(
                    start=current_cluster[0].date,
                    end=current_cluster[-1].date,
                    events=current_cluster,
                    summary=self._summarize_cluster(current_cluster)
                ))
                current_cluster = [event]
        
        if current_cluster:
            clusters.append(EventCluster(
                start=current_cluster[0].date,
                end=current_cluster[-1].date,
                events=current_cluster,
                summary=self._summarize_cluster(current_cluster)
            ))
        
        return clusters
    
    def _identify_phases(self, pairs, events):
        """Определить фазы: стабильность → изменение → стабилизация"""
        phases = []
        
        # Разбить timeline на сегменты по событиям
        event_dates = [e.date for e in events]
        
        current_phase_start = pairs[0].date_a
        current_state = "stable"
        
        for pair in pairs:
            if pair.date_b in event_dates:
                # Переход в новую фазу
                phases.append(Phase(
                    start=current_phase_start,
                    end=pair.date_b,
                    state=current_state,
                    pairs_count=self._count_pairs_in_range(
                        pairs, current_phase_start, pair.date_b
                    )
                ))
                current_phase_start = pair.date_b
                current_state = "changing" if current_state == "stable" else "stabilizing"
        
        return phases
```

**Пример вывода:**
```
TIMELINE: 2015-03-15 → 2020-11-22 (5 лет, 8 месяцев)

ФАЗЫ:
  🟢 2015-03 → 2016-06: Стабильность (142 пары, 0 изменений)
  🟡 2016-06 → 2016-09: Изменения (3 кластера событий)
  🟢 2016-09 → 2018-01: Стабилизация (312 пар, 1 слабое изменение)
  🔴 2018-01 → 2018-06: Значительные изменения (2 кластера)
  🟢 2018-06 → 2020-11: Стабильность (1,444 пары)

КЛАСТЕРЫ СОБЫТИЙ:
  📅 2016-07-12 → 2016-07-28 (16 дней, 4 события)
     → Изменения в области скул и глаз
     → Подтверждено в 3 ракурсах
  
  📅 2018-02-15 → 2018-03-20 (33 дня, 7 событий)
     → Значительные изменения челюсти и подбородка
     → Подтверждено в 5 ракурсах
```

---

### 1.2 Narrative Arc Builder (1 день)

**Что:** Создаёт структуру повествования (завязка → развитие → кульминация → развязка)

```python
class NarrativeArcBuilder:
    """Строит narrative arc из timeline"""
    
    def build(self, timeline: Timeline, style="journalistic") -> NarrativeArc:
        """
        Структура:
          1. Exposition (введение) — начальный контекст
          2. Rising Action — нарастание сигналов
          3. Climax — главные обнаружения
          4. Falling Action — последствия, подтверждение
          5. Resolution — выводы, ограничения
        """
        
        arc = NarrativeArc()
        
        # 1. EXPOSITION: Начальный контекст
        arc.exposition = ExpositionSection(
            headline=self._generate_headline(timeline),
            lead=self._generate_lead(timeline),
            context=self._generate_context(timeline),
            methodology_brief=self._methodology_brief()
        )
        
        # 2. RISING ACTION: Нарастание
        early_events = [e for e in timeline.events 
                        if e.date < timeline.midpoint]
        arc.rising_action = RisingActionSection(
            first_signals=self._describe_first_signals(early_events),
            escalation=self._describe_escalation(timeline),
            key_pairs=self._select_key_pairs(timeline, "rising")
        )
        
        # 3. CLIMAX: Главное обнаружение
        major_events = [e for e in timeline.events 
                        if e.magnitude > 0.7 and e.confidence > 6]
        arc.climax = ClimaxSection(
            main_finding=self._describe_main_finding(major_events),
            evidence=self._gather_evidence(major_events),
            cross_confirmation=self._cross_confirm(major_events),
            key_pairs=self._select_key_pairs(timeline, "climax")
        )
        
        # 4. FALLING ACTION: Подтверждение
        later_events = [e for e in timeline.events 
                        if e.date > timeline.midpoint]
        arc.falling_action = FallingActionSection(
            confirmations=self._describe_confirmations(later_events),
            stabilization=self._describe_stabilization(timeline),
            alternative_explanations=self._list_alternatives(timeline)
        )
        
        # 5. RESOLUTION: Выводы
        arc.resolution = ResolutionSection(
            summary=self._generate_summary(timeline),
            limitations=self._list_limitations(timeline),
            disclaimers=self._standard_disclaimers(),
            what_this_means=self._explain_implications(timeline)
        )
        
        return arc
    
    def _generate_headline(self, timeline: Timeline) -> str:
        """Сгенерировать заголовок"""
        total_events = len(timeline.events)
        years = timeline.duration_years
        
        if total_events > 10:
            return f"Обнаружены значительные изменения лица на {total_events} фотографиях за {years:.1f} лет"
        elif total_events > 3:
            return f"Обнаружены изменения лица: анализ {timeline.total_pairs} фотографий за {years:.1f} лет"
        else:
            return f"Анализ {timeline.total_pairs} фотографий: лицо преимущественно стабильно"
    
    def _generate_lead(self, timeline: Timeline) -> str:
        """Сгенерировать лид (первый абзац)"""
        return (
            f"Анализ {timeline.total_pairs} фотографий, снятых в период "
            f"с {timeline.start_date:%d.%m.%Y} по {timeline.end_date:%d.%m.%Y}, "
            f"выявил {len(timeline.events)} эпизодов значимых изменений "
            f"в структуре лица. Изменения наблюдались преимущественно "
            f"в области {timeline.most_affected_zone} и были подтверждены "
            f"в {timeline.cross_confirmation_count} различных ракурсах."
        )
```

**Пример Narrative Arc:**
```
📖 STRUCTURE OF THE INVESTIGATION:

1. EXPOSITION (Введение)
   "FROM CONSPIRACY THEORIES TO AN INVESTIGATION SPANNING 1900+ PHOTOS"
   → Контекст, методология, оговорки

2. RISING ACTION (Нарастание)
   "ПЕРВЫЕ СИГНАЛЫ: 2016"
   → Первые слабые изменения в области скул
   → Подтверждение в 2 ракурсах
   → Возможные объяснения (вес, возраст)

3. CLIMAX (Кульминация)
   "ЗНАЧИТЕЛЬНЫЕ ИЗМЕНЕНИЯ: ФЕВРАЛЬ-МАРТ 2018"
   → 7 пар с p95_z > 5.0
   → Изменения челюсти и подбородка
   → Подтверждено в 5 ракурсах
   → Когерентное движение точек

4. FALLING ACTION (Развитие)
   "ПОДТВЕРЖДЕНИЕ И СТАБИЛИЗАЦИЯ"
   → Последующие пары подтверждают изменения
   → Стабилизация на новом уровне
   → Альтернативные объяснения рассмотрены

5. RESOLUTION (Выводы)
   "ЧТО ЭТО ОЗНАЧАЕТ И ЧЕГО НЕ ОЗНАЧАЕТ"
   → Измерения, не выводы о личности
   → Ограничения методологии
   → Нужна независимая экспертиза
```

---

### 1.3 Story Generator (1 день)

**Что:** Генерирует финальный текст из Narrative Arc

```python
class StoryGenerator:
    """Генерирует связный текст из Narrative Arc"""
    
    def generate(self, arc: NarrativeArc, config: StoryConfig) -> Story:
        """Генерация полного текста"""
        
        sections = []
        
        # Заголовок
        sections.append(Section(
            type="headline",
            text=arc.exposition.headline
        ))
        
        # Подзаголовок
        sections.append(Section(
            type="subheadline",
            text=arc.exposition.lead
        ))
        
        # Введение
        sections.append(Section(
            type="exposition",
            text=self._render_exposition(arc.exposition, config)
        ))
        
        # Нарастание
        for i, signal in enumerate(arc.rising_action.first_signals):
            sections.append(Section(
                type="rising_action",
                heading=f"Сигнал #{i+1}: {signal.date:%B %Y}",
                text=self._render_signal(signal, config),
                evidence=signal.evidence,
                cross_refs=signal.cross_references
            ))
        
        # Кульминация
        sections.append(Section(
            type="climax",
            heading="Ключевое обнаружение",
            text=self._render_climax(arc.climax, config),
            evidence=arc.climax.evidence,
            visualizations=self._select_visualizations(arc.climax)
        ))
        
        # Развязка
        sections.append(Section(
            type="resolution",
            heading="Выводы и ограничения",
            text=self._render_resolution(arc.resolution, config)
        ))
        
        return Story(
            sections=sections,
            word_count=sum(len(s.text.split()) for s in sections),
            reading_time_minutes=sum(len(s.text.split()) for s in sections) // 200,
            metadata=self._generate_metadata(arc, config)
        )
    
    def _render_signal(self, signal, config) -> str:
        """Отрендерить описание сигнала"""
        
        # Выбрать шаблон в зависимости от типа сигнала
        template = self._select_template(signal.type, config.tone)
        
        # Заполнить данные
        text = template.format(
            date=signal.date.strftime("%d.%m.%Y"),
            zone=signal.zones_affected_ru,
            magnitude=fmt(signal.magnitude, "magnitude"),
            z_score=fmt(signal.p95_z, "z_score"),
            confidence=fmt(signal.confidence, "confidence"),
            cross_ref=signal.cross_references_text
        )
        
        return text
```

---

## ШАГ 2: CROSS-REFERENCE SYSTEM (1 день, +8 баллов)

```python
class CrossReferenceEngine:
    """Создаёт связки между парами"""
    
    def find_references(self, pair, all_pairs: list) -> list:
        """Найти связанные пары"""
        
        references = []
        
        # 1. Временная связь: пары снятые близко по времени
        temporal = self._find_temporal(pair, all_pairs, max_days=30)
        for ref_pair in temporal:
            references.append(CrossReference(
                type="temporal",
                pair=ref_pair,
                text=f"Через {ref_pair.days_after} дней, на фото от {ref_pair.date:%d.%m.%Y}, "
                     f"аналогичные изменения наблюдались в области {ref_pair.overlapping_zones}."
            ))
        
        # 2. Ракурсная связь: те же изменения с другого ракурса
        angular = self._find_angular_confirmation(pair, all_pairs)
        for ref_pair in angular:
            references.append(CrossReference(
                type="angular",
                pair=ref_pair,
                text=f"Это подтверждается парой #{ref_pair.id} (ракурс {ref_pair.yaw:.0f}°), "
                     f"где {ref_pair.overlapping_zones} показали аналогичное смещение "
                     f"({ref_pair.displacement_mm:.1f} мм)."
            ))
        
        # 3. Зональная связь: те же зоны затронуты в других парах
        zonal = self._find_zonal_pattern(pair, all_pairs)
        for ref_pair in zonal:
            references.append(CrossReference(
                type="zonal",
                pair=ref_pair,
                text=f"Та же зона ({pair.primary_zone}) была затронута в паре #{ref_pair.id} "
                     f"от {ref_pair.date:%d.%m.%Y}."
            ))
        
        return references
    
    def generate_inline_reference(self, ref: CrossReference) -> str:
        """Сгенерировать inline-ссылку для текста"""
        templates = {
            "temporal": [
                "Аналогичные изменения были замечены {time_delta} спустя (пара #{pair_id}).",
                "Спустя {time_delta}, на фото от {date}, та же зона показала {magnitude}.",
                "Пара #{pair_id} от {date} подтверждает этот паттерн."
            ],
            "angular": [
                "С другого ракурса ({angle}°) изменения также видны (пара #{pair_id}).",
                "Подтверждение в паре #{pair_id} (ракурс {angle}°): {zone} сместилась на {displacement}.",
            ],
            "zonal": [
                "Эта зона была затронута и ранее — в паре #{pair_id} от {date}.",
                "Аналогичный паттерн в зоне {zone} наблюдался в {count} других парах."
            ]
        }
        
        template = random.choice(templates[ref.type])
        return template.format(**ref.data)
```

---

## ШАГ 3: TEMPLATE VARIATIONS (1 день, +5 баллов)

```python
class TemplateVariationEngine:
    """3-5 вариантов каждого шаблона для разнообразия"""
    
    VARIATIONS = {
        "significant_change_cheekbone": [
            # Вариант 1: Прямой
            "Значительное смещение {side} скулы ({value} мм, z={z}). "
            "Это превышает калибровочный шум в {z_ratio} раз.",
            
            # Вариант 2: Сравнительный
            "{side_ru} скула сместилась на {value} мм между фотографиями — "
            "это в {z_ratio} раз больше ожидаемого шума.",
            
            # Вариант 3: Нарративный
            "Наиболее заметное изменение затронуло {side} скулу: "
            "точка сместилась на {value} мм (z-score: {z}).",
            
            # Вариант 4: Контекстуальный
            "Костная структура показала изменение: {side} скула "
            "сместилась на {value} мм. Как костный ориентир, "
            "эта точка менее подвержена влиянию мимики."
        ],
        
        "stable_zone": [
            "Зона {zone} осталась стабильной (все z-scores < 2.0).",
            "В области {zone_ru} изменений не обнаружено.",
            "{zone_ru} не показала значимых отклонений от нормы.",
            "Все точки в зоне {zone_ru} в пределах калибровочного шума."
        ],
        
        "cluster_description": [
            "За период {start} — {end} обнаружено {count} связанных изменений.",
            "Кластер из {count} событий за {duration}: {summary}.",
            "Между {start} и {end} зафиксированы {count} эпизодов изменений."
        ]
    }
    
    def select_variation(self, template_id: str, context: dict) -> str:
        """Выбрать вариант шаблона"""
        variations = self.VARIATIONS.get(template_id, [])
        
        if not variations:
            return ""
        
        # Ротация вариантов (не повторять один и тот же)
        used = context.get("used_variations", {}).get(template_id, set())
        available = [v for i, v in enumerate(variations) if i not in used]
        
        if not available:
            available = variations  # Сбросить если все использованы
        
        selected = random.choice(available)
        
        # Запомнить использованный вариант
        if template_id not in context.get("used_variations", {}):
            context["used_variations"][template_id] = set()
        context["used_variations"][template_id].add(
            variations.index(selected)
        )
        
        return selected
```

---

## ШАГ 4: TONE/AUDIENCE ADAPTATION (1 день, +5 баллов)

```python
class ToneAdapter:
    """Адаптация текста под тон и аудиторию"""
    
    TONES = {
        "scientific": {
            "description": "Научный стиль",
            "characteristics": {
                "precision": "high",       # Точные формулировки
                "hedging": "heavy",        # Много оговорок
                "jargon": "allowed",       # Можно термины
                "passive_voice": True,      # Пассивный залог
                "numbers": "exact",        # Точные числа
                "disclaimers": "detailed"  # Подробные ограничения
            },
            "examples": {
                "change": "Обнаружено статистически значимое смещение (z=4.2, p<0.001)",
                "stable": "Различия не достигли уровня статистической значимости",
                "uncertain": "Данные недостаточны для отклонения нулевой гипотезы"
            }
        },
        
        "journalistic": {
            "description": "Журналистский стиль (нейтральный)",
            "characteristics": {
                "precision": "medium",
                "hedging": "moderate",
                "jargon": "minimized",
                "passive_voice": False,
                "numbers": "rounded",
                "disclaimers": "brief"
            },
            "examples": {
                "change": "Обнаружено значительное смещение скулы (2,8 мм)",
                "stable": "Изменений не обнаружено",
                "uncertain": "Результат неопределён"
            }
        },
        
        "popular": {
            "description": "Популярный стиль (для широкой аудитории)",
            "characteristics": {
                "precision": "low",
                "hedging": "light",
                "jargon": "none",
                "passive_voice": False,
                "numbers": "simplified",
                "disclaimers": "minimal"
            },
            "examples": {
                "change": "Лицо заметно изменилось — скула сдвинулась почти на 3 миллиметра",
                "stable": "Лицо не изменилось",
                "uncertain": "Точно сказать нельзя"
            }
        }
    }
    
    AUDIENCE_PROFILES = {
        "investigation_media": {
            "name": "Расследовательские СМИ",
            "tone": "journalistic",
            "detail_level": "high",
            "include_methodology": True,
            "include_raw_numbers": True,
            "disclaimer_emphasis": "high"
        },
        "scientific_journal": {
            "name": "Научные журналы",
            "tone": "scientific",
            "detail_level": "maximum",
            "include_methodology": True,
            "include_raw_numbers": True,
            "include_statistical_tests": True
        },
        "general_news": {
            "name": "Общие новости",
            "tone": "popular",
            "detail_level": "medium",
            "include_methodology": False,
            "include_raw_numbers": False,
            "focus": "key_findings"
        },
        "social_media": {
            "name": "Социальные сети",
            "tone": "popular",
            "detail_level": "low",
            "max_length": 280,
            "include_hashtags": True,
            "format": "thread"
        }
    }
    
    def adapt(self, text: str, tone: str, audience: str) -> str:
        """Адаптировать текст"""
        tone_config = self.TONES[tone]
        audience_config = self.AUDIENCE_PROFILES[audience]
        
        # Применить трансформации
        adapted = text
        
        if tone_config["characteristics"]["numbers"] == "rounded":
            adapted = self._round_numbers(adapted)
        elif tone_config["characteristics"]["numbers"] == "simplified":
            adapted = self._simplify_numbers(adapted)
        
        if tone_config["characteristics"]["jargon"] == "none":
            adapted = self._remove_jargon(adapted)
        elif tone_config["characteristics"]["jargon"] == "minimized":
            adapted = self._minimize_jargon(adapted)
        
        if tone_config["characteristics"]["hedging"] == "heavy":
            adapted = self._add_hedging(adapted)
        elif tone_config["characteristics"]["hedging"] == "light":
            adapted = self._reduce_hedging(adapted)
        
        if audience_config.get("max_length"):
            adapted = self._truncate(adapted, audience_config["max_length"])
        
        return adapted
```

---

## ШАГ 5: EXECUTIVE SUMMARY (0.5 дня, +3 балла)

```python
class ExecutiveSummaryGenerator:
    """Генерирует краткий отчёт для редактора"""
    
    def generate(self, story: Story, timeline: Timeline) -> ExecutiveSummary:
        """
        Структура:
        1. Key Finding (1 предложение)
        2. Evidence Strength (1-2 предложения)
        3. Timeline Overview (2-3 предложения)
        4. Limitations (1-2 предложения)
        5. Recommended Action (1 предложение)
        """
        
        return ExecutiveSummary(
            key_finding=self._key_finding(timeline),
            evidence_strength=self._evidence_strength(timeline),
            timeline_overview=self._timeline_overview(timeline),
            limitations=self._limitations(),
            recommended_action=self._recommended_action(timeline),
            
            # Метрики для быстрого обзора
            metrics={
                "total_pairs": timeline.total_pairs,
                "significant_changes": len(timeline.events),
                "max_confidence": max(e.confidence for e in timeline.events) if timeline.events else 0,
                "cross_confirmed": timeline.cross_confirmation_count,
                "time_span": f"{timeline.duration_years:.1f} лет"
            }
        )
    
    def _key_finding(self, timeline) -> str:
        """Главное обнаружение в 1 предложении"""
        if not timeline.events:
            return "Анализ не выявил значимых изменений лица."
        
        most_significant = max(timeline.events, key=lambda e: e.confidence)
        return (
            f"Наиболее значимое изменение обнаружено {most_significant.date:%d.%m.%Y}: "
            f"{most_significant.description} (уверенность: {most_significant.confidence}/8)."
        )
```

---

## ШАГ 6: QUALITY CONTROL (0.5 дня, +2 балла)

```python
class TextQualityController:
    """Проверяет качество сгенерированного текста"""
    
    def check(self, text: str, source_data: dict) -> QualityReport:
        """Проверить текст на ошибки"""
        
        issues = []
        
        # 1. Проверка на галлюцинации (данные в тексте совпадают с исходными)
        hallucinations = self._check_hallucinations(text, source_data)
        issues.extend(hallucinations)
        
        # 2. Проверка на внутренние противоречия
        contradictions = self._check_contradictions(text)
        issues.extend(contradictions)
        
        # 3. Проверка на обязательные disclaimers
        missing_disclaimers = self._check_disclaimers(text)
        issues.extend(missing_disclaimers)
        
        # 4. Проверка форматирования чисел
        formatting_issues = self._check_number_formatting(text)
        issues.extend(formatting_issues)
        
        # 5. Проверка читаемости
        readability = self._check_readability(text)
        
        return QualityReport(
            issues=issues,
            readability_score=readability,
            overall_score=self._calculate_score(issues, readability),
            passed=len([i for i in issues if i.severity == "critical"]) == 0
        )
    
    def _check_hallucinations(self, text, source_data):
        """Проверить что все числа в тексте есть в данных"""
        numbers_in_text = self._extract_numbers(text)
        issues = []
        
        for num in numbers_in_text:
            if not self._number_exists_in_data(num, source_data):
                issues.append(QualityIssue(
                    type="hallucination",
                    severity="critical",
                    message=f"Число {num} в тексте не найдено в исходных данных",
                    location=self._find_location(text, num)
                ))
        
        return issues
    
    def _check_contradictions(self, text):
        """Проверить на внутренние противоречия"""
        # Пример: текст говорит "изменений нет" но упоминает "смещение 2.8мм"
        claims = self._extract_claims(text)
        contradictions = []
        
        for i, claim_a in enumerate(claims):
            for claim_b in claims[i+1:]:
                if self._are_contradictory(claim_a, claim_b):
                    contradictions.append(QualityIssue(
                        type="contradiction",
                        severity="warning",
                        message=f"Противоречие: '{claim_a.text}' vs '{claim_b.text}'"
                    ))
        
        return contradictions
```

---

## ШАГ 7: EXPORT PIPELINE (0.5 дня, +2 балла)

```python
class ExportPipeline:
    """Экспорт в разные форматы"""
    
    def export(self, story: Story, format: str, config: dict) -> bytes:
        """Экспорт в указанный формат"""
        
        exporters = {
            "markdown": self._export_markdown,
            "html": self._export_html,
            "pdf": self._export_pdf,
            "docx": self._export_docx,
            "json": self._export_json,
            "plaintext": self._export_plaintext
        }
        
        exporter = exporters.get(format)
        if not exporter:
            raise ValueError(f"Unknown format: {format}")
        
        return exporter(story, config)
    
    def _export_markdown(self, story, config):
        """Экспорт в Markdown"""
        lines = []
        for section in story.sections:
            if section.type == "headline":
                lines.append(f"# {section.text}\n")
            elif section.heading:
                lines.append(f"## {section.heading}\n")
            lines.append(f"{section.text}\n")
        return "\n".join(lines)
    
    def _export_html(self, story, config):
        """Экспорт в HTML с визуализациями"""
        # Include interactive charts, hover tooltips, etc.
        pass
    
    def _export_pdf(self, story, config):
        """Экспорт в PDF через weasyprint"""
        html = self._export_html(story, config)
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
```

---

## 📊 ПРОГНОЗ БАЛЛОВ ПОСЛЕ РЕАЛИЗАЦИИ

```
ФАКТОР                    ДО    ПОСЛЕ    ПРИРОСТ
─────────────────────────────────────────────────
Narrative Arc             40    92       +52
Timeline Storytelling     35    90       +55
Cross-Reference           45    90       +45
Variability               50    88       +38
Tone Adaptation           40    85       +45
Audience Adaptation       35    85       +50
Template Engine           75    95       +20
Generation Engine         65    92       +27
Multi-pair Context        55    90       +35
Quality Control           65    88       +23
Export Pipeline           60    85       +25
Executive Summary         —     90       NEW
─────────────────────────────────────────────────
СРЕДНИЙ (слабые → все):   72    95+      +23
```

---

## ⏱ TIMELINE РЕАЛИЗАЦИИ

```
ДЕНЬ 1-2: Timeline Builder + Event Clustering
  → Сортировка, события, кластеры, фазы
  → Результат: timeline из 1900 пар

ДЕНЬ 3: Narrative Arc Builder
  → Exposition → Rising → Climax → Falling → Resolution
  → Результат: структура истории

ДЕНЬ 4: Story Generator + Cross-References
  → Рендер текста из arc
  → Inline-ссылки между парами
  → Результат: связный текст

ДЕНЬ 5: Template Variations
  → 3-5 вариантов каждого шаблона
  → Ротация для разнообразия
  → Результат: уникальные тексты

ДЕНЬ 6: Tone/Audience Adaptation
  → Scientific, journalistic, popular
  → 4 audience profiles
  → Результат: адаптивные тексты

ДЕНЬ 7: Executive Summary + Quality Control
  → Краткий отчёт для редактора
  → Anti-hallucination checks
  → Результат: надёжные тексты

ДЕНЬ 8: Export Pipeline + Integration
  → Markdown, HTML, PDF, DOCX
  → UI integration
  → Результат: production-ready

ДЕНЬ 9-10: Testing + Bug fixes
  → Unit tests для каждого компонента
  → Integration tests
  → Результат: 95+ баллов
```

---

## 🎯 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

**ДО (72/100):**
```
"Значительное смещение левой скулы (2,8 мм, z=4,2).
 Костные структуры — наиболее надёжный индикатор."
```

**ПОСЛЕ (95+/100):**
```
📰 ЗАГОЛОВОК:
"Обнаружены значительные изменения лица на 23 фотографиях за 5 лет"

📋 EXECUTIVE SUMMARY:
Наиболее значимое изменение: февраль-март 2018 (уверенность 7/8).
23 пары подтвердили изменения в 5 различных ракурсах.
Ограничения: это измерения, не выводы о личности.

📖 ПОЛНЫЙ ТЕКСТ:
Введение:
  За период с марта 2015 по ноябрь 2020 было проанализировано
  1,947 пар фотографий. Анализ выявил 3 кластера значимых изменений...

Нарастание (2016):
  Первые сигналы появились в июле 2016 года. В паре #0342
  обнаружено слабое смещение левой скулы (1,5 мм, z=2,3).
  Через 5 дней, в паре #0358 (ракурс 12°), аналогичное
  смещение подтвердилось (1,3 мм, z=2,1)...

Кульминация (2018):
  Наиболее значимые изменения зафиксированы в феврале-марте 2018.
  За 33 дня обнаружено 7 пар с p95_z > 5.0.
  
  В паре #1247 (15.02.2018) левая скула сместилась на 2,8 мм
  (z=4,2) — это в 4 раза превышает калибровочный шум.
  Через 3 дня, пара #1253 (ракурс -18°) подтвердила: 2,5 мм
  (z=3,8). Ещё через неделю, пара #1271 (ракурс 35°): 3,1 мм
  (z=4,7).
  
  Изменения затронули преимущественно костные структуры:
  скулы, углы челюсти, подбородок. Как стабильные костные
  ориентиры, эти точки менее подвержены влиянию мимики...

Выводы:
  Обнаруженные изменения подтверждены в 5 ракурсах и 3 временных
  точках. Однако: статус «изменение» НЕ доказывает подмену личности,
  маску, операцию или медицинский факт. Это только измерение
  величины движения точек относительно калибровочного шума...

📊 ВИЗУАЛИЗАЦИИ:
  [Timeline chart] [Heatmap] [3D mesh comparison]

⚠ DISCLAIMERS:
  • Статус — это измерение, не вывод о личности
  • Вероятности — вес доказательств, не «процент доказанности»
  • 3D-форма — оценка модели, не КТ-сканирование
```

---

**Документ создан:** 2026-08-27  
**Статус:** ✅ План готов к реализации  
**Прогноз:** 72 → 95+ за 8-10 дней
