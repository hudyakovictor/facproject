import { useEffect, useRef } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useAnalysisStore } from "./analysisStore";
import { toSearchParams, type AnalysisSearch } from "./urlState";

/**
 * Двусторонняя синхронизация стора и строки запроса.
 *
 * При первом рендере состояние берётся из URL — так открывается присланная
 * ссылка. Дальше изменения стора пишутся обратно через `replace`, чтобы
 * настройка фильтров не засоряла историю браузера кнопкой «назад».
 */
export function useUrlSync() {
  const navigate = useNavigate();
  const search = useSearch({ strict: false }) as AnalysisSearch;
  const hydrated = useRef(false);

  const state = useAnalysisStore();

  // URL → стор, однократно при монтировании маршрута.
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    const patch: Parameters<typeof state.hydrate>[0] = {};
    if (search.pose) patch.activePose = search.pose;
    if (search.multi !== undefined) patch.multiPose = search.multi;
    if (search.q !== undefined) patch.qualityThreshold = search.q;
    if (search.mouth !== undefined) patch.mouthThreshold = search.mouth;
    if (search.angle !== undefined) patch.poseAngleThreshold = search.angle;
    if (search.findings !== undefined) patch.findingsMode = search.findings;
    if (search.search) patch.search = search.search;
    if (search.a) patch.pairA = search.a;
    if (search.b) patch.pairB = search.b;
    if (search.photo) patch.selectedPhoto = search.photo;
    if (search.metrics?.length) patch.visibleMetrics = search.metrics;
    if (search.blind !== undefined) patch.blindMode = search.blind;
    if (Object.keys(patch).length) state.hydrate(patch);
  }, [search, state]);

  // Стор → URL.
  useEffect(() => {
    if (!hydrated.current) return;
    const next = toSearchParams(state);
    void navigate({ to: ".", search: next, replace: true });
  }, [
    navigate,
    state.activePose,
    state.multiPose,
    state.qualityThreshold,
    state.mouthThreshold,
    state.poseAngleThreshold,
    state.findingsMode,
    state.search,
    state.pairA,
    state.pairB,
    state.selectedPhoto,
    state.blindMode,
    state,
  ]);
}
