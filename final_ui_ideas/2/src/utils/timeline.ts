import { useMemo } from "react";

export const TIMELINE_START = new Date("1999-01-01").getTime();
export const TIMELINE_END = new Date("2027-01-01").getTime();
export const TIMELINE_YEARS = 28; // 1999..2027

export const YEAR_MS = 365.25 * 24 * 3600 * 1000;

export function dateToRatio(ts: number): number {
  return (ts - TIMELINE_START) / (TIMELINE_END - TIMELINE_START);
}
export function yearToRatio(year: number): number {
  return (new Date(`${year}-01-01`).getTime() - TIMELINE_START) / (TIMELINE_END - TIMELINE_START);
}

export function useTimelineMetrics(width: number, zoom: number, scrollRatio: number) {
  return useMemo(() => {
    const totalW = width * zoom;
    const offset = scrollRatio * (totalW - width);
    return { totalW, offset, pxPerYear: totalW / TIMELINE_YEARS };
  }, [width, zoom, scrollRatio]);
}

export const ZONE_COLORS = {
  bone: "#4f98a3",
  orbits: "#6daa45",
  chin: "#e8af34",
  jaw: "#fdab43",
  cheekbones: "#a86fdf",
  symmetry: "#5591c7",
  pose: "#797876",
  silicone: "#a13544",
  gloss: "#4f98a3",
  lbp: "#6daa45",
  frangi: "#5591c7",
  wrinkle: "#e8af34",
  subsurface: "#a86fdf",
  visualAge: "#fdab43",
};
