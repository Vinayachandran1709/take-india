# Phase 1 API contract

Base URL: `/api/v1`. JSON errors consistently use:

```json
{
  "error": {
    "code": "SLOT_UNAVAILABLE",
    "message": "The requested slot is unavailable",
    "details": {}
  }
}
```

Authenticated endpoints require `Authorization: Bearer <access-token>`. The access JWT has merchant identity and expiry only; there are no refresh tokens, cookies, OAuth, or server sessions.

## Authentication and merchant

| Method | Path | Behavior |
|---|---|---|
| POST | `/auth/signup` | Create merchant, normalize phone to E.164, return access token. |
| POST | `/auth/login` | JSON email/password login. |
| GET | `/auth/me` | Current active merchant. |
| GET | `/merchant/me` | Current merchant profile. |
| PATCH | `/merchant/me` | Update business/owner/phone/address/images/timezone. |

## Configuration

| Method | Path |
|---|---|
| GET, POST | `/services` |
| GET, PATCH, DELETE | `/services/{service_id}` |
| GET, POST | `/staff` |
| PATCH, DELETE | `/staff/{staff_id}` |
| GET, POST | `/services/{service_id}/custom-fields` |
| PATCH, DELETE | `/services/{service_id}/custom-fields/{field_id}` |
| GET, POST | `/services/{service_id}/batch-schedules` |
| PATCH, DELETE | `/services/{service_id}/batch-schedules/{schedule_id}` |
| GET, PUT | `/operating-hours` |

Service create/update accepts `staff_member_ids`, which are validated against the authenticated merchant. Operating-hours PUT atomically upserts the supplied weekdays. Service, staff, and batch-schedule DELETE calls soft-disable and are safe to repeat. `FILE_UPLOAD` may be configured only when optional; Phase 1 has no upload transport.

Every authenticated lookup uses both the resource ID and current merchant ID. A resource belonging to another tenant returns 404.

## Public storefront

### `GET /storefront/{slug}`

Returns an active merchant, sorted category names, and active services with public custom-field definitions. Inactive or unknown resources return 404.

### `GET /storefront/{slug}/available-slots?service_id={uuid}&date={YYYY-MM-DD}`

Returns one top-level shape:

```json
{
  "service_id": "uuid",
  "booking_mode": "APPOINTMENT",
  "date": "2030-01-07",
  "available_slots": [],
  "earliest_allowed_at": null
}
```

- Appointment entries include `start_time`, `end_time`, `available`, and `available_staff`.
- Batch entries include `batch_schedule_id`, times, `max_capacity`, `remaining_capacity`, and `available`.
- Custom-order entries describe the allowed business window; `earliest_allowed_at` is an absolute timestamp.

### `POST /bookings/initiate`

The client sends customer intent only:

```json
{
  "service_id": "uuid",
  "customer_name": "Ananya Rao",
  "customer_phone": "9876543210",
  "booking_date": "2030-01-07",
  "start_time": "10:00",
  "staff_member_id": null,
  "custom_field_responses": {}
}
```

Mode-specific intent:

- Appointment: `booking_date`, `start_time`, optional `staff_member_id`.
- Batch: `booking_date`, `batch_schedule_id`; omit start/end/staff.
- Custom order: `booking_date`, requested `start_time` and `end_time`.

The server derives merchant, mode, price, payable amount, duration/end time, batch times/capacity, and expiry. Client-supplied extra calculations are ignored. Customer phones accept Indian national or international input and are stored as validated E.164.

Successful initiation returns HTTP 201:

```json
{
  "booking_reference": "TI-20300107-7K2M9Q4J8R",
  "booking_status": "PENDING_PAYMENT",
  "payment_status": "PENDING",
  "booking_date": "2030-01-07",
  "start_time": "10:00:00",
  "end_time": "11:00:00",
  "staff_member_id": "uuid-or-null",
  "batch_schedule_id": null,
  "amount_to_pay": "300.00",
  "currency": "INR",
  "hold_expires_at": "2030-01-06T00:10:00Z"
}
```

There is no Phase 1 route that confirms a payment.

## Important errors

| Code | HTTP | Meaning |
|---|---:|---|
| `VALIDATION_ERROR` | 400 | Shape or mode-specific intent is invalid. |
| `AUTHENTICATION_REQUIRED` | 401 | Token/credentials are invalid. |
| `NOT_FOUND` | 404 | Unknown, inactive, or cross-tenant resource. |
| `SLOT_UNAVAILABLE` | 409 | Appointment resource cannot be reserved atomically. |
| `BATCH_UNAVAILABLE` | 409 | Schedule does not occur or has started. |
| `BATCH_FULL` | 409 | Atomic capacity recount found no seat. |
| `WINDOW_UNAVAILABLE` | 409 | Custom window is outside business hours. |
| `LEAD_TIME_REQUIRED` | 409 | Custom start is before the exact lead-time boundary. |
| `INVALID_CUSTOM_FIELDS` | 422 | Missing, unknown, or incorrectly typed intake response. |
| `REFERENCE_GENERATION_FAILED` | 503 | Five collision-safe reference attempts failed. |
