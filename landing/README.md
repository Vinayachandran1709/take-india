# typein cream landing page

An independent static page adapted from the supplied **B · Cream** HTML mockup. The repository is named take-india; the public product name is **typein**.

## Run locally (Windows Command Prompt)

Requires Node.js 20 or newer. There are no package dependencies and no installation step.

```cmd
cd /d "C:\Github folder\take-india\landing"
node server.mjs
```

Open http://127.0.0.1:4173/. Stop with Ctrl+C. If the port is in use, run `node server.mjs 4174`.

Without an API URL, both forms remain unavailable and no submission is sent. To connect a separately running **development** backend:

```cmd
cd /d "C:\Github folder\take-india\landing"
set "TYPEIN_API_BASE_URL=http://127.0.0.1:8000/api/v1"
node server.mjs
```

The backend must allow `http://127.0.0.1:4173` in `CORS_ORIGINS` while retaining its other origins. Its selected development database must contain `waitlist_entries`. See [backend/docs/waitlist.md](../backend/docs/waitlist.md) before testing real entries. Never point this local test at production or staging.

`TYPEIN_API_BASE_URL` is public browser configuration. It must end in `/api/v1`. Use public HTTPS in deployment; local loopback HTTP is allowed for development. Never put credentials, database URLs, or tokens in this variable. The server does not load `.env` files.

## Check and build

Run from `landing/`:

```cmd
node scripts\check.mjs
node scripts\waitlist.test.mjs
node scripts\build.mjs
```

The static build writes six public assets to `dist/`. Configure `TYPEIN_API_BASE_URL` **before** building; changing it requires a rebuild. The old `app.js` from the earlier interactive demo is retained in the source folder but is no longer served or built. `scripts/convert-reference.mjs` records the one-time ZIP conversion and refuses to overwrite the finished page.

## Design and behavior

The page follows the supplied mockup's section order and visual system: cream background, electric-blue accent, navy type, Bricolage Grotesque, centered hero, floating badges around the phone, source strip, five problem cards, six-step follow-up journey, feature grid, eight audience cards, and dark lower call to action. Its inline icon paths and phone artwork come from the reference.

The reference had email-only forms. At the user's choice, both forms collect name, business type and Indian WhatsApp number, with no email or checkbox. A short line beside each form explains WhatsApp early-access contact and links to privacy information. Both submit to `POST /api/v1/waitlist` through the existing `waitlist.js`. They show loading, success only after `{ "accepted": true }`, and recoverable errors without clearing values. A missing API URL keeps both forms disabled without showing an initial status line. The visual phone flow is an illustration; it does not book, charge, message, or save anything.

Some reference copy described live payments, WhatsApp automation, reviews, rebooking, and other features that are not operational. The hero now describes what typein is building, and the feature sections mark unfinished work as planned. It makes no price promise. The linked `privacy.html` describes only the waitlist. No analytics tracker was added.

The page has semantic headings, labels, keyboard focus indicators, a skip link, mobile layouts, and reduced-motion rules.

## Browser review checklist

On November 2, 2026, the source/HTTP check, all 14 mocked waitlist tests, and static build passed. The new page was viewed against the supplied mockup at desktop width and checked at 320, 375, 768, and 1280px; those widths had no horizontal overflow. The header link reached the form, both forms were disabled when no API URL was configured, and the browser console showed no errors. A live database submission was not tested.

Before publication, review the page in your target browsers and test both forms against an approved development database. Check keyboard focus, screen reader labels, reduced motion, backend errors, and the short WhatsApp contact line.

## Separate Vercel project

The landing project can use this repository with:

- Root Directory: `landing`
- Framework Preset: Other
- Install Command override: `node --version` (no installation is needed)
- Build Command: `node scripts/build.mjs`
- Output Directory: `dist`
- Build-time `TYPEIN_API_BASE_URL` pointing to the public HTTPS backend `/api/v1`

Choose the production branch and preview/ignored-build policy explicitly. Do not
reuse the existing storefront/dashboard project.
Configure the dedicated backend entry point `app.waitlist_main:app` with `CORS_ORIGINS`
set to the exact landing origin. The isolated Neon `typein-waitlist` branch was
migrated to `a7d8c9012f34` and verified on November 2, 2026; the original development
and production branches were not migrated. Verify backend availability and one
end-to-end registration with a test number before opening sign-ups. Confirm the
intended domain before adding canonical or Open Graph URL/image metadata; none has
been invented here. Configure production response headers on the approved
host: the local preview server's headers do not automatically apply to static hosting.
The README, development server, scripts and package files are excluded from `dist/`.
