import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { access, writeFile } from 'node:fs/promises';

// One-time conversion of the supplied design component into ordinary static HTML.
const archive = process.argv[2];
assert.ok(archive, 'Pass the attached ZIP path.');
const raw = execFileSync('tar', ['-xOf', archive, 'B-Cream.dc.html'], {
  encoding: 'utf8',
  maxBuffer: 1024 * 1024,
});
const css = raw.match(/<style>([\s\S]*?)<\/style>/)?.[1];
const start = raw.indexOf('<div class="p B">');
const end = raw.indexOf('</x-dc>');
assert.ok(css && start >= 0 && end > start, 'Reference structure changed.');
let page = raw.slice(start, end).trim();

const businessOptions = [
  'Salon &amp; hair studio',
  'Makeup, lash &amp; nail artist',
  'Custom baker',
  'Aesthetic or dental clinic',
  'Yoga, dance or fitness studio',
  'Other',
].map((name) => `<option>${name}</option>`).join('');

function waitlistForm(id, suffix) {
  return `<form class="f waitlist-form" id="${id}" method="post" aria-label="Join the typein early-access waitlist">
  <label class="vh" for="business-${suffix}">Business type</label>
  <select id="business-${suffix}" name="business_type" required disabled aria-describedby="waitlist-status-${suffix}">${businessOptions}</select>
  <label class="vh" for="phone-${suffix}">WhatsApp number</label>
  <input id="phone-${suffix}" name="whatsapp" type="tel" inputmode="tel" autocomplete="tel" required minlength="10" maxlength="32" placeholder="Your WhatsApp number" disabled aria-describedby="waitlist-status-${suffix}">
  <button type="submit" disabled>Join the waitlist</button>
  <p class="wls" id="waitlist-status-${suffix}" role="status" aria-live="polite" aria-atomic="true"></p>
</form>`;
}

page = page.replace(/<form class="f" id="joinF">[\s\S]*?<\/form>/, waitlistForm('joinF', 'hero'));
page = page.replace(/<form class="f" id="joinF2">[\s\S]*?<\/form>/, waitlistForm('joinF2', 'footer'));
assert.equal((page.match(/class="f waitlist-form"/g) ?? []).length, 2);
page = page.replace('<div class="cta" id="joinF2">', '<div class="cta" id="join">');
page = page.replace('<span class="lg">typein<i>.</i></span>', '<a class="lg" href="#top" aria-label="typein home">typein<i>.</i></a>');
page = page.replace('</header><section class="hero">', '</header><main id="main-content"><section class="hero" id="top" aria-labelledby="hero-title">');
page = page.replace('<h1>Bookings by phone and DM?', '<h1 id="hero-title">Bookings by phone and DM?');
page = page.replace('<footer class="w ft">', '</main><footer class="w ft">');

// Preserve the visual hierarchy and copy where truthful; clarify previews and planned features.
const copy = [
  ['A WhatsApp store for service businesses with no website. Customers book, pay and rebook right where they already chat.',
    "A WhatsApp-first store for service businesses. We're building it so customers can book, pay and rebook through WhatsApp, with automated Google review requests and rebooking reminders."],
  ['Five daily headaches. Gone.', 'Five daily headaches. One planned workflow.'],
  ['Your WhatsApp store takes the booking', 'A shareable booking page helps take the booking'],
  ['Replies and bookings run on their own', 'Planned: faster replies and booking'],
  ['Payments confirmed automatically', 'Planned: verified advance payments'],
  ['Customers pick a new slot themselves', 'Planned: self-serve rescheduling'],
  ['Gentle nudges bring them back', 'Planned: gentle rebooking nudges'],
  ['Like a caring front desk', 'Planned follow-up journey'],
  ['Your whole front desk, automated.', 'Your future front desk, in one place.'],
  ['Everything in the chat', 'Concept features for feedback'],
  ['Services and classes, open in chat', 'Services and classes on a shareable page'],
  ['New enquiries get booked, no typing', 'Planned: faster enquiry replies'],
  ['No more payment screenshots', 'Planned: verified advance payments'],
  ['Customers move their own slot', 'Planned: self-serve rescheduling'],
  ['Comment or DM, straight to booking', 'Planned: a path from DM to booking'],
  ['Profile visitors land in your chat', 'Planned: a link from Google profile'],
  ['Requested after every visit', 'Planned: post-visit review requests'],
  ['Rebooking reminders on autopilot', 'Planned: rebooking reminders'],
  ['Check-ins tracked for every class', 'Planned: class attendance'],
  ['Memberships tracked and nudged', 'Planned: renewal support'],
  ['Your store is the booking page', 'A shareable business and booking page'],
  ['Tune flows to your business', 'Planned: settings for each business'],
  ['<p style="margin-top:14px;color:#C9CDE3;font-size:13px">Free early access · No website needed</p>', ''],
  ['Early-access concept · Not affiliated with WhatsApp, Meta or Google', 'WhatsApp store for your business'],
];
for (const [from, to] of copy) {
  assert.ok(page.includes(from), `Reference copy missing: ${from}`);
  page = page.replace(from, to);
}

