import type { Plugin, ProxyOptions } from 'vite';
import { realpathSync } from 'node:fs';

// The test runner supplies a separate loopback port and fresh data roots.
// Production always uses the existing 8770 owner; arbitrary upstream URLs are not accepted.
export function localIntegration(backendPort = 8770): Plugin {
  if (!Number.isSafeInteger(backendPort) || backendPort < 1024 || backendPort > 65535) {
    throw new Error('invalid_local_backend_port');
  }
  const target = `http://127.0.0.1:${backendPort}`;
  const prefixes = ['/api/research', '/api/workspace', '/intel'];
  const proxy: Record<string, ProxyOptions> = Object.fromEntries(prefixes.map((prefix) => [prefix, {
    target,
    changeOrigin: true,
    headers: { origin: target },
  }]));
  return {
    name: 'catos-local-integration',
    config: () => ({ server: { proxy } }),
    configureServer(server) {
      const frontendOrigin = `http://127.0.0.1:${server.config.server.port}`;
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? '').split('?')[0];
        const isIdentity = url === '/__catos/frontend';
        if (!isIdentity && !prefixes.some((p) => url === p || url.startsWith(`${p}/`))) {
          next();
          return;
        }
        // Validate BEFORE the proxy rewrites Host/Origin for the backend's same-origin guard.
        if (req.headers.host !== frontendOrigin.slice(7) ||
            (req.headers.origin !== undefined && req.headers.origin !== frontendOrigin)) {
          res.writeHead(403, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
          res.end(JSON.stringify({ detail: 'frontend_origin_mismatch' }));
          return;
        }
        if (isIdentity) {
          res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
          res.end(JSON.stringify({ contract: 'catos.frontend.v1', root: realpathSync(server.config.root) }));
          return;
        }
        next();
      });
    },
  };
}
