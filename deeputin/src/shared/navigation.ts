import type { PageId } from './contracts';

export function hashParam(key: string): string {
  if (typeof window === 'undefined') return '';
  const query = window.location.hash.split('?')[1] ?? '';
  return new URLSearchParams(query).get(key) ?? '';
}

export function navigateTo(pageId: PageId, params: Record<string, string | undefined> = {}) {
  if (typeof window === 'undefined') return;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString() ? `?${query.toString()}` : '';
  window.location.hash = `#/${pageId}${suffix}`;
}
