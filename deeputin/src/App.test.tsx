import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('DEEPUTIN blueprint shell', () => {
  it('starts with an empty Timeline and exposes the shared block contract', () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: 'Timeline', level: 1 })).toBeVisible();
    expect(screen.getByText('ON-DEMAND DATA')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Archive explorer', level: 3 })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Load calculated data' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Load timeline artifacts' })).toBeVisible();
    expect(screen.getByText('No observations to plot')).toBeVisible();
    expect(within(screen.getByRole('navigation')).getAllByRole('button')).toHaveLength(7);
    const navigation = within(screen.getByRole('navigation'));
    for (const label of [
      'Timeline',
      'Photo Detail',
      'Compare',
      'Research',
      'Methodology',
      'Report',
      'Publications',
    ]) {
      expect(navigation.getByRole('button', { name: label })).toBeVisible();
    }
    expect(screen.queryByRole('button', { name: 'Morphing' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Upload' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Timeline' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByText('Block / timeline.archive-explorer')).toBeVisible();
  });

  it('renders the owned detail blocks across all seven pages', async () => {
    const user = userEvent.setup();
    render(<App />);

    const pageChecks = [
      ['Photo Detail', 'Photo overview and artifact viewer'],
      ['Compare', 'Pair Detail and data-first analysis'],
      ['Research', 'Zone Atlas and spatial research'],
      ['Methodology', 'Pipeline, archive quality and gates'],
      ['Report', 'Run Summary and working evidence'],
      ['Publications', 'Authoring workspace'],
    ] as const;

    const navigation = within(screen.getByRole('navigation'));
    for (const [page, block] of pageChecks) {
      await user.click(navigation.getByRole('button', { name: page }));
      expect(screen.getByRole('heading', { name: block, level: 3 })).toBeVisible();
    }
  });

  it('restores selected context from a deep link without adding a route', () => {
    const previousUrl = window.location.href;
    window.history.replaceState(null, '', '#/photo-detail?photo_id=linked-photo');

    render(<App />);

    expect(screen.getByRole('heading', { name: 'Photo Detail', level: 1 })).toBeVisible();
    expect(screen.getAllByDisplayValue('linked-photo')).toHaveLength(3);

    window.history.replaceState(null, '', previousUrl);
  });

  it('restores Compare visual mode from the route context', () => {
    const previousUrl = window.location.href;
    window.history.replaceState(
      null,
      '',
      '#/compare?photo_a=returned-a&photo_b=returned-b&visual_mode=mesh_3d',
    );

    render(<App />);

    expect(screen.getByRole('heading', { name: 'Compare', level: 1 })).toBeVisible();
    expect(screen.getByLabelText('View mode')).toHaveValue('mesh_3d');
    expect(screen.getAllByDisplayValue('returned-a')).toHaveLength(3);
    expect(screen.getAllByDisplayValue('returned-b')).toHaveLength(3);

    window.history.replaceState(null, '', previousUrl);
  });

  it('keeps API failures visible inside the owning block', async () => {
    const previousUrl = window.location.href;
    window.history.replaceState(null, '', '#/timeline');
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('network down'));
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Load calculated data' }));

    await waitFor(() => {
      expect(
        screen.getByText(
          'Не удалось соединиться с API. Проверьте доступность рассчитанного источника.',
        ),
      ).toBeVisible();
    });
    expect(screen.getByText('Source unavailable')).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/photos?offset=0&limit=200', expect.any(Object));
    window.history.replaceState(null, '', previousUrl);
  });

  it('keeps page-level navigation independent from block implementation', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Publications' }));

    expect(screen.getByRole('heading', { name: 'Publications', level: 1 })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Publications' })).toHaveAttribute(
      'aria-current',
      'page',
    );

    const evidenceBlock = screen.getByText('Block / publications.evidence-map').closest('section');
    expect(evidenceBlock).not.toBeNull();

    await user.click(
      within(evidenceBlock as HTMLElement).getByText('Source files and API endpoints'),
    );

    expect(
      within(evidenceBlock as HTMLElement).getByText(
        'ui_artifacts/report_sections/change_points.json',
      ),
    ).toBeVisible();
  });
});
