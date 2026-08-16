/**
 * Определения слоёв левой области инспектора (§10.2).
 *
 * Список слоёв — это перечень артефактов Stage 1 и их систем координат, а не
 * настройка отображения: от системы координат зависит, можно ли слой наложить
 * на исходный кадр.
 */

export type LayerId =
  | "original"
  | "face_crop"
  | "face_mask"
  | "uv_texture"
  | "landmarks"
  | "visibility";

export interface LayerDef {
  id: LayerId;
  label: string;
  /** Файл артефакта Stage 1, если слой это картинка. */
  artifact: string | null;
  /** Слой лежит в системе координат исходного кадра. */
  inOriginalSpace: boolean;
  note: string;
}

export const LAYERS: readonly LayerDef[] = [
  {
    id: "original",
    label: "Исходный",
    artifact: "original.jpg",
    inOriginalSpace: true,
    note: "Кадр как он попал в архив, после применения EXIF-ориентации.",
  },
  {
    id: "face_crop",
    label: "Кроп лица",
    artifact: "face_crop.jpg",
    inOriginalSpace: false,
    note: "Кроп 224×224 по рамке ldm106. Своя система координат — поверх исходного не накладывается.",
  },
  {
    id: "face_mask",
    label: "Маска лица",
    artifact: "face_mask.png",
    inOriginalSpace: false,
    note: "Маска сегментации в системе кропа.",
  },
  {
    id: "uv_texture",
    label: "UV-текстура",
    artifact: "uv_texture.png",
    inOriginalSpace: false,
    note: "Развёртка текстуры в UV. Это не фотография, а атлас.",
  },
  {
    id: "landmarks",
    label: "Точки LDM",
    artifact: null,
    inOriginalSpace: true,
    note: "Точки ldm106/ldm134 в пикселях исходного кадра.",
  },
  {
    id: "visibility",
    label: "Видимость",
    artifact: null,
    inOriginalSpace: true,
    note: "Карта видимости вершин backend не отдаёт отдельным артефактом.",
  },
];

