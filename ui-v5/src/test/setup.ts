import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());

/**
 * ResizeObserver в jsdom отсутствует.
 *
 * Пустая заглушка недостаточна для виртуализированных списков: TanStack
 * Virtual узнаёт высоту области прокрутки именно из первого вызова
 * наблюдателя, и без него считает, что видно ноль пикселей, — в разметку не
 * попадает ни одна строка. Заглушка сообщает размер сразу после `observe`,
 * иначе тесты таблицы проверяли бы пустой контейнер.
 */
class ResizeObserverMock implements ResizeObserver {
  private readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element): void {
    const rect = target.getBoundingClientRect();
    this.callback(
      [
        {
          target,
          contentRect: rect,
          borderBoxSize: [{ inlineSize: rect.width, blockSize: rect.height }],
          contentBoxSize: [{ inlineSize: rect.width, blockSize: rect.height }],
          devicePixelContentBoxSize: [{ inlineSize: rect.width, blockSize: rect.height }],
        } as unknown as ResizeObserverEntry,
      ],
      this,
    );
  }

  unobserve(): void {}
  disconnect(): void {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
  writable: true,
  value: ResizeObserverMock,
});

Object.defineProperty(globalThis, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

/**
 * Размеры элементов в jsdom.
 *
 * jsdom не выполняет layout: `getBoundingClientRect` всегда возвращает нули.
 * Виртуализированные списки из-за этого считают, что видимая область пуста, и
 * не отрисовывают ни одной строки — тест «в таблице нет лишних строк» проходил
 * бы на пустом контейнере, ничего не проверяя.
 *
 * Заглушка отдаёт высоту из inline-стиля, если он задан, и разумную величину
 * по умолчанию. Это не эмуляция вёрстки, а минимум, при котором проверки
 * содержимого осмысленны.
 */
const DEFAULT_VIEWPORT_HEIGHT = 600;
const DEFAULT_VIEWPORT_WIDTH = 1200;

HTMLElement.prototype.getBoundingClientRect = function (this: HTMLElement): DOMRect {
  const inline = this.style.height;
  const height = inline.endsWith("px") ? Number.parseInt(inline, 10) : DEFAULT_VIEWPORT_HEIGHT;
  return {
    width: DEFAULT_VIEWPORT_WIDTH,
    height,
    top: 0,
    left: 0,
    right: DEFAULT_VIEWPORT_WIDTH,
    bottom: height,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect;
};
