import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { ResearchPhoto } from "../../shared/researchApi";
import { consoleLogger } from "../../shared/logger";
import {
  SIDECAR_FIELDS,
  SIDECAR_SCHEMA_ID,
  claimedDateDelta,
  sidecarSchema,
  type SidecarValues,
} from "./sidecarSchema";
import styles from "./dataManager.module.css";

/**
 * Редактор provenance-sidecar (§7.3 ТЗ).
 *
 * Проверка выполняется по той же схеме, что применяет backend
 * (`app6/schemas/provenance_sidecar_v1.json`), — иначе интерфейс принимал бы
 * записи, которые сервер отвергнет.
 *
 * Сохранения на сервер здесь нет и не может быть: эндпоинта для sidecar в API
 * не существует (задача B-02). Поэтому форма отдаёт готовый JSON для файла
 * рядом с изображением и говорит об этом прямо. Кнопка «Сохранить», которая
 * ничего не сохраняет, создала бы ложную уверенность, что происхождение
 * задокументировано в системе.
 *
 * Конфликт заявленной даты с датой кадра показывается, но не устраняется:
 * §7.2 запрещает молча исправлять даты, и это тот же запрет — выбор между
 * двумя источниками даты остаётся за человеком.
 */

export interface SidecarEditorProps {
  photo: ResearchPhoto;
}

export function SidecarEditor({ photo }: SidecarEditorProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isValid },
  } = useForm<SidecarValues>({
    resolver: zodResolver(sidecarSchema),
    mode: "onChange",
    defaultValues: {
      source_url: "",
      archive_url: "",
      publisher: "",
      acquired_at: "",
      collector: "",
      claimed_date: "",
      rights: "",
      notes: "",
    },
  });

  const claimed = watch("claimed_date");
  const delta = claimedDateDelta(claimed?.trim() || undefined, photo.date);

  const download = (values: SidecarValues) => {
    // Пустые поля не попадают в файл: пустая строка в JSON неотличима от
    // заполненного пустого значения, а схема запрещает лишние ключи.
    const payload = Object.fromEntries(
      Object.entries(values)
        .map(([key, value]) => [key, typeof value === "string" ? value.trim() : value])
        .filter(([, value]) => value !== "" && value !== undefined),
    );
    const text = JSON.stringify({ $schema: SIDECAR_SCHEMA_ID, ...payload }, null, 2);
    const blob = new Blob([text], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${photo.id}.provenance.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    consoleLogger.addLog(
      "INFO",
      "DATA",
      `Sidecar сформирован для ${photo.id}`,
      Object.keys(payload).join(", ") || "пусто",
    );
  };

  return (
    <form className={styles.sidecar} onSubmit={handleSubmit(download)}>
      <h4 className={styles.drawerSection}>Происхождение (sidecar)</h4>

      <p className={styles.drawerNote}>
        Проверяется по схеме {SIDECAR_SCHEMA_ID}, той же, что применяет backend.
      </p>

      {SIDECAR_FIELDS.map((field) => {
        const error = errors[field.name];
        return (
          <label key={field.name} className={styles.sidecarField}>
            <span className={styles.sidecarLabel}>{field.label}</span>
            {field.multiline ? (
              <textarea rows={2} placeholder={field.placeholder} {...register(field.name)} />
            ) : (
              <input placeholder={field.placeholder} {...register(field.name)} />
            )}
            {field.hint && <span className={styles.sidecarHint}>{field.hint}</span>}
            {error && (
              <span className={styles.sidecarError} role="alert">
                {String(error.message)}
              </span>
            )}
          </label>
        );
      })}

      {delta?.conflict && (
        <p className={styles.sidecarConflict} role="alert">
          Заявленная дата расходится с датой кадра ({photo.date}) на{" "}
          {Math.abs(delta.days).toLocaleString("ru-RU")} дн. Обе даты сохраняются как
          есть: выбрать между ними может только человек, знающий источник.
        </p>
      )}

      <div className={styles.ingestActions}>
        <button type="submit" className={styles.primaryButton} disabled={!isValid}>
          Сформировать файл sidecar
        </button>
      </div>

      <p className={styles.drawerNote}>
        Отправить запись на сервер нельзя: эндпоинта для sidecar в API нет (задача
        B-02). Файл кладётся рядом с изображением и попадёт в систему при
        следующем извлечении.
      </p>
    </form>
  );
}
