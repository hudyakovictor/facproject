/**
 * Русификация интерфейса Forensic Timeline Suite.
 * Целевая аудитория: широкая публика, не технические специалисты.
 * Принцип: понятные русские названия + технические ID серым мелким шрифтом.
 */

export const T = {
  // Header
  APP_TITLE: "DEEPUTIN",
  APP_SUBTITLE: "ХРОНОФОRENЗИКА ЛИЦА",
  ARTIFACT: "АРТЕФАКТ",
  PHOTOS: "фото",
  LAST_RUN: "последний прогон",
  DATASET: "ДАТАСЕТ",
  BUCKET: "РАКУРС",
  VIEW: "РЕЖИМ",
  SEARCH_PLACEHOLDER: "id фото / дата",
  EXPORT_REPORT: "ЭКСПОРТ ОТЧЁТА",
  HIDE: "СКРЫТЬ",
  FILTER: "ФИЛЬТР",
  SOURCES: "ИСТОЧНИКИ",
  FIT: "ВСЁ",

  // Datasets
  DATASET_MAIN: "основной",
  DATASET_CALIBRATION: "калибровка",

  // Buckets
  BUCKET_ALL: "все",
  BUCKET_FRONTAL: "фронт",
  BUCKET_FRONTAL_15: "фронт 15°",
  BUCKET_FRONTAL_30: "фронт 30°",
  BUCKET_PROFILE_L: "профиль Л",
  BUCKET_PROFILE_R: "профиль П",

  // View modes
  VIEW_FULL: "ХРОНОЛОГИЯ",
  VIEW_ERA_COMPARE: "ЭПОХИ",
  VIEW_CLUSTER: "ГРУППЫ",

  // Eras
  ERA_1: "ЭТАЛОН",
  ERA_2: "РАННИЙ",
  ERA_3: "УДМУРТ",
  ERA_4: "ПЕРЕХОД",
  ERA_5: "ВАСИЛИЧ",

  // Hypotheses
  H0_LABEL: "тот же человек",
  H1_LABEL: "маска / пластика",
  H2_LABEL: "замена личности",

  // Track panel
  GEOMETRY_TITLE: "ГЕОМЕТРИЯ ЛИЦА",
  TEXTURE_TITLE: "ТЕКСТУРА КОЖИ",
  LANE_BONE: "КОСТНАЯ СТРУКТУРА",
  LANE_ORBITS: "ГЛАЗНИЦЫ",
  LANE_CHIN: "ПОДБОРОДОК",
  LANE_JAW: "НИЖНЯЯ ЧЕЛЮСТЬ",
  LANE_CHEEKBONES: "СКУЛЫ",
  LANE_SYMMETRY: "СИММЕТРИЯ",
  LANE_POSE: "ПОВОРОТ ГОЛОВЫ",
  LANE_SILICONE: "ВЕРОЯТН. СИЛИКОНА",
  LANE_GLOSS: "БЛЕСК КОЖИ",
  LANE_LBP: "МИКРОТЕКСТУРА",
  LANE_FRANGI: "СОСУДИСТЫЙ РИСУНОК",
  LANE_WRINKLE: "МОРЩИНЫ",
  LANE_SUBSURFACE: "ПОДКОЖНЫЙ СЛОЙ",
  LANE_VISUAL_AGE: "ВИЗУАЛЬНЫЙ ВОЗРАСТ",

  // Left panel tabs
  TAB_PHOTO: "ФОТО",
  TAB_GEOMETRY: "ГЕОМЕТРИЯ",
  TAB_SKIN: "КОЖА",
  TAB_VERDICT: "ВЕРДИКТ",
  TAB_CONTEXT: "КОНТЕКСТ",

  // Left panel metadata
  META_PHOTO_ID: "идентификатор",
  META_SOURCE: "источник",
  META_DATE: "дата съёмки",
  META_BUCKET: "ракурс",
  META_QUALITY: "качество",
  META_BLUR: "размытие",
  META_NOISE: "шум",
  META_EVIDENCE_MODE: "режим анализа",
  META_RELIABILITY: "надёжность",
  META_GEOMETRY_SCORE: "оценка геометрии",
  EVIDENCE_CALIBRATED: "КАЛИБРОВАННЫЙ",
  EVIDENCE_FALLBACK: "РЕЗЕРВНЫЙ",

  // Left panel actions
  BTN_HIDE_RESTORE: "СКРЫТЬ / ВОССТАНОВИТЬ",
  BTN_MESH_OVERLAY: "СЕТКА ЛАНДМАРКОВ",

  // Verdict
  VERDICT_TITLE: "БАЙЕСОВСКИЙ ВЕРДИКТ",
  VERDICT_DOMINANT: "ДОМИНАНТА",
  VERDICT_CONFIDENCE: "УВЕРЕННОСТЬ",
  VERDICT_SNR_GEOMETRY: "сигнал геометрии",
  VERDICT_SNR_TEXTURE: "сигнал текстуры",
  VERDICT_SIGNAL: "СИГНАЛ",
  VERDICT_UNCERTAIN: "НЕОПРЕДЕЛЁННО",
  VERDICT_ACTIVE_FLAGS: "АКТИВНЫЕ ФЛАГИ",
  VERDICT_REASONING: "ОБОСНОВАНИЕ",
  VERDICT_VERSION: "версия модели",

  // Fuzzy labels
  FUZZY_STRONGLY_MATCHING: "ПОЛНОЕ СОВПАДЕНИЕ",
  FUZZY_CONSISTENT: "СООТВЕТСТВУЕТ",
  FUZZY_INSUFFICIENT_DATA: "МАЛО ДАННЫХ",
  FUZZY_WEAK_EVIDENCE: "СЛАБЫЕ ДАННЫЕ",
  FUZZY_SUSPICIOUS_TEXTURE: "ПОДОЗРИТЕЛЬНАЯ ТЕКСТУРА",
  FUZZY_GEOMETRIC_MISMATCH: "НЕСООТВЕТСТВИЕ ГЕОМЕТРИИ",
  FUZZY_IDENTITY_ANOMALY: "АНОМАЛИЯ ЛИЧНОСТИ",
  FUZZY_TEMPORAL_IMPOSSIBILITY: "НЕВОЗМОЖНО ПО ВРЕМЕНИ",

  // Fuzzy labels — short (для inline legend)
  FUZZY_SHORT_SM: "СОВП",
  FUZZY_SHORT_CON: "СООТВ",
  FUZZY_SHORT_INS: "МАЛО",
  FUZZY_SHORT_WE: "СЛАБ",
  FUZZY_SHORT_ST: "ПОДОЗР",
  FUZZY_SHORT_GM: "НЕСООТВ",
  FUZZY_SHORT_IA: "АНОМАЛ",
  FUZZY_SHORT_TI: "НЕВОЗМ",

  // Flags
  FLAG_IMPOSSIBLE_SHORT: "НЕВОЗМОЖНО КОРОТКИЙ СРОК",
  FLAG_TEXTURE_SPIKE: "СКАЧОК ТЕКСТУРЫ",
  FLAG_RETURN_TO_BASELINE: "ВОЗВРАТ К ЭТАЛОНУ",
  FLAG_TRANSITION: "ПЕРЕХОДНЫЙ ПЕРИОД",
  FLAG_TEMPORAL_IMPOSSIBILITY: "НЕВОЗМОЖНО ПО ВРЕМЕНИ",
  FLAG_EXIF_ANOMALY: "АНОМАЛИЯ ДАТЫ В EXIF",

  // Filter bar
  FILTERS: "ФИЛЬТРЫ",
  FILTER_ANOMALIES_ONLY: "ТОЛЬКО АНОМАЛИИ",
  FILTER_HIDE_LOW_QUALITY: "СКРЫТЬ НИЗКОЕ КАЧЕСТВО",
  FILTER_CONFIDENCE: "УВЕРЕННОСТЬ ≥",
  FILTER_ERA: "ЭПОХА:",
  FILTER_HYP: "ГИПОТЕЗА:",
  FILTER_FLAGS: "ФЛАГИ:",
  FILTER_VISIBLE: "видимых",

  // Hypothesis legend
  LEGEND_TITLE: "ГИПОТЕЗЫ",
  LEGEND_PRIORS: "БАЗОВЫЕ ВЕРОЯТНОСТИ",
  LEGEND_METHOD_TITLE: "МЕТОДИКА",
  LEGEND_METHOD:
    "Байесовская модель обновляет базовые вероятности трёх гипотез на основе 21 зоны геометрии лица (106 ключевых точек) и 34 метрик текстуры кожи.",
  LEGEND_Z2: "отклонение > 2σ — аномалия",
  LEGEND_Z3: "отклонение > 3σ — критично",
  LEGEND_IMPOSSIBLE: "невозможно: Δ < 90 дней, отклонение > 1.75σ",
  LEGEND_REFERENCE: "эталонный период: до 31.12.2002",

  // Alternative views
  ERA_COMPARE_TITLE: "СРАВНЕНИЕ ПО ЭПОХАМ",
  CLUSTER_TITLE: "ГРУППЫ ПО СХОДСТВУ",
  CLUSTER_PC1: "ось 1: геометрия →",
  CLUSTER_PC2: "ось 2: текстура →",
  CLUSTER_SUBTITLE: "каждая точка — одно фото, цвет — эпоха",
  CLUSTER_HINT: "кликните на точку, чтобы увидеть детали фото",

  // Comparison
  COMPARE_TITLE: "РЕЖИМ СРАВНЕНИЯ",
  COMPARE_SPLIT: "СРАВНЕНИЕ А / Б",
  COMPARE_REFERENCE: "ЭТАЛОН",
  COMPARE_COMPARE: "СРАВНИТЬ",
  COMPARE_CLOSE: "ЗАКРЫТЬ",
  COMPARE_OPEN_DETAILS: "ДЕТАЛИ",
  COMPARE_DIFF_TITLE: "РАЗЛИЧИЯ МЕТРИК",
  COMPARE_ALLOWED_DELTA: "допустимое отклонение",
  COMPARE_GEOMETRY: "геометрия",
  COMPARE_TEXTURE: "текстура",
  COMPARE_METRIC: "МЕТРИКА",
  COMPARE_DELTA: "Δ",
  COMPARE_ABS_DELTA: "|Δ|",

  // Filmstrip hint
  FILMSTRIP_HINT: "SHIFT + клик на другое фото — включить СРАВНЕНИЕ",

  // Publications
  SOURCES_TITLE: "ИСТОЧНИКИ",
  SOURCES_SUBTITLE: "событий в архиве публикаций",
  SOURCES_TIMELINE: "ХРОНОЛОГИЯ",
  SOURCES_FILTER_ALL: "все",
  SOURCES_FILTER_MEDIA: "СМИ",
  SOURCES_FILTER_POLITICAL: "политика",
  SOURCES_FILTER_AI: "ИИ-исследования",
  SOURCES_FILTER_FORENSIC: "форензика",

  // Event pins
  PIN_DISAPPEARANCE_2015: "ИСЧЕЗНОВЕНИЕ 2015",
  PIN_BUDAN_STATEMENT: "ЗАЯВЛЕНИЕ БУДАНОВА",
  PIN_JP_AI_STUDY: "ЯПОНСКОЕ ИИ-ИССЛЕДОВАНИЕ",
  PIN_MINCHENKO_REPORT: "ДОКЛАД МИНЧЕНКО",
  PIN_ERA_3_START: "НАЧАЛО ЭПОХИ УДМУРТ",
  PIN_ERA_4_START: "НАЧАЛО ПЕРЕХОДНОЙ ЭПОХИ",
  PIN_ERA_5_START: "НАЧАЛО ЭПОХИ ВАСИЛИЧ",

  // Ruler
  RULER_YEAR: "год",
  RULER_PHOTOS: "фото",
};

// Функции перевода fuzzy label и flags
export function tFuzzy(label: string, short = false): string {
  const key = `FUZZY${short ? "_SHORT_" : "_"}${label}` as keyof typeof T;
  return (T[key] as string) || label;
}

export function tFlag(flag: string): string {
  const key = `FLAG_${flag}` as keyof typeof T;
  return (T[key] as string) || flag;
}

export function tEra(era: string): string {
  const key = era as keyof typeof T;
  return (T[key] as string) || era;
}
