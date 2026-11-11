# Merchant billing: Test Mode handoff

Checked on 11 November 2026. `https://app.typein.co` is currently a **test
surface** backed by `https://typein-v1-api-staging.up.railway.app`; it is not a
production merchant launch. The V1 database is the isolated Neon
`typein-v1-staging` branch. The disposable database-test branch is
`codex-billing-tests-20261111`. Neither is the live Neon branch.

## Configuration

The Railway **staging V1 API service**, not Vercel, holds `RAZORPAY_KEY_ID`,
`RAZORPAY_KEY_SECRET`, `RAZORPAY_PLAN_ID`, and `RAZORPAY_WEBHOOK_SECRET`. Keep
Vercel's `VITE_API_URL` at
`https://typein-v1-api-staging.up.railway.app/api/v1`. Never put Razorpay
secrets in a `VITE_` variable. The V1 service also uses `ENVIRONMENT=staging`,
`PUBLIC_API_URL=https://typein-v1-api-staging.up.railway.app`,
`CORS_ORIGINS=https://app.typein.co,http://localhost:5173`,
`BILLING_TRIAL_DAYS=30`, `BILLING_PLAN_AMOUNT_PAISE=149900`,
`BILLING_TOTAL_COUNT=120`, and `BILLING_GRACE_DAYS=3`.

The plan ID is the ID of the monthly INR 1,499 **Test Mode** plan in Razorpay;
it is distinct from the key ID. The webhook secret is a separate random
string chosen when creating the Test Mode webhook. To generate one in Windows
PowerShell without storing it in command history, run:

```powershell
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToHexString($bytes).ToLowerInvariant()
```

Copy the output into Razorpay's webhook **Secret** field and the Railway V1
staging `RAZORPAY_WEBHOOK_SECRET` variable. Do not use the API key secret as
the webhook secret. The repository's `backend/.env.example` lists local names;
the deployed service reads its own Railway variables, not a local `.env`.

## Razorpay dashboard check

In **Test Mode**, Account & Settings → Webhooks, the existing merchant
subscription webhook was updated on 11 November to
`https://typein-v1-api-staging.up.railway.app/api/v1/webhooks/razorpay`.
It is enabled and selects `subscription.authenticated`, `subscription.activated`,
`subscription.charged`, `subscription.pending`, `subscription.halted`,
`subscription.paused`, `subscription.resumed`, `subscription.cancelled`, and
`subscription.completed`. The other Razorpay webhooks were left unchanged.
The existing secret is hidden in Razorpay; its match with Railway was verified
by a provider-delivered, signed cancellation event accepted by the V1 API.

The current key was confirmed to be a Test Mode key, and the provider API
confirmed the configured plan is INR 1,499 monthly with interval 1. A new
staging merchant completed signup, created a real Test Mode subscription,
and cancelled it before any charge. The API reported `cancelled`, retained
trial access, and showed zero payments. This confirms that Razorpay accepted
the current `total_count=120` on subscription creation; it is a cycle count,
not an accepted business account cap. After updating the webhook URL, a second
controlled Test Mode subscription was created and cancelled. Railway logged
`POST /api/v1/webhooks/razorpay` with HTTP 200, and the V1 staging Neon branch
recorded `subscription.cancelled` with `processing_status=applied` and no
error code.

On 11 November, a separate staging merchant completed the browser Checkout
with an official Razorpay dummy Visa card. The user performed the final
simulated bank step. Checkout returned to Billing with authorization received,
and the Neon branch recorded provider-delivered `subscription.authenticated`
with `processing_status=applied` and no error. The merchant remained `trialing`
through 11 December, with zero monthly subscription payments; Razorpay has not
started the paid cycle. Precharge cancellation via the dashboard then produced
another applied, provider-delivered `subscription.cancelled` event and retained
the original trial end. Resubscribing after this cancellation revealed a missing
dashboard button. The button was fixed, lint and build passed, and Vercel
deployment `dpl_Hb4gWLCm9N7bVYkyzkJj3pchZEmf` was READY at `app.typein.co`;
the button was verified in the served page. A second subscription was opened
to try UPI, then cancelled before authorization, again preserving trial access.
The Razorpay Checkout exposed only a UPI QR path, not a UPI ID field, so a
`success@razorpay` VPA could not be entered. The QR test was not completed.
The final test merchant state is `cancelled`, trial through 11 December, and
zero monthly payments.

