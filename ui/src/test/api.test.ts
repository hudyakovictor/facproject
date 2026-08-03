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
    text: () => Promise.resolve(JSON.stringify(body)),
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

  it("rejects a non-research object payload", async () => {
    const body = {
      source_mode: "demo",
      note: "synthetic",
      photos: [{ id: "P1", date: "1999-01-01", t: 0, era: "E", bucket: "frontal", quality: 1, boneScore: 1, p0: 1, p1: 0, p2: 0 }],
    };
    mockFetchOnce(body);
    await expect(loadTimeline()).rejects.toThrow("Non-research timeline rejected");
  });

  it("propagates a network failure instead of fabricating evidence", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network down")) as unknown as typeof fetch;
    await expect(loadTimeline()).rejects.toThrow("network down");
  });

  it("rejects a research payload with no valid rows", async () => {
    mockFetchOnce({ source_mode: "research", photos: [{ garbage: true }] });
    await expect(loadTimeline()).rejects.toThrow("no valid photo rows");
  });

  it("rejects a non-2xx response", async () => {
    mockFetchOnce({ detail: "failure" }, false, 500);
    await expect(loadTimeline()).rejects.toThrow("HTTP 500");
  });
});
