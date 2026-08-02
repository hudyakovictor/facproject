import { describe, expect, it, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";
import FullPhotoOverlay from "../components/FullPhotoOverlay";

import { buildDemoPhotos } from "../demoData";

/** Демо-набор как тестовая фикстура: генератор вынесен из основного
 * бандла (аудит №27), поэтому строим его явно. */
const DEMO_PHOTOS = buildDemoPhotos();

vi.mock("../components/LazyMeshViewer", () => ({ default: () => null }));

function mockMotionPreference(reduce: boolean) {
  vi.stubGlobal("matchMedia", vi.fn().mockImplementation((q: string) => ({
    matches: q.includes("prefers-reduced-motion") ? reduce : false,
    media: q, addEventListener: vi.fn(), removeEventListener: vi.fn(),
    addListener: vi.fn(), removeListener: vi.fn(), onchange: null, dispatchEvent: vi.fn(),
  })));
}

// Кадр с сильным отклонением: |z| > 2 включает пульсацию.
const photo = { ...DEMO_PHOTOS[0], zChinProj: 3.5, zOrbitDepth: 3.2 };

afterEach(() => vi.unstubAllGlobals());

describe("prefers-reduced-motion for SVG SMIL", () => {
  it("renders <animate> when motion is allowed", () => {
    mockMotionPreference(false);
    const { container } = render(<FullPhotoOverlay photo={photo} onClose={() => undefined} />);
    expect(container.querySelectorAll("animate").length).toBeGreaterThan(0);
  });

  it("REGRESSION: emits no <animate> when the user asks for reduced motion", () => {
    // CSS `animation:none` не останавливает SMIL — элементы не должны
    // рендериться вовсе (WCAG 2.3.3).
    mockMotionPreference(true);
    const { container } = render(<FullPhotoOverlay photo={photo} onClose={() => undefined} />);
    expect(container.querySelectorAll("animate")).toHaveLength(0);
  });

  it("still marks the anomalous zone, just without motion", () => {
    mockMotionPreference(true);
    const { container } = render(<FullPhotoOverlay photo={photo} onClose={() => undefined} />);
    // Акцент сохраняется статичным кольцом: сигнал не теряется.
    expect(container.querySelectorAll("circle[stroke-width='0.5']").length).toBeGreaterThan(0);
  });
});
