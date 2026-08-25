import { afterEach, describe, expect, it, vi } from 'vitest';

import { requestJson } from './api';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('typed API request layer', () => {
  it('keeps relative paths, adds JSON accept and returns the source payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ schema: 'deeputin-api-v1.0', source_mode: 'research' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const payload = await requestJson<{ schema: string }>('/api/v1/health', {
      headers: { 'X-Request-Context': 'test' },
    });

    expect(payload.schema).toBe('deeputin-api-v1.0');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/health', expect.anything());
    const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = requestInit.headers as Headers;
    expect(headers.get('accept')).toBe('application/json');
    expect(headers.get('x-request-context')).toBe('test');
  });

  it('preserves explicit API error detail and status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Photo is not present in Stage 1.' }), {
          status: 404,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    );

    await expect(requestJson('/api/v1/photos/missing')).rejects.toEqual(
      expect.objectContaining({
        status: 404,
        detail: 'Photo is not present in Stage 1.',
      }),
    );
  });

  it('does not manufacture a payload for a successful empty response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(null, {
          status: 204,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    );

    await expect(requestJson('/api/v1/reviews')).resolves.toBeNull();
  });
});
