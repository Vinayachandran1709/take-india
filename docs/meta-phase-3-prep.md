# Meta preparation checklist

This is an external preparation checklist only. Phase 1 contains no Meta or WhatsApp integration.

- Verify the Meta Business account and business details.
- Start WhatsApp Business Platform setup and use a test WABA/test number where appropriate.
- Draft and submit future utility templates early because approval has external lead time:
  - `booking_confirmation`
  - `booking_reminder_24h`
  - `booking_reminder_2h`
  - `review_request`
  - `retention_rebook`
- Keep production credentials out of this repository.

## Future template drafts

These are planning drafts only. Variables and wording must be reviewed against Meta policy before later submission.

### `booking_confirmation`

`Your booking {{1}} with {{2}} is confirmed for {{3}} at {{4}}. We look forward to seeing you.`

### `booking_reminder_24h`

`Reminder: booking {{1}} with {{2}} is tomorrow, {{3}}, at {{4}}.`

### `booking_reminder_2h`

`Your booking {{1}} with {{2}} starts in about two hours at {{3}}.`

### `review_request`

`Thank you for visiting {{1}}. If you have a moment, share your experience here: {{2}}.`

### `retention_rebook`

`It may be time for your next {{1}} at {{2}}. Book when convenient: {{3}}.`

No credentials, SDKs, API calls, webhook handlers, notifications, or scheduling code are included in Phase 1.
