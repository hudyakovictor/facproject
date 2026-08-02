import { describe, expect, it, vi, afterEach } from "vitest";
import { loadTimeline } from "../api";

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
  vi.restoreAllMocks();
});

function mockFetchOnce(body: unknown, ok = true, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok, status,
    json: () => Promise.resolve(body),
  }) as unknown as typeof fetch;
}

describe("loadTimeline", () => {
  it("labels a valid array payload as research mode", async () => {
    const rows = [{ id: "P1", date: "1999-01-01", t: 0, era: "E", bucket: "frontal", quality: 1, boneScore: 1, p0: 1, p1: 0, p2: 0 }];
    mockFetchOnce(rows);
    const result = await loadTimeline();
    expect(result.mode).toBe("research");
    expect(result.photos).toHaveLength(1);
  });

  it("labels an object payload with source_mode=demo correctly", async () => {
    const body = {
      source_mode: "demo",
      note: "synthetic",
      photos: [{ id: "P1", date: "1999-01-01", t: 0, era: "E", bucket: "frontal", quality: 1, boneScore: 1, p0: 1, p1: 0, p2: 0 }],
    };
    mockFetchOnce(body);
    const result = await loadTimeline();
    expect(result.mode).toBe("demo");
    expect(result.message).toContain("synthetic");
  });

  it("falls back to the bundled demo dataset on network failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network down")) as unknown as typeof fetch;
    const result = await loadTimeline();
    expect(result.mode).toBe("demo");
    expect(result.photos.length).toBeGreaterThan(0);
    expect(result.message).toContain("network down");
  });

  it("falls back to demo when the API returns no valid rows", async () => {
    mockFetchOnce({ photos: [{ garbage: true }] });
    const result = await loadTimeline();
    expect(result.mode).toBe("demo");
  });

  it("falls back to demo on non-2xx HTTP status", async () => {
    mockFetchOnce({}, false, 500);
    const result = await loadTimeline();
    expect(result.mode).toBe("demo");
    expect(result.message).toContain("500");
  });
});
