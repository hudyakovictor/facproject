import { createContext, useContext } from "react";
import type { Photo } from "./data";
export interface MetricRef { median: number; std: number }
export interface BaselineRefs {
  refs: Record<string, MetricRef>; baselineEra: string | null; sampleSize: number;
  sufficient: boolean; source: "pipeline" | "unavailable";
}
export const MIN_BASELINE_SAMPLE = 8;
export const BASELINE_METRIC_KEYS = ["boneScore","orbit","chin","jaw","cheek","symmetry","yaw","siliconeProb","specular","lbpEntropy","frangi","wrinkle","subsurface","visualAge"] as const;
/** UI never estimates a forensic baseline. It must arrive as a versioned pipeline artifact. */
export function computeBaselineRefs(_photos: Photo[]): BaselineRefs {
  return { refs: {}, baselineEra: null, sampleSize: 0, sufficient: false, source: "unavailable" };
}
export const EMPTY_BASELINE: BaselineRefs = { refs: {}, baselineEra: null, sampleSize: 0, sufficient: false, source: "unavailable" };
export const BaselineContext = createContext<BaselineRefs>(EMPTY_BASELINE);
export function useBaseline(): BaselineRefs { return useContext(BaselineContext); }
