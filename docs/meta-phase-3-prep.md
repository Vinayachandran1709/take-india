# Meta Business and WhatsApp preparation

Checked against this repository on 11 November 2026. This is a handoff, not
evidence that Meta has approved the business, app, number, or templates.

## Account inventory before changing anything

- Identify the correct Meta Business portfolio, app, WhatsApp Business Account
  (WABA), phone-number ID, account currency, payment state, app mode, and the
  current business-verification status. Record IDs and statuses, not tokens.
- In Security Center, inspect whether **Start verification** is offered and
  which documents Meta currently accepts for this account. Match the legal
  name and address to the selected document. Do not assume an Udyam certificate
  will be accepted until the flow offers it.
- Verify ownership of `typein.co` using Meta's displayed DNS record if needed.
  First inspect existing DNS records so an unrelated record is not overwritten.
- Check that `https://typein.co`, `/privacy`, `/terms`, `/refund-policy`, and
  `/contact` resolve and show the correct legal operator and contact details.
  The code currently sets `LEGAL_NAME=typein` in `storefront/src/lib/site-config.ts`;
  confirm that this matches the legal identity submitted to Meta before editing
  or submitting verification.

## WhatsApp account, billing, and credentials

- Inspect the WABA payment method and currency before adding a card or making
  an irreversible currency choice. Confirm INR is available for this account.
- Confirm whether the selected phone-number ID is a Meta test number or a real
  business number, and check registration, display-name approval, and any
  existing WhatsApp Business app use. Do not remove a number from an app or
  migrate it until the account's supported coexistence/onboarding path is
  verified. A dedicated new number is a straightforward option.
- For backend sending, create or identify a system user with access to the
  correct app and WABA, then generate an appropriately scoped token with
  `whatsapp_business_messaging` and `whatsapp_business_management` when
  available. Use a duration and rotation plan supported by the account; do not
  assume a permanent token is always offered. Store the token only as
  `WHATSAPP_API_TOKEN` on the intended Railway backend service or in a local
  ignored `.env`, never in Vercel or Git. Configure
  `WHATSAPP_BUSINESS_ACCOUNT_ID`, `WHATSAPP_PHONE_NUMBER_ID`, and
  `WHATSAPP_API_VERSION` there as applicable. Avoid enabling real sends during
  a staging or billing test.
- Review the Meta app's current mode and requirements. Add the published
  privacy URL `https://typein.co/privacy` where Meta asks for it. Switch to
  Live only after the account, number, templates, billing, and sending controls
  are ready.

## Template inventory and code contract

The V1 backend currently sends only these templates from
`backend/app/services/whatsapp_service.py`:

| Template name | Trigger | Body parameter order |
| --- | --- | --- |
| `booking_confirmation_v1` | Booking confirmation | service title, business name, appointment date/time, manage URL |
| `reschedule_confirmation_v1` | Booking reschedule | service title, business name, new date/time, manage URL |

The code uses language code `en`. Inspect WhatsApp Manager for existing
templates, their actual language code, status, category, component type, and
parameter order before creating or changing anything. Update code and tests if
the approved language or component shape differs. Booking and reschedule
confirmations may qualify as Utility because they refer to a requested booking;
Meta's category decision is authoritative. Provide safe sample values for all
four variables and review the manage-link URL format before submission.

The older planning names `booking_confirmation`, `booking_reminder_24h`,
`booking_reminder_2h`, `review_request`, and `retention_rebook` are **not** all
implemented. Do not create duplicates or claim they are active. Draft reminders
only after the scheduling and consent behavior exists. Review requests and
rebooking prompts may be Marketing rather than Utility; check Meta's current
template-category rules before submission.

## Status and next gate

Repository preparation is complete: backend configuration names are documented
and the two current template payloads have unit tests. Meta account status,
business verification, domain verification, billing currency, real-number
registration, template approval, and live sending remain unverified. Inspect
those in the correct Meta account before making external changes. Do not send
real customer messages as a test.
