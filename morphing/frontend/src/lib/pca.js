/**
 * Классический PCA через двойное центрирование Gram-матрицы (эквивалент
 * metric MDS для честных евклидовых векторов — что у нас и есть: alpha_id
 * 80-мерные векторы формы 3DMM). Работает в "двойственном" пространстве
 * N×N вместо D×D (80×80), что тривиально для N=2..6 загруженных в сессии
 * лиц и даёт ТОЧНЫЕ (не приближённые power-iteration) главные компоненты.
 *
 * M12/M29 в docs/30_MORPHING_ANALYSES.md просили 3D PCA Scatter по ВСЕМУ
 * датасету лиц — у нас нет доступа к Stage 1 датасету в этой песочнице,
 * поэтому это осознанно урезанная version: PCA только по фото, загруженным
 * в текущей сессии (2-6 точек). Задокументировано в 31_MORPHING_PROGRESS.md.
 */

/** Якоби-метод для симметричных матриц малого размера (N<=8). Возвращает {values, vectors} где vectors[i] — i-й собственный вектор (столбец). */
function jacobiEigen(A, maxIter = 100, tol = 1e-10) {
  const n = A.length;
  const a = A.map((row) => [...row]);
  const v = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => (i === j ? 1 : 0)));

  for (let iter = 0; iter < maxIter; iter++) {
    // найти наибольший внедиагональный элемент
    let off = 0, p = 0, q = 1;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        if (Math.abs(a[i][j]) > off) { off = Math.abs(a[i][j]); p = i; q = j; }
      }
    }
    if (off < tol) break;

    const app = a[p][p], aqq = a[q][q], apq = a[p][q];
    const phi = 0.5 * Math.atan2(2 * apq, aqq - app);
    const c = Math.cos(phi), s = Math.sin(phi);

    for (let k = 0; k < n; k++) {
      const akp = a[k][p], akq = a[k][q];
      a[k][p] = c * akp - s * akq;
      a[k][q] = s * akp + c * akq;
    }
    for (let k = 0; k < n; k++) {
      const apk = a[p][k], aqk = a[q][k];
      a[p][k] = c * apk - s * aqk;
      a[q][k] = s * apk + c * aqk;
    }
    for (let k = 0; k < n; k++) {
      const vkp = v[k][p], vkq = v[k][q];
      v[k][p] = c * vkp - s * vkq;
      v[k][q] = s * vkp + c * vkq;
    }
  }

  const values = a.map((row, i) => row[i]);
  const vectors = Array.from({ length: n }, (_, i) => v.map((row) => row[i]));
  return { values, vectors };
}

/**
 * @param vectors N x D массив (N точек, D измерений)
 * @param k число компонент (обычно 3)
 * @returns { coords: N x k координаты, explainedVariance: [k] доля дисперсии }
 */
export function pcaProject(vectors, k = 3) {
  const n = vectors.length;
  const d = vectors[0].length;
  const mean = new Float64Array(d);
  for (const v of vectors) for (let j = 0; j < d; j++) mean[j] += v[j] / n;
  const centered = vectors.map((v) => v.map((x, j) => x - mean[j]));

  // Gram-матрица N×N
  const G = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => {
    let s = 0;
    for (let t = 0; t < d; t++) s += centered[i][t] * centered[j][t];
    return s;
  }));

  const { values, vectors: eigvecs } = jacobiEigen(G);
  const order = values.map((v, i) => i).sort((a, b) => values[b] - values[a]);
  const totalVar = values.reduce((a, b) => a + Math.max(b, 0), 0) || 1e-9;

  const kk = Math.min(k, n - 1 > 0 ? n - 1 : 1);
  const coords = Array.from({ length: n }, () => new Array(k).fill(0));
  const explainedVariance = new Array(k).fill(0);
  for (let c = 0; c < kk; c++) {
    const idx = order[c];
    const lambda = Math.max(values[idx], 0);
    const scale = Math.sqrt(lambda);
    explainedVariance[c] = lambda / totalVar;
    for (let i = 0; i < n; i++) coords[i][c] = eigvecs[idx][i] * scale;
  }
  return { coords, explainedVariance };
}
