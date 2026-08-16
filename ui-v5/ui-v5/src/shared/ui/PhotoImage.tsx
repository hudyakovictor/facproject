import { useState } from "react";
import { ImageOff } from "lucide-react";
import styles from "./photoImage.module.css";

/**
 * Превью кадра с честной обработкой отказа.
 *
 * `/api/v1/photos/{id}/image` отдаёт 404, когда исходник недоступен: архив
 * лежит на съёмном носителе (`/Volumes/SDCARD/storage`), которого на машине
 * может не быть. Раньше ни один `<img>` не имел `onError`, и такой кадр
 * показывался иконкой сломанного изображения — неотличимо от сбоя интерфейса
 * (D24). Здесь отказ подписан словами.
 */
export function PhotoImage({
  photoId,
  alt,
  className,
  variant = "cover",
  loading = "lazy",
}: {
  photoId: string;
  alt: string;
  className?: string;
  variant?: "cover" | "contain";
  loading?: "lazy" | "eager";
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span
        className={`${styles.fallback} ${className ?? ""}`}
        role="img"
        aria-label={`${alt}: изображение недоступно`}
        title="Исходный файл недоступен: архив не смонтирован либо кадр удалён"
      >
        <ImageOff className={styles.icon} aria-hidden="true" />
        <span className={styles.text}>нет файла</span>
      </span>
    );
  }

  return (
    <img
      src={`/api/v1/photos/${encodeURIComponent(photoId)}/image`}
      alt={alt}
      loading={loading}
      decoding="async"
      onError={() => setFailed(true)}
      className={`${variant === "cover" ? styles.cover : styles.contain} ${className ?? ""}`}
    />
  );
}
