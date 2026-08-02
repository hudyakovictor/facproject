# Статические и интеграционные проверки вне симулятора

Идеи A3, B8, C7, C8, D10, F7, F8, G6, H1–H4, I1, I2, I4 нельзя честно оценить одним pair simulator.

- A3: удалить/депрекейтить aligned — import graph + schema migration.
- B8: симметризация — property tests A↔B.
- C7/C8: synthetic pose calibration/sign — renderer ground truth.
- D10: ENFSI scale — внешняя методологическая рецензия.
- F7/F8: quality/resolution — image degradation benchmark.
- G6: 21 mesh zones — topology/coverage validation.
- H1: perceptual duplicates — crop/resave fixture.
- H2/H3: EXIF/date weight — provenance fixtures и reviewer policy.
- H4: integrity — tamper tests всех четырёх hashes.
- I1/I2: stable fields/UI keys — schema snapshot + TypeScript exhaustiveness.
- I4: pose policy v3 — CSV/schema diff и contract tests.

Каждый пункт закрывается отдельным artifact, тестом и decision record; отсутствие симуляционного score не означает низкий приоритет.