Local validation: 110 backend unit tests passed; 43 database-backed tests
passed on the disposable Neon branch; dashboard lint and build passed; Ruff
passed. The database suite started before a response-model fix and reported
four serializer warnings, which the final deployment addresses. The final
Railway staging deployment and Vercel production alias are healthy; `/health`
returned 200, the dashboard returned 200 with the Railway staging API URL in
its bundle, and the API returned 200 to the `app.typein.co` CORS preflight.
The staging database revision is `d4c2e6a91b70`.

**Test Mode is not yet complete.** The test card authorization and cancellation
are provider-backed. Still complete a supported UPI Checkout, observe a
provider-delivered activation and payment history,
and exercise failed recurring payment, grace expiry, recovery, paid-cycle
cancellation, and an existing customer's manage link while the business is
locked. Where Razorpay Test Mode cannot produce a recurring transition, use
the focused signed-event tests and label that evidence synthetic. Invalid
signature rejection, duplicate event handling, grace boundaries, and lock
behavior have focused API/unit coverage; they are not provider-delivery
evidence. Do not send customer email or WhatsApp during these checks.

## Lock coverage

`require_billing_access` rejects a locked merchant with HTTP 403 and
`subscription_required`. The following list covers every V1 route shown by
the app's OpenAPI document. Public routes do not depend on a merchant session.

| Method and path under `/api/v1` | Locked-account behavior | Enforcement |
| --- | --- | --- |
| `POST /auth/signup`, `POST /auth/login` | Allowed for account entry/recovery | Public auth routes |
| `GET /auth/me`, `GET /merchant/me` | Allowed to display account and billing state | `CurrentMerchant` only |
| `PATCH /merchant/me` | Blocked | Route `require_billing_access` |
| `GET /merchants/me/agenda` | Blocked | Router `require_billing_access` |
| `GET, POST /services`; `GET, PATCH, DELETE /services/{service_id}` | Blocked | Router `require_billing_access` |
| `GET, POST /staff`; `PATCH, DELETE /staff/{staff_id}` | Blocked | Router `require_billing_access` |
| `GET, POST /services/{service_id}/custom-fields`; `PATCH, DELETE /services/{service_id}/custom-fields/{field_id}` | Blocked | Router `require_billing_access` |
| `GET, PUT /operating-hours` | Blocked | Router `require_billing_access` |
| `GET, POST /services/{service_id}/batch-schedules`; `PATCH, DELETE /services/{service_id}/batch-schedules/{schedule_id}` | Blocked | Router `require_billing_access` |
| `GET /billing`; `POST /billing/subscribe`, `/billing/confirm`, `/billing/cancel` | Allowed for recovery and cancellation | `CurrentMerchant` only |
| `GET /storefront/{slug}`, `/storefront/{slug}/available-slots` | Public listing remains available; storefront reports `accepting_bookings=false` when locked | Public route, computed billing summary |
| `POST /bookings/initiate` | Blocked for the locked business | `require_booking_access` checks service owner |
| `GET /manage/{token}`, `POST /manage/{token}/cancel`, `/manage/{token}/reschedule` | Allowed for existing customers | Management token, independent of merchant billing |
| `POST /webhooks/razorpay` | Allowed for provider delivery | Razorpay HMAC signature and event ID |

`GET /health` is public outside `/api/v1`. The older booking-payment API is
not mounted in the V1 app. Direct API tests cover locked services, booking
submission, and the customer manage route's lack of billing gating; the
existing-booking manage-link flow still needs a provider-backed walkthrough.

## Production cutover later

Review and apply billing migrations to a separately verified live Neon
target; create a live INR 1,499 plan and use live keys only on the production
Railway V1 service; create a **separate live webhook secret** and live webhook;
confirm Razorpay approved `app.typein.co`; rotate any credential previously
exposed; then verify a controlled production Checkout and signed webhook.
Do not turn the staging-linked `app.typein.co` deployment into a merchant
launch by changing `ENVIRONMENT` alone.

## Meta Business verification next

Confirm admin access to the Meta Business portfolio and the legal business
name, address, phone, and registration documents. Confirm `typein.co` website
ownership and its published business/contact details. Inventory the WhatsApp
Business Account, phone-number status, display name, and any existing review
requirements. Then follow the current Meta dashboard prompts and record any
required domain, identity, or messaging review steps. Do not submit Meta
verification or alter Meta settings during this billing task.
