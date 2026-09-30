// Keep timeline interpolation in sync with morphing/backend/timeline.py.
export function catmullRomWeights(progress, count, positions = null) {
  if (count < 2 || count > 4) throw new Error('Timeline must contain 2–4 keyframes');
  const t = Math.max(0, Math.min(1, Number(progress)));
  if (count === 2) return [1 - t, t, 0, 0];
  const timelinePositions = positions || Array.from({ length: count }, (_, index) => index / (count - 1));
  if (timelinePositions.length !== count || timelinePositions[0] !== 0 || timelinePositions[timelinePositions.length - 1] !== 1 || timelinePositions.some((value, index) => index > 0 && value <= timelinePositions[index - 1])) {
    throw new Error('Timeline positions must be strictly increasing from 0 to 1');
  }
  const upper = timelinePositions.findIndex((value, index) => index > 0 && t <= value);
  const segment = upper < 0 ? count - 2 : upper - 1;
  const span = timelinePositions[segment + 1] - timelinePositions[segment];
  const u = t >= 1 ? 1 : (t - timelinePositions[segment]) / span;
  const u2 = u * u;
  const u3 = u2 * u;
  const basis = [
    -0.5 * u3 + u2 - 0.5 * u,
    1.5 * u3 - 2.5 * u2 + 1,
    -1.5 * u3 + 2 * u2 + 0.5 * u,
    0.5 * u3 - 0.5 * u2,
  ];
  const weights = [0, 0, 0, 0];
  [segment - 1, segment, segment + 1, segment + 2].forEach((index, offset) => {
    weights[Math.min(Math.max(index, 0), count - 1)] += basis[offset];
  });
  return weights;
}

export function interpolateFlat(values, progress, count, positions = null) {
  if (!values?.length || count < 2) return null;
  const weights = catmullRomWeights(progress, count, positions);
  const result = new Float32Array(values[0].length);
  values.forEach((value, index) => {
    const weight = weights[index];
    if (!weight) return;
    for (let i = 0; i < value.length; i += 1) result[i] += value[i] * weight;
  });
  return result;
}
