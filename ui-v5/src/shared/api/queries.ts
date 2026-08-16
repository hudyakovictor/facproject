import { useQuery } from "@tanstack/react-query";
import { calibrationHealth, researchTimeline, runSummary } from "../researchApi";

/**
 * Единые ключи и хуки запросов.
 *
 * Раньше тринадцать файлов заводили собственный `useQuery` с ключом-строкой,
 * набранным вручную. Опечатка в ключе означала бы второй сетевой запрос и
 * рассинхрон данных между экранами, а изменить политику кеширования можно было
 * только правкой всех файлов сразу.
 */
export const queryKeys = {
  timeline: ["research-timeline"] as const,
  runSummary: ["run-summary"] as const,
  calibrationHealth: ["calibration-health"] as const,
};

/** Ошибки контракта и 4xx повторять бессмысленно — причина не в сети. */
function retryPolicy(failureCount: number, error: unknown): boolean {
  const status = (error as { status?: number } | null)?.status;
  if (typeof status === "number" && status >= 400 && status < 500) return false;
  if ((error as { name?: string } | null)?.name === "ContractError") return false;
  return failureCount < 2;
}

export function useTimeline() {
  return useQuery({
    queryKey: queryKeys.timeline,
    queryFn: researchTimeline,
    retry: retryPolicy,
  });
}

export function useRunSummary() {
  return useQuery({
    queryKey: queryKeys.runSummary,
    queryFn: runSummary,
    retry: retryPolicy,
  });
}

export function useCalibrationHealth() {
  return useQuery({
    queryKey: queryKeys.calibrationHealth,
    queryFn: calibrationHealth,
    retry: retryPolicy,
  });
}
