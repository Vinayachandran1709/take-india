import { normalizeApiBaseUrl } from './api-config.js';

export function setupWaitlistForm(form, apiBaseUrl, request = fetch) {
  const business = form.elements.namedItem('business_type');
  const whatsapp = form.elements.namedItem('whatsapp');
  const consent = form.elements.namedItem('consent');
  const button = form.querySelector('button[type="submit"]');
  const status = form.querySelector('.wls');
  const fields = [business, whatsapp, consent, button];
  let submitting = false;
  let base;
  try { base = normalizeApiBaseUrl(apiBaseUrl); } catch { base = ''; }

  function message(text, state) {
    status.textContent = text;
    status.dataset.state = state;
  }
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submitting || !base) return;
    if (!form.reportValidity()) return;
    if (!consent.checked) {
      message('Please agree to WhatsApp early-access updates before joining.', 'error');
      return;
    }
    const payload = { business_type: business.value.trim(), whatsapp: whatsapp.value.trim(), consent: consent.checked };
    submitting = true;
    fields.forEach((field) => { field.disabled = true; });
    form.setAttribute('aria-busy', 'true');
    button.textContent = 'Joining…';
    message('Saving your request…', 'loading');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await request(`${base}/waitlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'omit',
        cache: 'no-store',
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!response.ok) {
        if (response.status === 400 || response.status === 422) {
          message('Check your business type and enter a valid Indian mobile number, with +91 if needed.', 'error');
        } else if (response.status === 429) {
          message('Too many attempts. Please wait a little before trying again.', 'error');
        } else {
          message('We couldn’t save your request. Please try again shortly. Your details are still here.', 'error');
        }
        return;
      }
      const result = await response.json();
      if (result?.accepted !== true) throw new Error('Registration was not acknowledged.');
      form.reset();
      message('You’re on the early-access list. Thank you for your interest in typein.', 'success');
      // Optional future analytics hook: waitlist_submitted, only after API acceptance.
    } catch {
      message('We couldn’t confirm your registration. Please try again; repeated requests won’t create another entry.', 'error');
    } finally {
      clearTimeout(timeout);
      submitting = false;
      fields.forEach((field) => { field.disabled = false; });
      form.setAttribute('aria-busy', 'false');
      button.textContent = 'Join the waitlist';
    }
  });

  fields.forEach((field) => { field.disabled = !base; });
  message('', base ? 'ready' : 'unavailable');
}

if (typeof document !== 'undefined') {
  document.querySelectorAll('.waitlist-form').forEach((form) => {
    setupWaitlistForm(form, window.TYPEIN_CONFIG?.apiBaseUrl ?? '');
  });
}
