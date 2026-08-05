// Web Worker for asynchronous Mahalanobis distance & similarity overlay computation (1,900 photos)
// Runs in background thread without blocking main UI thread (< 30ms target)

export interface WorkerInput {
  photoAId: string;
  photoASnr: number;
  photoABoneRmse: number;
  photos: Array<{
    id: string;
    snr: number;
    boneRmse: number;
  }>;
}

export interface WorkerOutput {
  photoAId: string;
  results: Record<
    string,
    {
      deltaSnr: number;
      deltaRmse: number;
      overlayType: "SIMILAR_HIGH" | "DIVERGENT_HIGH" | "NEUTRAL";
      matchPercent: number;
    }
  >;
  computeTimeMs: number;
}

self.onmessage = (e: MessageEvent<WorkerInput>) => {
  const start = performance.now();
  const { photoAId, photoASnr, photoABoneRmse, photos } = e.data;

  const results: WorkerOutput["results"] = {};

  for (let i = 0; i < photos.length; i++) {
    const p = photos[i];
    const deltaSnr = Math.abs(p.snr - photoASnr);
    const deltaRmse = Math.abs(p.boneRmse - photoABoneRmse);

    // Mahalanobis / SNR similarity metric approximation
    let overlayType: "SIMILAR_HIGH" | "DIVERGENT_HIGH" | "NEUTRAL" = "NEUTRAL";
    if (deltaSnr < 0.6 && deltaRmse < 0.2) {
      overlayType = "SIMILAR_HIGH"; // Green 20% opacity overlay
    } else if (deltaSnr > 3.0 || deltaRmse > 1.2) {
      overlayType = "DIVERGENT_HIGH"; // Red 20% opacity overlay
    }

    const matchPercent = Math.max(0, Math.min(100, 100 - (deltaSnr / 18.0) * 100));

    results[p.id] = {
      deltaSnr: Number(deltaSnr.toFixed(3)),
      deltaRmse: Number(deltaRmse.toFixed(3)),
      overlayType,
      matchPercent: Number(matchPercent.toFixed(1)),
    };
  }

  const computeTimeMs = Number((performance.now() - start).toFixed(2));

  self.postMessage({
    photoAId,
    results,
    computeTimeMs,
  } satisfies WorkerOutput);
};
