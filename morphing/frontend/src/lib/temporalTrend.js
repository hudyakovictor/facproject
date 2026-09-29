/**
 * Temporal Identity Drift / 4D Age Progression (M15/M19, docs/30_MORPHING_ANALYSES.md).
 *
 * Линейная регрессия alpha_id (80-мерный вектор формы 3DMM) по годам съёмки.
 * Работает в НИЗКОРАЗМЕРНОМ пространстве формы, а не по 35 709×3 вершинам —
 * дешевле и устойчивее (совпадает с тем, как это делает основной pipeline
 * facproject для устойчивых трендов).
 *
 * Честная граница метода: 3DMM не различает ПРИЧИНУ изменения формы (старение
 * vs. хирургия vs. шум реконструкции) — регрессия даёт только "отклонение от
 * линейного тренда формы", не диагноз. Экстраполяция — всегда synthetic/exploratory.
 */

/** Простая линейная регрессия по каждой из 80 координат alpha_id независимо. */
export function fitAlphaTrend(years, alphaVectors) {
  const n = years.length;
  const dims = alphaVectors[0].length;
  const meanYear = years.reduce((a, b) => a + b, 0) / n;
  let varYear = 0;
  for (const y of years) varYear += (y - meanYear) ** 2;
  varYear = varYear || 1e-9;

  const meanAlpha = new Float64Array(dims);
  for (let d = 0; d < dims; d++) {
    let s = 0;
    for (let i = 0; i < n; i++) s += alphaVectors[i][d];
    meanAlpha[d] = s / n;
  }

  const slope = new Float64Array(dims); // db/dyear на координату
  for (let d = 0; d < dims; d++) {
    let cov = 0;
    for (let i = 0; i < n; i++) cov += (years[i] - meanYear) * (alphaVectors[i][d] - meanAlpha[d]);
    slope[d] = cov / varYear;
  }

  const predict = (year) => {
    const out = new Float64Array(dims);
    for (let d = 0; d < dims; d++) out[d] = meanAlpha[d] + slope[d] * (year - meanYear);
    return out;
  };

  // Остатки (residuals) и "скорость дрейфа" (норма вектора наклона)
  const residualNorms = alphaVectors.map((alpha, i) => {
    const pred = predict(years[i]);
    let sq = 0;
    for (let d = 0; d < dims; d++) sq += (alpha[d] - pred[d]) ** 2;
    return Math.sqrt(sq);
  });
  const meanRes = residualNorms.reduce((a, b) => a + b, 0) / n;
  const stdRes = Math.sqrt(residualNorms.reduce((a, b) => a + (b - meanRes) ** 2, 0) / n) || 1e-9;
  let driftSpeed = 0;
  for (let d = 0; d < dims; d++) driftSpeed += slope[d] * slope[d];
  driftSpeed = Math.sqrt(driftSpeed);

  return {
    meanYear,
    predict,
    residualNorms,
    meanResidual: meanRes,
    stdResidual: stdRes,
    driftSpeedPerYear: driftSpeed,
    anomalyFlags: residualNorms.map((r) => r > meanRes + 1.5 * stdRes),
  };
}
