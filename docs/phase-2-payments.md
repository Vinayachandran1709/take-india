# Phase 2: Razorpay Test payments

This branch implements local Test Mode payments only. The original Phase 1 Neon branch
and existing hosted services must remain unchanged during local payment development.
Phase 3 is excluded.

## Local setup

1. Create a separate Neon branch named `phase2-dev`. Do not reuse the original Phase 1 branch.
2. Create untracked `backend/.env.phase2` from `.env.example`. Set `DATABASE_URL` to
   its pooled URL and `DIRECT_DATABASE_URL` to its direct URL. Copy the local JWT
   settings. Keep the existing `.env` intact. Confirm in Neon that these URLs belong
   to `phase2-dev`; endpoint names alone cannot prove a human-readable branch name.
3. Generate a Fernet key locally with
   `.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   Store it only as `CREDENTIAL_ENCRYPTION_KEY` in the untracked file. Retain that key:
   replacing it makes existing encrypted credential versions unreadable.
4. Activate the backend venv, install missing requirements, then set
   `.venv\Scripts\python.exe -m scripts.phase2 check`, followed by
   `.venv\Scripts\python.exe -m scripts.phase2 migrate`. The guard verifies that the
   pooled/direct pair matches and differs from the original `.env` and test database.
   New revisions are `d71e2a9014bc` and `e82f3b0125cd`, after unchanged Phase 1
   revision `cbdbf24900c6`.
5. Seed locally with `.venv\Scripts\python.exe -m scripts.phase2 seed`, then start
   FastAPI with `.venv\Scripts\python.exe -m scripts.phase2 serve`.
   Set frontend local environment variables `NEXT_PUBLIC_API_URL` and `VITE_API_URL`
   to `http://localhost:8000/api/v1`. Run storefront on 3000 and dashboard on 5173.
6. Run database tests only with `ENVIRONMENT=test`, isolated `TEST_DATABASE_URL`, and
   `ALLOW_TEST_DATABASE_RESET=true`. The guard rejects development/test URL aliases,
   including pooled versus direct Neon hosts. Never reset development databases.

## Merchant Test account and real browser checklist

- Enter credentials in the authenticated dashboard's **Test payments** screen, never chat.
- Only `TEST` and `rzp_test_` are accepted. Secrets are write-only and encrypted at rest.
- Configure the merchant Razorpay Test account for **Automatic Capture**. There is no
  manual Capture API in Phase 2.
- When real webhook testing is needed, obtain approval for a public development HTTPS
  tunnel to local FastAPI. Set `PUBLIC_API_URL` to that HTTPS origin and restart locally.
- Add the displayed configuration-specific webhook URL in Razorpay Test Mode using
  the exact webhook secret entered in settings. Subscribe to `payment.captured` and
  `payment.failed`. A webhook URL is not a Checkout `callback_url`.
- For each of the three seeded merchants, connect that merchant's Test account,
  initiate its appointment/class/custom-order hold in the storefront, and complete
  Standard Checkout with Razorpay Test payment details. Record provider order/payment
  IDs, HTTP results, confirmed status, balance, and exactly one customer-count change.
- Exercise dismissal/retry and one failed payment followed by success. Browser success
  alone does not confirm a booking: authoritative captured state must reconcile.
- Real browser E2E is **not verified** until all three merchant flows actually pass.

## APIs and public access

`POST /api/v1/bookings/initiate` remains provider-free. Its one-time
`public_booking_token` is generated from 32 random bytes; only its SHA-256 hash is
stored. The private confirmation link carries it in a fragment, which the client
moves to sessionStorage and removes from the address bar. Subsequent requests use
`X-Booking-Token`. Invalid or missing access is concealed with 404. Do not put this
token in query strings, logs, dashboard summaries, Razorpay notes, or metadata.

| Endpoint | Purpose |
| --- | --- |
| `GET/PUT/DELETE /api/v1/merchants/me/payment-settings` | Masked settings, versioned Test credentials, disconnect |
| `POST /api/v1/bookings/{reference}/payment` | Create or reuse an unpaid provider order |
| `POST /api/v1/payments/razorpay/verify` | Checkout signature and authoritative provider verification |
| `POST /api/v1/payments/razorpay/webhook/{opaque_config_id}` | Raw-body signed event processing |
| `GET /api/v1/bookings/{reference}/status` | Non-cacheable minimal booking/payment summary |
| `GET /api/v1/merchants/me/bookings` | Latest 50 tenant-owned summaries |

