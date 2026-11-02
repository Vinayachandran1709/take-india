import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { normalizeApiBaseUrl, renderPublicConfig } from './api-config.js';

export const publicFiles = [
  'index.html', 'privacy.html', 'styles.css', 'favicon.svg', 'config.js', 'api-config.js', 'waitlist.js',
];
const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
};

export function createPreviewServer({ apiBaseUrl = process.env.TYPEIN_API_BASE_URL ?? '' } = {}) {
  const base = normalizeApiBaseUrl(apiBaseUrl);
  const connectionSource = base ? new URL(base).origin : "'none'";
  return createServer(async (request, response) => {
    const headers = {
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer',
      'Cache-Control': 'no-store',
      'Content-Security-Policy': `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self'; connect-src ${connectionSource}; form-action 'none'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'`,
    };
    if (!['GET', 'HEAD'].includes(request.method)) {
      response.writeHead(405, { ...headers, Allow: 'GET, HEAD' });
      response.end('Method not allowed');
      return;
    }
    let pathname;
    try {
      pathname = new URL(request.url, 'http://localhost').pathname;
    } catch {
      response.writeHead(400, headers);
      response.end('Bad request');
      return;
    }
    const filename = pathname === '/' ? 'index.html' : pathname.slice(1);
    if (!publicFiles.includes(filename)) {
      response.writeHead(404, headers);
      response.end('Not found');
      return;
    }
    try {
      const body = filename === 'config.js'
        ? renderPublicConfig(base)
        : await readFile(new URL(filename, import.meta.url));
      const extension = filename.slice(filename.lastIndexOf('.'));
      response.writeHead(200, { ...headers, 'Content-Type': contentTypes[extension] });
      response.end(request.method === 'HEAD' ? undefined : body);
    } catch {
      response.writeHead(500, headers);
      response.end('Unable to load this page');
    }
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const port = Number(process.argv[2] ?? 4173);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('Use a port number between 1 and 65535.');
  }
  const server = createPreviewServer();
  server.on('error', (error) => {
    console.error(error.code === 'EADDRINUSE' ? `Port ${port} is in use. Try node server.mjs 4174.` : 'The preview server could not start.');
    process.exitCode = 1;
  });
  server.listen(port, '127.0.0.1', () => console.log(`typein preview: http://127.0.0.1:${port}`));
}
