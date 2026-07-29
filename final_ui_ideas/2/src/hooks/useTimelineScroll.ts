import { useEffect, useRef } from "react";

/**
 * Синхронизирует горизонтальный скролл между всеми зонами таймлайна.
 *
 * - Конвертирует вертикальное колесо мыши в горизонтальный скролл (как в Figma / DaVinci).
 * - Shift+wheel = обычная горизонтальная прокрутка.
 * - Ctrl+wheel = zoom (опционально, через onZoom).
 * - Drag средней кнопкой или Space+drag = pan.
 * - Нативный listener с { passive: false } для корректного preventDefault.
 */
export function useTimelineScroll(
  ref: React.RefObject<HTMLElement | null>,
  options: {
    zoom: number;
    scrollRatio: number;
    setScrollRatio: (v: number) => void;
    viewportWidth: number;
    onZoom?: (delta: number) => void;
  }
) {
  const { zoom, scrollRatio, setScrollRatio, viewportWidth, onZoom } = options;
  const isPanning = useRef(false);
  const panStart = useRef({ x: 0, scrollRatio: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      const totalW = viewportWidth * zoom;
      const maxScroll = Math.max(1, totalW - viewportWidth);

      // Ctrl+wheel → zoom
      if (e.ctrlKey && onZoom) {
        e.preventDefault();
        const zoomDelta = e.deltaY > 0 ? -0.1 : 0.1;
        onZoom(zoomDelta);
        return;
      }

      e.preventDefault();

      let deltaX = e.deltaX;
      let deltaY = e.deltaY;

      // Shift+wheel уже даёт deltaX в большинстве браузеров
      if (e.shiftKey) {
        deltaX = deltaX || deltaY;
        deltaY = 0;
      }

      // Если вертикальный wheel без shift → конвертируем в горизонтальный
      if (deltaY !== 0 && deltaX === 0) {
        deltaX = deltaY;
      }

      const currentOffset = scrollRatio * maxScroll;
      // Коэффициент скорости: 1 pixel wheel = 1 pixel scroll (но с учётом DPR)
      const newOffset = Math.max(0, Math.min(maxScroll, currentOffset + deltaX));
      const newRatio = newOffset / maxScroll;
      setScrollRatio(isFinite(newRatio) ? newRatio : 0);
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [ref, zoom, scrollRatio, setScrollRatio, viewportWidth, onZoom]);

  // Drag-pan: средняя кнопка или Space+Left click
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    let spacePressed = false;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && (e.target as HTMLElement)?.tagName !== "INPUT") {
        spacePressed = true;
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") spacePressed = false;
    };

    const onMouseDown = (e: MouseEvent) => {
      if (e.button === 1 || (e.button === 0 && spacePressed)) {
        isPanning.current = true;
        panStart.current = { x: e.clientX, scrollRatio };
        e.preventDefault();
        document.body.style.cursor = "grabbing";
      }
    };
    const onMouseMove = (e: MouseEvent) => {
      if (!isPanning.current) return;
      const totalW = viewportWidth * zoom;
      const maxScroll = Math.max(1, totalW - viewportWidth);
      const dx = panStart.current.x - e.clientX;
      const newOffset = Math.max(0, Math.min(maxScroll, panStart.current.scrollRatio * maxScroll + dx));
      setScrollRatio(newOffset / maxScroll);
    };
    const onMouseUp = () => {
      if (isPanning.current) {
        isPanning.current = false;
        document.body.style.cursor = "";
      }
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    el.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);

    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      el.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [ref, zoom, scrollRatio, setScrollRatio, viewportWidth]);
}
