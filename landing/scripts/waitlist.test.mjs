import assert from 'node:assert/strict';
import { test } from 'node:test';
import { setupWaitlistForm } from '../waitlist.js';
import { normalizeApiBaseUrl, renderPublicConfig } from '../api-config.js';
import { createPreviewServer } from '../server.mjs';

// Minimal form interface for controller tests; not a simulated visual browser.
function formFixture() {
  const business = { value: 'Salon & hair studio', disabled: true };
  const whatsapp = { value: ' 9876543210 ', disabled: true };
  const consent = { checked: true, disabled: true };
  const button = { textContent: 'Join the waitlist', disabled: true };
  const status = { textContent: '', dataset: {} };
  const fields = { business_type: business, whatsapp, consent };
  const attributes = {};
  const handlers = {};
  return {
    business, whatsapp, consent, button, status, attributes,
    elements: { namedItem: (name) => fields[name] },
    querySelector: (selector) => selector === '.wls' ? status : button,
    addEventListener: (name, handler) => { handlers[name] = handler; },
    setAttribute: (name, value) => { attributes[name] = value; },
    reportValidity: () => true,
    reset() { this.resetCount = (this.resetCount ?? 0) + 1; whatsapp.value = ''; consent.checked = false; },
    submit: () => handlers.submit({ preventDefault() {} }),
  };
}

const api = 'https://api.example.invalid/api/v1';
const accepted = { ok: true, status: 200, json: async () => ({ accepted: true }) };

test('both forms use the same endpoint, payload, and explicit acceptance contract', async () => {
  const calls = [];
  for (let index = 0; index < 2; index++) {
    const form = formFixture();
    setupWaitlistForm(form, api, async (...args) => { calls.push(args); return accepted; });
    await form.submit();
    assert.equal(form.status.dataset.state, 'success');
    assert.equal(form.resetCount, 1);
    assert.equal(form.button.disabled, false);
  }
  assert.equal(calls.length, 2);
  for (const [url, options] of calls) {
    assert.equal(url, `${api}/waitlist`);
    assert.equal(options.credentials, 'omit');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { business_type: 'Salon & hair studio', whatsapp: '9876543210', consent: true });
  }
});

test('in-flight requests lock controls and ignore accidental repeat submissions', async () => {
  const form = formFixture();
  let finish;
  let calls = 0;
  setupWaitlistForm(form, api, () => { calls++; return new Promise((resolve) => { finish = resolve; }); });
  const pending = form.submit();
  assert.equal(form.status.dataset.state, 'loading');
  assert.equal(form.attributes['aria-busy'], 'true');
  assert.equal(form.whatsapp.disabled, true);
  await form.submit();
  assert.equal(calls, 1);
  finish(accepted);
  await pending;
  assert.equal(form.attributes['aria-busy'], 'false');
});

test('unchecked consent never sends a request', async () => {
  const form = formFixture();
  form.consent.checked = false;
  let called = false;
  setupWaitlistForm(form, api, async () => { called = true; return accepted; });
  await form.submit();
  assert.equal(called, false);
  assert.equal(form.status.dataset.state, 'error');
});

for (const statusCode of [400, 413, 422, 429, 500, 503]) {
  test(`HTTP ${statusCode} retains entered values and never shows success`, async () => {
    const form = formFixture();
    setupWaitlistForm(form, api, async () => ({ ok: false, status: statusCode }));
    await form.submit();
    assert.equal(form.status.dataset.state, 'error');
    assert.equal(form.whatsapp.value, ' 9876543210 ');
    assert.equal(form.resetCount, undefined);
    assert.equal(form.button.disabled, false);
  });
}

for (const [name, request] of [
  ['network failure', async () => { throw new Error('internal network details'); }],
  ['invalid JSON', async () => ({ ok: true, json: async () => { throw new Error('bad JSON'); } })],
  ['unacknowledged 2xx', async () => ({ ok: true, json: async () => ({ accepted: false }) })],
]) {
  test(`${name} is not registration success`, async () => {
    const form = formFixture();
    setupWaitlistForm(form, api, request);
    await form.submit();
    assert.equal(form.status.dataset.state, 'error');
    assert.equal(form.whatsapp.value, ' 9876543210 ');
    assert.equal(form.button.disabled, false);
    assert.ok(!form.status.textContent.includes('internal'));
  });
}

test('missing or unsafe configuration keeps forms unavailable and makes no request', async () => {
  for (const base of ['', 'not-a-url', 'https://user:password@example.invalid']) {
    const form = formFixture();
    let called = false;
    setupWaitlistForm(form, base, async () => { called = true; return accepted; });
    await form.submit();
    assert.equal(called, false);
    assert.equal(form.status.dataset.state, 'unavailable');
    assert.equal(form.whatsapp.disabled, true);
    assert.equal(form.button.disabled, true);
  }
});

test('public configuration accepts HTTPS and loopback HTTP only without URL credentials', () => {
  assert.equal(normalizeApiBaseUrl(`${api}/`), api);
  assert.equal(normalizeApiBaseUrl('http://localhost:8000/api/v1'), 'http://localhost:8000/api/v1');
  assert.ok(renderPublicConfig(api).includes(api));
  for (const value of ['javascript:alert(1)', 'http://api.example.invalid', `${api}?secret=x`, `${api}#token`, 'postgresql://localhost']) {
    assert.throws(() => renderPublicConfig(value));
  }
});

test('local preview emits only the configured public API origin in connect-src', async () => {
  const server = createPreviewServer({ apiBaseUrl: api });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}/config.js`);
    assert.equal(response.status, 200);
    assert.ok(response.headers.get('content-security-policy').includes('connect-src https://api.example.invalid;'));
    assert.equal(await response.text(), renderPublicConfig(api));
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
