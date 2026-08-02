import { useEffect, useRef } from "react";
import PhotoKeysPanel from "./PhotoKeysPanel";
import Icon from "./Icon";
import { t } from "../i18n";

/** Попап провенанса кадра — категория G карты размещения ключей.
 *
 * Отвечает на вопрос «откуда взялся этот результат и воспроизводим ли он»:
 * SHA-256 исходника, относительный путь, хэши кода/конфига/модели, версия
 * схемы, отметка времени извлечения, параметры камеры, нормализации и кропа.
 *
 * Отдельный попап, а не строка в панели: провенанс нужен редко, но целиком,
 * и не должен занимать место в вкладке, которую смотрят постоянно.
 */
export default function ProvenancePopup({ photoId, onClose }: {
  photoId: string;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Фокус переводится в диалог при открытии и возвращается по Escape:
  // без этого клавиатурный пользователь остаётся в фоне страницы.
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.stopPropagation(); onClose(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[70] bg-black/70 flex items-center justify-center p-6"
      onClick={onClose}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${t.provenanceTitle}: ${photoId}`}
        onClick={event => event.stopPropagation()}
        className="bg-surface border border-border-strong shadow-2xl w-[560px] max-h-[80vh] flex flex-col">
        <header className="flex items-center justify-between px-3 py-2 border-b border-border">
          <div>
            <div className="font-display text-sm tracking-forensic">{t.provenanceTitle}</div>
            <div className="font-mono text-[10px] text-text-muted">{photoId}</div>
          </div>
          <button ref={closeRef} onClick={onClose} aria-label={t.closeLabel}
            className="w-7 h-7 flex items-center justify-center border border-border hover:bg-critical/30">
            <Icon name="x" size={13} />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-3">
          <PhotoKeysPanel photoId={photoId} only={["G"]} defaultOpen />
        </div>
        <footer className="px-3 py-1.5 border-t border-border font-mono text-[8px] text-text-faint">
          {t.provenanceNote}
        </footer>
      </div>
    </div>
  );
}
