// This setting is public. Never put credentials, tokens or database URLs here.
export function normalizeApiBaseUrl(value = '') {
  if (typeof value !== 'string') throw new Error('Invalid public API URL.');
  const raw = value.trim();
  if (!raw) return '';
  let url;
  try { url = new URL(raw); } catch { throw new Error('Invalid public API URL.'); }
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash ||
      (url.protocol !== 'https:' && !(url.protocol === 'http:' && local))) {
    throw new Error('Use a public HTTPS API URL, or local HTTP, without credentials, query or fragment.');
  }
  return url.href.replace(/\/+$/, '');
}

export function renderPublicConfig(value) {
  const config = JSON.stringify({ apiBaseUrl: normalizeApiBaseUrl(value) }).replace(/</g, '\\u003c');
  return `window.TYPEIN_CONFIG = Object.freeze(${config});\n`;
}