const document = `<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>typein — A booking page for businesses on WhatsApp</title>
  <meta name="description" content="Explore typein, a planned WhatsApp-first booking experience for local service businesses. Join the early-access list for updates.">
  <meta property="og:title" content="typein — A booking page for businesses on WhatsApp">
  <meta property="og:description" content="Meet typein and join the early-access list.">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="typein — A booking page for businesses on WhatsApp">
  <meta name="twitter:description" content="Meet typein and join the early-access list.">
  <!-- Add canonical, og:url, and a real og:image after the public domain and asset are approved. -->
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;600;700&amp;display=swap">
  <link rel="stylesheet" href="styles.css">
  <script src="config.js"></script>
  <script type="module" src="waitlist.js"></script>
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to content</a>
  ${page.replace(/></g, '>\n<')}
</body>
</html>
`;

const additions = `
html { scroll-behavior: smooth; }
body { margin: 0; background: #FFF7E8; }
.p { min-height: 100vh; }
.p .lg { color: #14142B; text-decoration: none; }
.p .f { max-width: 760px; align-items: stretch; }
.p .f select { flex: 1; min-width: 190px; min-height: 52px; border-radius: 10px; border: 1px solid var(--l); background: #fff; padding: 0 16px; font: inherit; font-size: 16px; color: #0B1030; }
.p .f input { min-width: 205px; }
.p .f .wls { flex-basis: 100%; margin: 0; font-size: 13px; text-align: center; }
.p .f .wls { min-height: 20px; color: #55557A; }
.p .f .wls:empty { display: none; }
.p .f .wls[data-state="error"] { color: #9B1C1C; }
.p .f .wls[data-state="success"] { color: #145438; }
.p .cta .f .wls { color: #E4E9FF; }
.p .cta .f .wls[data-state="error"] { color: #FFD3D3; }
.p .cta .f .wls[data-state="success"] { color: #A9F0C8; }
.p .f button:disabled, .p .f select:disabled, .p .f input:disabled { cursor: not-allowed; opacity: .72; }
.p .f select:disabled, .p .f input:disabled { background: #fff; color: #55557A; opacity: 1; }
.p .f input:disabled::placeholder { color: #55557A; opacity: 1; }
.p .f button:not(:disabled):hover, .p .bt:hover { filter: brightness(.88); }
.p a:focus-visible, .p button:focus-visible, .p input:focus-visible, .p select:focus-visible, .skip-link:focus-visible { outline: 3px solid #1F3DFF; outline-offset: 3px; }
.skip-link { position: fixed; top: 8px; left: 8px; z-index: 100; transform: translateY(-150%); padding: 10px 14px; border-radius: 8px; background: #fff; color: #14142B; }
.skip-link:focus { transform: translateY(0); }
.p .ph { width: min(300px, 100%); }
.p .cta { overflow: hidden; }
@media (max-width: 700px) { .p .f { max-width: 470px; } .p .f select, .p .f input, .p .f button { flex-basis: 100%; width: 100%; } .p .hd { height: auto; min-height: 80px; gap: 12px; } }
@media (max-width: 420px) { .p .w { padding-left: 20px; padding-right: 20px; } .p .sec { padding-left: 20px; padding-right: 20px; } .p .hero { padding-left: 20px; padding-right: 20px; } .p .cta { padding: 44px 20px; } .p .ph { max-width: 100%; } }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; } }
`;
for (const filename of ['index.html', 'styles.css']) {
  const target = new URL(`../${filename}`, import.meta.url);
  await access(target).then(
    () => { throw new Error(`Refusing to overwrite existing ${filename}.`); },
    (error) => { if (error?.code !== 'ENOENT') throw error; },
  );
}
await writeFile(new URL('../index.html', import.meta.url), document);
await writeFile(new URL('../styles.css', import.meta.url), css.replace(/}/g, '}\n') + additions);
console.log('Converted the cream reference into static landing HTML and CSS.');
