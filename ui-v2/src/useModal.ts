import { useEffect, useRef } from "react";

/** Доступность модального окна: focus trap, Escape, возврат фокуса.
 *
 * Пять модальных окон интерфейса (`SettingsModal`, `ComparisonPanel`,
 * `FullPhotoOverlay`, `FilterPanel`, `SourcesPanel`) перекрывали экран, но
 * не объявляли себя диалогами. Последствия для клавиатурного и
 * screen-reader пользователя:
 *
 *   * фокус оставался на элементах под оверлеем — Tab уводил в невидимую
 *     часть страницы, и было непонятно, где находишься;
 *   * screen reader продолжал читать фон как активное содержимое;
 *   * после закрытия фокус терялся в начале документа, а не возвращался
 *     на кнопку, которой окно открыли.
 *
 * Хук решает это одним вызовом и возвращает ref, который вешается на
 * контейнер диалога.
 *
 * WCAG 2.1: 2.1.2 (No Keyboard Trap — выход по Escape), 2.4.3 (Focus
 * Order), 4.1.2 (Name, Role, Value — вместе с `role="dialog"`).
 */
export function useModal<T extends HTMLElement = HTMLDivElement>(onClose: () => void) {
  const ref = useRef<T>(null);
  /** Элемент, у которого был фокус до открытия: туда его и вернём. */
  const restoreRef = useRef<Element | null>(null);

  useEffect(() => {
    restoreRef.current = document.activeElement;

    // Фокус переводится внутрь диалога: первый интерактивный элемент, а
    // если таких нет — сам контейнер (он получает tabIndex={-1}).
    const container = ref.current;
    const focusable = () => Array.from(
      container?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    ).filter(el => {
      // `aria-hidden` и `hidden` исключаются всегда. Проверять
      // `offsetParent`/`getBoundingClientRect` нельзя: в jsdom они дают
      // ноль для любого элемента, и фильтр отбросил бы весь диалог —
      // focus trap молча перестал бы работать в тестах, а вместе с ним
      // и уверенность, что он работает в браузере.
      if (el.hasAttribute("hidden") || el.getAttribute("aria-hidden") === "true") return false;
      return el.closest("[hidden]") === null;
    });

    const first = focusable()[0];
    (first ?? container)?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        // stopPropagation: вложенный диалог (провенанс поверх панели)
        // должен закрываться по одному Escape, а не вместе с родителем.
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const items = focusable();
      if (items.length === 0) {
        event.preventDefault();
        container?.focus();
        return;
      }
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      const active = document.activeElement;

      // Цикл по кругу внутри диалога вместо ухода в фон.
      if (event.shiftKey && (active === firstItem || !container?.contains(active))) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && active === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      // Возврат фокуса: только если элемент всё ещё в документе.
      const restore = restoreRef.current;
      if (restore instanceof HTMLElement && document.contains(restore)) restore.focus();
    };
  }, [onClose]);

  return ref;
}

/** Пропсы, которые обязан объявить контейнер диалога.
 *
 * Функция, а не константа: `aria-label` у каждого окна свой, а забыть его
 * легко — тогда screen reader объявит окно как безымянное. */
export function modalProps(label: string) {
  return {
    role: "dialog" as const,
    "aria-modal": true,
    "aria-label": label,
    tabIndex: -1,
  };
}
