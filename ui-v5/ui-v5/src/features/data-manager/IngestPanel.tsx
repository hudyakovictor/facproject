import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { useUploadPhoto } from "../../shared/api/queries";
import { describeError } from "../../shared/ui/errorDetail";
import { isAcceptable, parseFilename, type ParsedName } from "./ingest";
import styles from "./dataManager.module.css";

/**
 * Область приёма файлов (§7.1–7.2 ТЗ).
 *
 * Перед отправкой показывается разбор имени: какая дата прочитана, какой
 * идентификатор будет предложен и что мешает принять файл. Дата не
 * исправляется автоматически — ТЗ запрещает это прямо, и запрет содержательный:
 * подставленное время съёмки невозможно отличить от прочитанного.
 *
 * Проверки, требующие чтения содержимого (magic bytes, decode-тест, EXIF,
 * перцептивные дубликаты), здесь не имитируются: они выполняются backend при
 * извлечении, и об этом сказано в панели. Зелёная галочка «проверено» без
 * проверки хуже её отсутствия.
 */

interface Candidate {
  file: File;
  parsed: ParsedName;
  status: "pending" | "uploading" | "done" | "error";
  message?: string;
}

export function IngestPanel() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadPhoto();

  const addFiles = (files: FileList | null) => {
    if (!files) return;
    const next: Candidate[] = Array.from(files).map((file) => ({
      file,
      parsed: parseFilename(file.name),
      status: "pending",
    }));
    setCandidates((prev) => [...prev, ...next]);
  };

  const acceptable = candidates.filter(
    (candidate) => candidate.status === "pending" && isAcceptable(candidate.parsed),
  );

  const sendAll = async () => {
    for (const candidate of acceptable) {
      setCandidates((prev) =>
        prev.map((item) =>
          item.file === candidate.file ? { ...item, status: "uploading" } : item,
        ),
      );
      try {
        await upload.mutateAsync(candidate.file);
        setCandidates((prev) =>
          prev.map((item) =>
            item.file === candidate.file ? { ...item, status: "done" } : item,
          ),
        );
      } catch (error) {
        setCandidates((prev) =>
          prev.map((item) =>
            item.file === candidate.file
              ? { ...item, status: "error", message: describeError(error).message }
              : item,
          ),
        );
      }
    }
  };

  return (
    <section className={styles.ingest}>
      <div
        className={`${styles.dropZone} ${dragging ? styles.dropZoneActive : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          addFiles(event.dataTransfer.files);
        }}
      >
        <UploadCloud className="h-5 w-5" aria-hidden="true" />
        <p className={styles.dropText}>
          Перетащите файлы сюда или{" "}
          <button
            type="button"
            className={styles.linkButton}
            onClick={() => inputRef.current?.click()}
          >
            выберите на диске
          </button>
        </p>
        <p className={styles.dropHint}>
          Принимаются .jpg, .jpeg, .png с именем ГГГГ_ММ_ДД[_N]. Дата берётся из
          имени и не исправляется автоматически.
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".jpg,.jpeg,.png"
          className="sr-only"
          aria-label="Выбрать файлы для загрузки"
          onChange={(event) => addFiles(event.target.files)}
        />
      </div>

      {candidates.length > 0 && (
        <>
          <table className={styles.ingestTable}>
            <thead>
              <tr>
                <th scope="col">Файл</th>
                <th scope="col">Дата из имени</th>
                <th scope="col">Идентификатор</th>
                <th scope="col">Состояние</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr key={`${candidate.file.name}-${candidate.file.size}`}>
                  <td>{candidate.file.name}</td>
                  <td className={candidate.parsed.date ? undefined : styles.cellMissing}>
                    {candidate.parsed.date ?? "не прочитана"}
                  </td>
                  <td>{candidate.parsed.proposedId ?? "—"}</td>
                  <td>
                    {candidate.status === "done" && (
                      <span className={styles.jobOk}>загружен</span>
                    )}
                    {candidate.status === "uploading" && "отправка…"}
                    {candidate.status === "error" && (
                      <span className={styles.jobFail}>{candidate.message}</span>
                    )}
                    {candidate.status === "pending" &&
                      (candidate.parsed.problems.length > 0 ? (
                        <span className={styles.jobFail}>
                          {candidate.parsed.problems.join("; ")}
                        </span>
                      ) : (
                        "готов к отправке"
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className={styles.ingestActions}>
            <button
              type="button"
              className={styles.primaryButton}
              disabled={acceptable.length === 0 || upload.isPending}
              onClick={() => void sendAll()}
            >
              Загрузить {acceptable.length > 0 ? `(${acceptable.length})` : ""}
            </button>
            <button
              type="button"
              className={styles.linkButton}
              onClick={() => setCandidates([])}
            >
              Очистить список
            </button>
          </div>

          <p className={styles.dropHint}>
            Загрузка сохраняет файл, но не запускает извлечение: содержимое
            проверяется backend при выполнении задания. Проверки magic bytes,
            EXIF и дубликатов здесь не выполняются и не показываются как
            выполненные.
          </p>
        </>
      )}
    </section>
  );
}
