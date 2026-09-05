# Booking engine rules

## Status and capacity

Every public Phase 1 initiation creates exactly:

```text
booking_status = PENDING_PAYMENT
payment_status = PENDING
```

It is a temporary unpaid hold. Phase 1 never promotes it to a paid or confirmed state.

The single capacity predicate is:

```text
booking_status = CONFIRMED
OR
(booking_status = PENDING_PAYMENT AND hold_expires_at > current UTC time)
```

Expired holds do not occupy capacity. A confirmed booking remains occupying even if a historical hold-expiry value exists.

## Time semantics

Merchant-local calendar values are PostgreSQL `DATE`/`TIME`: booking date/times, operating hours, and batch schedules. Merchant timezone defaults to `Asia/Kolkata` and uses Python `zoneinfo.ZoneInfo`.

Absolute lifecycle values are timezone-aware UTC timestamps: `created_at`, `updated_at`, and `hold_expires_at`. A shared injectable clock supplies current UTC; tests never sleep or manipulate the system clock. Naive and aware datetimes are never compared.

Weekday numbering is Sunday-based: Sunday `0` through Saturday `6`.

## Appointment mode

Slots begin at opening time, align to service duration, and cannot extend after closing. Past starts are excluded. The server derives end time from `start + duration_minutes` and detects every interval overlap with `existing.start < requested.end AND existing.end > requested.start`.

Explicit staff transaction:

```text
lock selected staff and assignment rows
verify active, assigned, and tenant ownership
recheck occupying overlaps
upsert customer
insert unpaid hold
commit
```

Automatic assignment uses stable UUID order. Each active assigned candidate is attempted with `FOR UPDATE SKIP LOCKED`; after locking, overlaps are checked and the first truly available candidate is stored on the booking. No candidate produces `409 SLOT_UNAVAILABLE`.

A service with exactly zero staff assignments uses the merchant-level appointment resource. The merchant row is locked, and every staff-less appointment service for that merchant shares one overlapping capacity. Bookings tied to real staff do not consume this resource. Assigned-but-inactive staff do not turn a service into staff-less capacity.

## Batch mode

The server maps the requested date to the recurring weekday, then locks the selected active schedule row. Start, end, and capacity come from that schedule. Occupying bookings are recounted inside the same transaction; a full schedule returns `409 BATCH_FULL`.

## Custom-order mode

Customers request a local pickup/delivery start and end. The server verifies ordering, operating hours, timezone, and the exact inclusive boundary:

```text
requested start >= current merchant time + prep lead time
```

Phase 1 adds no logistics or speculative capacity model.

## Money, references, and tenant defense

Money uses PostgreSQL `NUMERIC` and Python `Decimal`. Amount due is a positive configured advance, otherwise the full configured service price.

Human references use `TI-YYYYMMDD-XXXXXXXXXX`, where the suffix is cryptographically random Crockford-style text. A database unique constraint is authoritative; inserts safely retry a collision up to five times. UUIDs remain internal identifiers.

Merchant-owned composite foreign keys prevent cross-tenant service/staff/custom-field/schedule/customer/booking relationships through direct SQL. This supplements—not replaces—tenant-scoped application queries.
