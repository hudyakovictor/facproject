import { z } from "zod";
import { METRIC_KEYS, type MetricKey } from "./analysisStore";

/**
 * Кодирование состояния анализа в URL.
 *
 * §4 ТЗ требует, чтобы ссылка воспроизводила экран целиком: коллега должен
 * увидеть ровно то, что видит автор ссылки. Раньше `useNavigate`/`useSearch`
 * не использовались нигде, и состояние не покидало память вкладки.
 *
 * Все поля необязательны: короткий URL остаётся валидным, а неизвестные или
 * повреждённые значения не роняют навигацию, а отбрасываются.
 */


const boolish = z
  .union([z.boolean(), z.literal("1"), z.literal("0"), z.literal("true"), z.literal("false")])
  .transform((v) => v === true || v === "1" || v === "true");

const unitInterval = z.coerce.number().min(0).max(1);

export const analysisSearchSchema = z.object({
  pose: z.string().optional(),
  multi: boolish.optional(),
  q: unitInterval.optional(),
  mouth: unitInterval.optional(),
  angle: z.coerce.number().min(0).max(90).optional(),
  findings: boolish.optional(),
  search: z.string().optional(),
  a: z.string().optional(),
  b: z.string().optional(),
  photo: z.string().optional(),
  metrics: z
    .string()
    .optional()
    .transform((value) =>
      value
        ? value
            .split(",")
            .filter((item): item is MetricKey =>
              (METRIC_KEYS as readonly string[]).includes(item),
            )
        : undefined,
    )
    .optional(),
  blind: boolish.optional(),
});

export type AnalysisSearch = z.infer<typeof analysisSearchSchema>;

/**
 * Валидатор для TanStack Router. Некорректный параметр не должен приводить к
 * отказу навигации — пользователь получил бы пустой экран вместо страницы.
 */
export function validateAnalysisSearch(input: Record<string, unknown>): AnalysisSearch {
  const result = analysisSearchSchema.safeParse(input);
  return result.success ? result.data : {};
}

/** Пустые и умолчательные значения в URL не пишем, чтобы ссылка была читаемой. */
export function toSearchParams(state: {
  activePose: string;
  multiPose: boolean;
  qualityThreshold: number;
  mouthThreshold: number;
  poseAngleThreshold: number;
  findingsMode: boolean;
  search: string;
  pairA: string | null;
  pairB: string | null;
  selectedPhoto: string | null;
  visibleMetrics: MetricKey[];
  blindMode: boolean;
}): AnalysisSearch {
  const params: Record<string, unknown> = {};
  if (state.activePose !== "frontal") params.pose = state.activePose;
  if (state.multiPose) params.multi = true;
  if (state.qualityThreshold > 0) params.q = state.qualityThreshold;
  if (state.mouthThreshold !== 0.35) params.mouth = state.mouthThreshold;
  if (state.poseAngleThreshold !== 6) params.angle = state.poseAngleThreshold;
  if (state.findingsMode) params.findings = true;
  if (state.search) params.search = state.search;
  if (state.pairA) params.a = state.pairA;
  if (state.pairB) params.b = state.pairB;
  if (state.selectedPhoto) params.photo = state.selectedPhoto;
  if (state.blindMode) params.blind = true;
  return params as AnalysisSearch;
}
