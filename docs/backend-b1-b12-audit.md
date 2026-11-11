# Backend B1–B12 audit

Checked 11 November 2026 against `app.v1_main:app`, the dashboard,
Railway V1 staging, and Neon `typein-v1-staging`. Status means the **requested
scope**, not whether an individual source file exists. No live database or
provider configuration was changed for this audit.

| Item | Baseline | Evidence and gap | External dependency |
| --- | --- | --- | --- |
| B1 deployment, DB readiness, backups | Partial; deployed | Railway staging commit `cae29cb` reports success. `/health` and `/ready` both returned 200 after deployment. Neon staging has no configured snapshot schedule or listed snapshot. | Verify Neon backup retention and restore policy; Sentry deferred by request. |
| B2 auth | Partial | Signup, login and me still use bearer JWT in dashboard localStorage. Slug availability/reserved names and single-process signup/login/slug limits are implemented. No cookie refresh/logout, password reset or resumable onboarding yet. | A same-site API domain or proxy is needed for reliable browser cookie sessions; controlled reset-email inbox. |
| B3 migrations | Partial | New additive Meta inbox, booking cap index and trial reminder ledger migrations were applied to disposable and staging Neon branches through the Neon connector; both now report `a81d7e4c902b`. The original “section 10” requirements were not found. | Original section 10 specification needed to declare B3 complete. |
| B4 merchant billing | Partial, tested on staging | Test Mode subscription auth and cancellation webhooks were provider-delivered and applied; trial, grace, lock and webhook paths have tests. First paid cycle, UPI, failed renewal and recovery lack provider-delivery evidence. | Razorpay Test Mode cycle transitions; live cutover deliberately deferred. |
| B5 cutoff, owner changes, refund_due | Partial | Customer manage links still apply separate per-service cutoffs. Owner cancellation/reschedule and `refund_due` remain absent. The user specified the 24-hour rule and full refund conditions; implementation remains. | None for the stated policy; owner reschedule agreement flow still needs design. |
| B6 UPI | Partial, older Phase 2 | `payments.py` and payment services implement test payment routes, but V1 does not mount that router. No complete V1 hold/claim/Received/Not received journey. | Merchant payment-policy decisions and controlled Razorpay test account. |
| B7 schedule exceptions | Missing | V1 has operating hours and recurring batch schedules, but no exception entity or affected-booking workflow. | Product rules for closures and existing bookings. |
| B8 demo rule | Implemented; deployed | Public `/demo` is browser-session-only with a 60-minute reset, sample services, availability, dashboard, and simulated booking/cancel/reschedule. It has no real API calls, payments, messages, exports, or customer data. `app.typein.co/demo` returned 200 with the current bundle. Browser interaction has not yet been manually checked. | None. |
| B9 owner booking and lists | Partial | V1 agenda and an authenticated manual booking route with tenant check and cap override exist. Filtered booking/customer lists and CSV remain absent. | CSV columns and privacy/retention decisions. |
| B10 WhatsApp | Partial | Two outgoing template calls exist. A signed Meta webhook challenge and durable dedup inbox are implemented but not configured for delivery; retry/log, owner alerts, consent and merchant config remain. | Meta account/template/number inspection; business verification for later live messaging. |
| B11 spam protection | Partial; deployed | Public confirmed bookings have a 3-successes-per-phone/business rolling 24-hour cap, counting cancellations, with authenticated owner override at `POST /api/v1/bookings/manual`. Process-local waitlist/auth limits exist. Turnstile and distributed limits remain. | Turnstile site/secret keys. |
| B12 email/reminders | Partial | A controlled-clock 3-day, 1-day and trial-end owner reminder job, delivery ledger, retries, provider idempotency key and default-off gate are implemented. No Railway schedule or real messages were enabled. | Controlled test inbox, sender verification, job schedule. |

V1 staging is `https://typein-v1-api-staging.up.railway.app` on Railway service
`typein-v1-api`; the dashboard test surface is `https://app.typein.co` on
Vercel. The Neon staging branch ID is `br-old-recipe-ax2f0gli`; the disposable
database-test branch is `br-autumn-waterfall-axedxt8e`. Neither is the primary
Neon production branch. The waitlist service and its database remain separate.

The database-backed pytest fixture was not rerun in this increment: it refused
to run without `TEST_DATABASE_URL`, and the automatic approval reviewer rejected
embedding the disposable branch credential in a shell command because that
would expose it in process metadata. No database reset occurred in that attempt.
The new schema was checked through the Neon connector on the disposable branch.

Validation: 135 backend unit tests, Ruff, dashboard lint and build passed.
Railway staging reported a successful deployment of `cae29cb`; Vercel deployment
`dpl_5dEUw7h4T3edkdySMWHf51A7grH5` was READY and aliased to `app.typein.co`.
The API returned 200 for `/health`, `/ready`, and an `app.typein.co` CORS
preflight. `/demo` returned 200 and its bundle included the demo and staging
API URL. No reminder job schedule or delivery was enabled. To test the job
later, set `TRIAL_REMINDER_DELIVERY_ENABLED=true` on an isolated test service
with `TRIAL_REMINDER_TEST_RECIPIENT` pointing to a controlled inbox, then run
`python -m app.jobs.trial_reminders`. Do not enable it on V1 staging with real
merchant addresses. Resend idempotency keys are retained for 24 hours; retries
after a two-hour job gap are suppressed to keep retries within that provider
window and avoid an ambiguous duplicate send.

The route-level billing lock audit and Razorpay Test Mode evidence are in
`docs/razorpay-test-mode-handoff.md`. The Meta account is not connected through
an available tool in this run, so WABA, payment method, token options, webhook
settings, and template statuses cannot yet be claimed as inspected.
