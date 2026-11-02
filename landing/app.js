// The demo is entirely local. It creates no bookings, charges or messages.
const businessChoices = [...document.querySelectorAll('.chip')];
const businesses = [...document.querySelectorAll('.biz')];
const announcement = document.querySelector('#demo-status');

function selectSlot(business, slot) {
  business.querySelectorAll('.slot-option').forEach((button) => {
    button.setAttribute('aria-pressed', String(button === slot));
  });
  business.querySelectorAll('[data-slot-value]').forEach((value) => {
    value.textContent = slot.textContent;
  });
}

function showStep(business, step, moveFocus = true) {
  const screens = [...business.querySelectorAll('.scr')];
  screens.forEach((screen, index) => { screen.hidden = index !== step - 1; });
  if (step === 1) selectSlot(business, business.querySelector('.slot-option'));
  announcement.textContent = `${business.dataset.name}: ${screens[step - 1].getAttribute('aria-label')}. This is a sample preview.`;
  if (moveFocus) screens[step - 1].focus({ preventScroll: true });
  // Optional future analytics hook: demo_step_advanced (business, step).
}

businessChoices.forEach((choice, index) => {
  choice.disabled = false;
  choice.addEventListener('change', () => {
    if (!choice.checked) return;
    businesses.forEach((business, businessIndex) => {
      business.hidden = businessIndex !== index;
    });
    showStep(businesses[index], 1, false);
    // Optional future analytics hook: demo_business_selected (business).
  });
});

businesses.forEach((business) => {
  business.querySelectorAll('.demo-step-button').forEach((button) => {
    button.disabled = false;
    button.addEventListener('click', () => {
      showStep(business, Number(button.dataset.step));
    });
  });
  business.querySelectorAll('.slot-option').forEach((slot) => {
    slot.disabled = false;
    slot.addEventListener('click', () => selectSlot(business, slot));
  });
});

const menu = document.querySelector('.mobile-menu');
const navigation = document.querySelector('#primary-navigation');
function closeMenu(returnFocus = false) {
  menu.setAttribute('aria-expanded', 'false');
  navigation.classList.remove('is-open');
  menu.textContent = 'Menu';
  if (returnFocus) menu.focus();
}
menu.addEventListener('click', () => {
  const open = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(open));
  navigation.classList.toggle('is-open', open);
  menu.textContent = open ? 'Close' : 'Menu';
});
navigation.querySelectorAll('a').forEach((link) => {
  link.addEventListener('click', () => {
    closeMenu();
    document.querySelector(link.hash)?.focus({ preventScroll: true });
  });
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') closeMenu(true);
});
document.addEventListener('click', (event) => {
  if (!event.target.closest('.site-header')) closeMenu();
});
window.matchMedia('(max-width: 700px)').addEventListener?.('change', () => closeMenu());

// Enable the compact navigation only after its handlers are ready.
document.documentElement.classList.add('js');
// Waitlist submission is handled separately by waitlist.js.