The browser uses the Standard Checkout JavaScript handler, with server-returned key,
order, amount and currency. After verification it polls every three seconds for at
most a minute, then offers explicit refresh. Public summaries contain no customer PII
or reputation/review outcomes.

## Creation, retries and manual Test recovery

Amounts use Decimal and immutable server-calculated expectations. Generic conversion
maps INR 0.01 to one paise, while the Razorpay gateway rejects INR orders below 100
paise before network access. Receipts are `TI_` plus the transaction UUID hex: exactly
35 ASCII characters, unique and without PII.

Creation serializes on the booking and persists `CREATING` before the provider call.
It releases database locks during network requests. There is no automatic POST retry
and no assumption of provider create-order idempotency.

An ambiguous timeout becomes `UNKNOWN`. Subsequent requests investigate the exact
receipt using provider order evidence. The receipt filter can match substrings, so
the gateway requires an exact receipt match. If no unique order is proven, replacement
remains blocked. A stale `CREATING` intent is investigated as `UNKNOWN`.

For an unresolved attempt, investigate that receipt in the merchant's Razorpay Test
dashboard and support tools. Preserve the attempt and do not repeatedly issue new
create-order POSTs. There is deliberately no automatic/manual API override to pretend
an ambiguous attempt is safe. Establish the original order's authoritative identity
before reconciliation; otherwise leave it blocked for investigation. An expired hold
may be replaced by a new booking, but any later capture on the old booking still
requires reconciliation and may need merchant review.

Existing `created` and unpaid `attempted` orders are reused. A failure event does not
make the order unusable. Paid orders are never reopened; fetch their payments and
reconcile captured evidence. Already captured/confirmed bookings cannot create orders.

## Webhooks, rotation and reconciliation

Resolve the opaque configuration ID and verify HMAC against raw bytes before JSON
parsing. Prefer configuration ID plus `x-razorpay-event-id` for dedupe. Only absent
headers use a deterministic signed-identifier fallback. Store normalized identifiers,
payload hash and outcome, never raw payloads.

Processed/duplicate/ignored valid events return 2xx. Invalid signatures and temporary
provider/database failures return non-2xx. Temporary failures do not commit a processed
event. Failed payment IDs belong to event records; they never become the immutable
captured payment ID. `FAILED → CAPTURED` is allowed, `CAPTURED → FAILED` is prohibited.

Rotation creates a new encrypted configuration and webhook URL. Keep prior webhook
endpoints configured for outstanding retries; old attempts retain their original
credential version. Disconnect stops new payments but does not erase old credentials
or stop checkout/webhook reconciliation.

Checkout verification and captured webhooks use common reconciliation. Lock order is
booking, payment attempt, original resource/batch, then customer aggregate. Occupancy
excludes the current booking. Eligible captures atomically confirm, record paid/balance
amounts, and increment the customer count once; `last_visit_date` is never changed.

For a cancelled booking or a released resource now legitimately occupied, captured
financial evidence remains, booking stays non-confirmed, and `payment_review_required`
is set. No capacity/count change or refund automation occurs. Existing booking
Razorpay fields are compatibility copies; `payment_transactions` is authoritative.
Distinct duplicate captures are retained in `payment_capture_anomalies` without
changing the booking lifecycle or overwriting the original captured payment ID.

## Verification record

- Pre-implementation Phase 1: 26 pytest tests passed; Ruff passed; storefront and
  dashboard lint/build passed.
- Final automated backend run on the isolated test database: 52 pytest tests passed
  in 1027.52 seconds.
- Backend Ruff: passed.
- Alembic on the isolated test database: `upgrade head`, `current`, `history` and
  `check` passed. Current revision is `e82f3b0125cd`.
- Storefront: lint and production build passed.
- Dashboard: lint and production build passed.
- Local FastAPI smoke: `/health` returned 200 and `/docs` returned 200.
- Real Razorpay Test Mode browser E2E for all three seeded merchants is still pending
  merchant Test credentials, webhook HTTPS delivery and manual checkout execution.
  This document does not claim full Phase 2 verification until those external E2E
  flows pass.
