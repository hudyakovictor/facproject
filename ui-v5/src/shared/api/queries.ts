import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { calibrationHealth, researchTimeline, runSummary } from "../researchApi";
import { getValidated, mutateValidated } from "./client";
import {
  DeleteResultSchema,
  JobCancelSchema,
  JobListSchema,
  JobSubmitSchema,
  LandmarksSchema,
  PhotoInfoKeysSchema,
  PhotoInventorySchema,
  SkinZonesSchema,
  UploadResultSchema,
  ZoneCatalogSchema,
} from "./schemas";

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
  jobs: ["jobs"] as const,
  photoInventory: (offset: number, limit: number, poseBin: string | null) =>
    ["photo-inventory", offset, limit, poseBin] as const,
  photoInfoKeys: (photoId: string) => ["photo-info-keys", photoId] as const,
  skinZones: (photoId: string) => ["skin-zones", photoId] as const,
  zoneCatalog: ["zone-catalog"] as const,
  landmarks: (photoId: string, count: number, space: string) =>
    ["landmarks", photoId, count, space] as const,
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

/**
 * Очередь заданий (§7.7).
 *
 * Пока хотя бы одно задание не в терминальном состоянии, список опрашивается
 * раз в две секунды. Опрос останавливается сам: постоянный таймер на экране,
 * где ничего не происходит, тратит батарею и засоряет журнал запросов.
 */
export function useJobs(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.jobs,
    queryFn: () => getValidated("/api/v1/jobs", JobListSchema),
    retry: retryPolicy,
    enabled: options.enabled ?? true,
    refetchInterval: (query) => {
      const jobs = query.state.data?.jobs ?? [];
      const active = jobs.some(
        (job) => job.status === "queued" || job.status === "running",
      );
      return active ? 2000 : false;
    },
  });
}

/** Постраничный инвентарь Stage 1. */
export function usePhotoInventory(
  params: { offset: number; limit: number; poseBin?: string | null },
  options: { enabled?: boolean } = {},
) {
  const { offset, limit, poseBin = null } = params;
  return useQuery({
    queryKey: queryKeys.photoInventory(offset, limit, poseBin),
    queryFn: () => {
      const search = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
      });
      if (poseBin) search.set("pose_bin", poseBin);
      return getValidated(`/api/v1/photos?${search.toString()}`, PhotoInventorySchema);
    },
    retry: retryPolicy,
    enabled: options.enabled ?? true,
  });
}

export interface SubmitJobInput {
  kind: "extract" | "recompute_metrics";
  input_dir?: string;
  output_dir?: string;
  stage1_root?: string;
  calibration_root?: string;
  device?: string;
  limit?: number;
}

export function useSubmitJob() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: SubmitJobInput) =>
      mutateValidated("/api/v1/jobs", JobSubmitSchema, { method: "POST", body: input }),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.jobs }),
  });
}

export function useCancelJob() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) =>
      mutateValidated(`/api/v1/jobs/${encodeURIComponent(jobId)}/cancel`, JobCancelSchema, {
        method: "POST",
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.jobs }),
  });
}

export function useUploadPhoto() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return mutateValidated("/api/v1/photos/upload", UploadResultSchema, {
        method: "POST",
        body: form,
      });
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.timeline }),
  });
}

/**
 * Удаление производных Stage 1. Исходный файл backend не трогает — интерфейс
 * обязан говорить об этом прямо, чтобы «удалить» не читалось как «стереть
 * фотографию из архива».
 */
export function useDeletePhotoDerivatives() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (photoId: string) =>
      mutateValidated(`/api/v1/photos/${encodeURIComponent(photoId)}`, DeleteResultSchema, {
        method: "DELETE",
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.timeline }),
  });
}

// ---------------------------------------------------------------------------
// Инспектор кадра (§10)
// ---------------------------------------------------------------------------

/**
 * Полный `info.json` кадра. Данные неизменны после извлечения Stage 1, поэтому
 * перезапрашивать их при возврате на вкладку незачем.
 */
export function usePhotoInfoKeys(photoId: string | null) {
  return useQuery({
    queryKey: queryKeys.photoInfoKeys(photoId ?? ""),
    queryFn: () =>
      getValidated(
        `/api/v1/photos/${encodeURIComponent(photoId ?? "")}/info_keys`,
        PhotoInfoKeysSchema,
      ),
    retry: retryPolicy,
    enabled: Boolean(photoId),
    staleTime: Infinity,
  });
}

/** Измерения по 40 зонам кожи для конкретного кадра. */
export function useSkinZones(photoId: string | null) {
  return useQuery({
    queryKey: queryKeys.skinZones(photoId ?? ""),
    queryFn: () =>
      getValidated(
        `/api/v1/photos/${encodeURIComponent(photoId ?? "")}/skin_zones`,
        SkinZonesSchema,
      ),
    retry: retryPolicy,
    enabled: Boolean(photoId),
    staleTime: Infinity,
  });
}

/** Атлас зон: один на весь архив, грузится один раз. */
export function useZoneCatalog(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.zoneCatalog,
    queryFn: () => getValidated("/api/v1/zones/catalog", ZoneCatalogSchema),
    retry: retryPolicy,
    enabled: options.enabled ?? true,
    staleTime: Infinity,
  });
}

/**
 * Ландмарки в конкретном пространстве. Пространство — часть ключа кеша:
 * `original` и `chronology` это разные числа, а не разный вид одних и тех же.
 */
export function useLandmarks(
  photoId: string | null,
  count: number,
  space: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: queryKeys.landmarks(photoId ?? "", count, space),
    queryFn: () =>
      getValidated(
        `/api/v1/photos/${encodeURIComponent(photoId ?? "")}/landmarks/${count}/${space}`,
        LandmarksSchema,
      ),
    retry: retryPolicy,
    enabled: Boolean(photoId) && (options.enabled ?? true),
    staleTime: Infinity,
  });
}
