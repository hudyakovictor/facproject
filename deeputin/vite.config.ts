import { createReadStream } from 'node:fs';
import { promises as fs } from 'node:fs';
import { extname, relative, resolve, sep } from 'node:path';
import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin, type ViteDevServer } from 'vite';

const apiProxyTarget = process.env.DEEPUTIN_API_PROXY ?? 'http://127.0.0.1:8000';
const uiArtifactsRoot = resolve(
  process.env.DEEPUTIN_UI_ARTIFACTS_ROOT ?? '/Volumes/SDCARD/storage/ui_artifacts',
);
const uiArtifactsPrefix = '/api/v1/ui_artifacts/';
const allowedUiArtifactPath =
  /^(?:timeline_matrix\.json|pair_metrics_preview\.csv|zone_summary\.csv|report_meta\.json|report_sections\/(?:summary|narrative|timelines|change_points|zones|motion_maps)\.json)$/;

function sendJson(
  res: {
    statusCode: number;
    setHeader: (name: string, value: string) => void;
    end: (body: string) => void;
  },
  status: number,
  body: Record<string, unknown>,
) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(JSON.stringify(body));
}

async function serveUiArtifact(
  req: { method?: string; url?: string },
  res: {
    statusCode: number;
    setHeader: (name: string, value: string) => void;
    end: (body?: string) => void;
  },
  next: () => void,
): Promise<void> {
  const requestUrl = req.url ?? '';
  if (!requestUrl.startsWith(uiArtifactsPrefix)) {
    next();
    return;
  }

  if (req.method !== 'GET' && req.method !== 'HEAD') {
    sendJson(res, 405, {
      schema: 'deeputin-ui-artifact-error-v1',
      source_mode: 'research',
      not_a_verdict: true,
      detail: 'UI artifacts are read-only.',
    });
    return;
  }

  const rawPath = requestUrl.slice(uiArtifactsPrefix.length).split('?')[0];
  let artifactPath: string;
  try {
    artifactPath = decodeURIComponent(rawPath);
  } catch {
    sendJson(res, 400, {
      schema: 'deeputin-ui-artifact-error-v1',
      source_mode: 'research',
      not_a_verdict: true,
      detail: 'The UI artifact path is not valid URL encoding.',
    });
    return;
  }

  if (!allowedUiArtifactPath.test(artifactPath)) {
    sendJson(res, 400, {
      schema: 'deeputin-ui-artifact-error-v1',
      source_mode: 'research',
      not_a_verdict: true,
      detail: 'The requested file is not part of the lightweight UI-artifact contract.',
    });
    return;
  }

  let rootStat;
  try {
    rootStat = await fs.stat(uiArtifactsRoot);
  } catch {
    // A deployed API may expose the same relative route. Let Vite's proxy handle it
    // when the local removable-card mount is not present.
    next();
    return;
  }
  if (!rootStat.isDirectory()) {
    next();
    return;
  }

  const artifactFile = resolve(uiArtifactsRoot, artifactPath);
  const relativePath = relative(uiArtifactsRoot, artifactFile);
  if (relativePath.startsWith(`..${sep}`) || relativePath === '..') {
    sendJson(res, 400, {
      schema: 'deeputin-ui-artifact-error-v1',
      source_mode: 'research',
      not_a_verdict: true,
      detail: 'The UI artifact path leaves the configured artifact root.',
    });
    return;
  }

  let stat;
  try {
    stat = await fs.stat(artifactFile);
  } catch {
    sendJson(res, 404, {
      schema: 'deeputin-ui-artifact-error-v1',
      source_mode: 'research',
      not_a_verdict: true,
      detail: `UI artifact is missing: ${artifactPath}. Run scripts/prepare_ui_data.py after the pipeline run.`,
    });
    return;
  }
  if (!stat.isFile()) {
    sendJson(res, 404, {
      schema: 'deeputin-ui-artifact-error-v1',
      source_mode: 'research',
      not_a_verdict: true,
      detail: `UI artifact is not a file: ${artifactPath}.`,
    });
    return;
  }

  const contentType =
    extname(artifactFile) === '.csv'
      ? 'text/csv; charset=utf-8'
      : 'application/json; charset=utf-8';
  res.statusCode = 200;
  res.setHeader('Content-Type', contentType);
  res.setHeader('Content-Length', String(stat.size));
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'HEAD') {
    res.end();
    return;
  }

  await new Promise<void>((resolveStream, rejectStream) => {
    const stream = createReadStream(artifactFile);
    stream.on('error', rejectStream);
    stream.on('end', resolveStream);
    stream.pipe(res as never);
  }).catch(() => {
    if (!res.statusCode || res.statusCode < 400) {
      sendJson(res, 500, {
        schema: 'deeputin-ui-artifact-error-v1',
        source_mode: 'research',
        not_a_verdict: true,
        detail: 'The UI artifact could not be read.',
      });
    }
  });
}

function uiArtifactsPlugin(): Plugin {
  return {
    name: 'deeputin-ui-artifacts',
    configureServer(server: ViteDevServer) {
      server.middlewares.use((req, res, next) => {
        void serveUiArtifact(req, res, next);
      });
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        void serveUiArtifact(req, res, next);
      });
    },
  };
}

export default defineConfig({
  plugins: [uiArtifactsPlugin(), react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
