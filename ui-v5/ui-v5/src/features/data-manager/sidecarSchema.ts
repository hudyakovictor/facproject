import { z } from "zod";

/**
 * Схема provenance-sidecar (§7.3 ТЗ).
 *
 * Зеркало `app6/schemas/provenance_sidecar_v1.json`. Правила скопированы с
 * канонической схемы, а не придуманы заново:
 *  - `source_url` и `archive_url` обязаны начинаться с http(s);
 *  - `acquired_at` — дата и время, `claimed_date` — только дата;
 *  - `additionalProperties: false` — посторонние поля недопустимы;
 *  - `anyOf` требует хотя бы один из двух адресов.
 *
 * Последнее правило содержательное: запись о происхождении без ссылки на
 * источник или архивную копию не является свидетельством происхождения. Она
 * выглядела бы как заполненный документ, не будучи проверяемой.
 *
 * Расхождение с канонической схемой означало бы, что интерфейс принимает
 * данные, которые backend отвергнет, — поэтому идентификатор схемы вынесен в
 * константу и показывается пользователю.
 */

export const SIDECAR_SCHEMA_ID = "deeputin-provenance-sidecar-v1";

const httpUrl = z
  .string()
  .trim()
  .regex(/^https?:\/\/\S+$/, "Адрес должен начинаться с http:// или https://");

/** Пустая строка означает «поле не заполнено», а не «пустое значение». */
const optionalText = z
  .string()
  .trim()
  .optional()
  .transform((value) => (value === "" ? undefined : value))
  .optional();

export const sidecarSchema = z
  .object({
    source_url: z.union([httpUrl, z.literal("")]).optional(),
    archive_url: z.union([httpUrl, z.literal("")]).optional(),
    publisher: optionalText,
    acquired_at: z
      .union([
        z
          .string()
          .trim()
          .regex(
            /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?$/,
            "Формат: ГГГГ-ММ-ДД или ГГГГ-ММ-ДДTЧЧ:ММ",
          ),
        z.literal(""),
      ])
      .optional(),
    collector: optionalText,
    claimed_date: z
      .union([
        z.string().trim().regex(/^\d{4}-\d{2}-\d{2}$/, "Формат даты: ГГГГ-ММ-ДД"),
        z.literal(""),
      ])
      .optional(),
    rights: optionalText,
    notes: optionalText,
  })
  .refine(
    (value) => Boolean(value.source_url?.trim()) || Boolean(value.archive_url?.trim()),
    {
      message:
        "Нужен адрес источника или архивной копии: без ссылки запись о происхождении нечем проверить.",
      path: ["source_url"],
    },
  );

export type SidecarValues = z.input<typeof sidecarSchema>;

export interface SidecarFieldSpec {
  name: keyof SidecarValues;
  label: string;
  placeholder?: string;
  hint?: string;
  multiline?: boolean;
}

export const SIDECAR_FIELDS: readonly SidecarFieldSpec[] = [
  {
    name: "source_url",
    label: "Адрес источника",
    placeholder: "https://…",
    hint: "Страница, где кадр опубликован.",
  },
  {
    name: "archive_url",
    label: "Архивная копия",
    // Без примера настоящего архивного адреса: гейт синтетических данных
    // намеренно не отличает подсказку в поле от подставленного значения, и
    // это правильная строгость — образец легко превращается в данные.
    placeholder: "https://…",
    hint: "Снимок страницы: исходная публикация может исчезнуть.",
  },
  { name: "publisher", label: "Издатель", placeholder: "Название издания" },
  {
    name: "acquired_at",
    label: "Время получения",
    placeholder: "2026-08-16T12:30",
    hint: "Когда файл был получен собирающим, а не когда сделан снимок.",
  },
  { name: "collector", label: "Кто получил", placeholder: "Имя или идентификатор" },
  {
    name: "claimed_date",
    label: "Заявленная дата съёмки",
    placeholder: "2014-03-18",
    hint: "Дата со слов источника. Не заменяет дату из имени файла и может с ней расходиться.",
  },
  { name: "rights", label: "Права и лицензия", placeholder: "CC BY-SA 4.0, © издание…" },
  { name: "notes", label: "Примечания", multiline: true },
];

/**
 * Расхождение между заявленной датой и датой кадра.
 *
 * Конфликт не разрешается автоматически: обе даты остаются, и показывается
 * величина расхождения. Выбрать «правильную» может только человек, знающий
 * источник.
 */
export function claimedDateDelta(
  claimed: string | undefined,
  actual: string | null,
): { days: number; conflict: boolean } | null {
  if (!claimed || !actual) return null;
  const a = Date.parse(claimed);
  const b = Date.parse(actual);
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  const days = Math.round((a - b) / 86_400_000);
  return { days, conflict: days !== 0 };
}
