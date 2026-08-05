# Журнал решений

- **D-001:** девять pose bins неизменны — требование владельца данных.
- **D-002:** дата из имени файла authoritative; EXIF только corroboration.
- **D-003:** primary coordinates переключены с chronology на raw object-normalized после DCRD, SGT и simulations.
- **D-004:** axis gap вместо scalar pose-distance; pitch ≤2° наиболее полезен.
- **D-005:** subset91 и utility только NaN-safe; старый артефакт признан дефектным.
- **D-006:** FDR унифицирован на 0.05; 0.10 остаётся только legacy alias при чтении старых результатов.
- **D-007:** A→B→A detector требует абсолютного эффекта, не только ratio.
- **D-008:** calibration threshold защищается от 20% contamination и проверяется LOPO.
- **D-009:** alpha_id, pose subtraction и dual channel не primary из-за слабой/нестабильной эффективности.
- **D-010:** публичный результат всегда observation-based и `not_a_verdict`.
- **D-011:** байесовская логико-вероятностная модель нечёткого вывода из работы Кожомбердиевой (2019) **не включается** в production analytical pipeline и не используется для процентов H0/H1/H2. Причины: membership degree не является эмпирически откалиброванной вероятностью, correlated evidence нельзя наивно перемножать, а функции принадлежности/веса создают лишний слой субъективной настройки поверх calibration+FDR. Понятные объяснения строятся прямым детерминированным отображением versioned evidence states, limitations и review rules. Настоящий Bayesian inference допускается только как отдельное будущее исследование с labeled H0/H1/H2 datasets, likelihood validation, dependence model, prior sensitivity и holdout.
