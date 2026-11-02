import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { Script } from 'node:vm';
import { createPreviewServer, publicFiles } from '../server.mjs';
import { normalizeApiBaseUrl, renderPublicConfig } from '../api-config.js';
import '../waitlist.js';

const root = new URL('../', import.meta.url);
const html = await readFile(new URL('index.html', root), 'utf8');
const css = await readFile(new URL('styles.css', root), 'utf8');
const waitlist = await readFile(new URL('waitlist.js', root), 'utf8');
new Script(await readFile(new URL('config.js', root), 'utf8'), { filename: 'config.js' });
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
assert.equal(new Set(ids).size, ids.length, 'IDs must be unique');
for (const [, target] of html.matchAll(/href="#([^"]+)"/g)) assert.ok(ids.includes(target), `Missing anchor ${target}`);
for (const [, label] of html.matchAll(/\bfor="([^"]+)"/g)) assert.ok(ids.includes(label), `Missing label control ${label}`);
assert.equal((html.match(/<section\b/g) ?? []).length, 7);
assert.equal((html.match(/class="pc"/g) ?? []).length, 5);
assert.equal((html.match(/class="f waitlist-form"/g) ?? []).length, 2);
assert.equal((html.match(/name="whatsapp"/g) ?? []).length, 2);
assert.equal((html.match(/name="name"/g) ?? []).length, 2);
assert.equal((html.match(/name="business_type"/g) ?? []).length, 2);
assert.equal((html.match(/class="waitlist-notice"/g) ?? []).length, 2);
assert.ok(!html.includes('type="checkbox"'));
assert.equal((html.match(/type="submit"/g) ?? []).length, 2);
assert.ok(!html.includes('Early-access concept · Features in development'));
assert.ok(html.includes('automated Google review requests and rebooking reminders'));
assert.ok(html.includes('class="ph"'));
assert.ok(html.includes('class="cy"'));
assert.ok(html.includes('class="gr"'));
assert.ok(html.includes('class="wf"'));
assert.ok(!html.includes('type="email"'));
assert.ok(!/Take-India|WITH TAKE|>Take</.test(html));
assert.ok(!/localStorage|sessionStorage|sendBeacon/.test(waitlist));
assert.ok(css.includes('prefers-reduced-motion'));
assert.ok(html.includes('<title>typein'));
assert.ok(html.includes('Bricolage+Grotesque'));
assert.ok(!html.includes('Sign-up is not available yet.'));
assert.ok(html.includes('privacy.html'));
assert.ok(html.includes('WhatsApp store for your business'));
assert.ok(!html.includes('Not affiliated with WhatsApp'));
const urls = [...html.matchAll(/(?:href|src)="([^"]+)"/g)].map((match) => match[1]);
for (const url of urls.filter((value) => !value.startsWith('#') && !value.startsWith('https://fonts.'))) {
  assert.ok(publicFiles.includes(url), `Unexpected resource ${url}`);
}
console.log('PASS HTML structure, anchors, cream-page sections, form fields, and integration boundaries.');

assert.equal(normalizeApiBaseUrl(''), '');
assert.equal(normalizeApiBaseUrl(' http://127.0.0.1:8000/api/v1/ '), 'http://127.0.0.1:8000/api/v1');
for (const url of ['https://user:password@example.invalid', 'https://example.invalid/?key=value', 'http://example.invalid', 'postgresql://example.invalid']) {
  assert.throws(() => renderPublicConfig(url));
}
const server = createPreviewServer({ apiBaseUrl: '' });
await new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', resolve);
});
try {
  const base = `http://127.0.0.1:${server.address().port}`;
  for (const filename of ['', ...publicFiles]) {
    const result = await fetch(`${base}/${filename}`);
    assert.equal(result.status, 200);
    assert.ok(result.headers.get('content-type'));
    assert.ok(result.headers.get('content-security-policy').includes("connect-src 'none'"));
    assert.ok((await result.text()).length > 0);
  }
  const head = await fetch(base, { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(await head.text(), '');
  for (const path of ['/api/waitlist', '/README.md', '/package.json', '/backend/.env', '/%2e%2e/backend/.env']) {
    assert.equal((await fetch(base + path)).status, 404);
  }
  assert.equal((await fetch(base, { method: 'POST', body: '{}' })).status, 405);
  console.log('PASS local HTTP assets, HEAD, missing routes, blocked submissions, and resource allowlist.');
} finally {
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}
console.log('These checks do not replace visual, keyboard or responsive browser testing.');
