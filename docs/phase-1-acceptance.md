# Phase 1 acceptance verification

Verified on 2026-09-10. No Phase 2 features implemented.

| Acceptance item | Result | Evidence |
| --- | --- | --- |
| Existing backend virtual environment | PASS | Activated `backend/.venv/Scripts/Activate.ps1`; Python 3.13.14; `pip check` clean; no installation needed |
| pytest | PASS | Original complete suite: 25 passed in 409.33s. Added acceptance test: 1 passed in 107.79s. All 26 tests executed successfully across these two runs |
| Ruff | PASS | `ruff check .`, including the added test |
| Alembic upgrade/current/history | PASS | Executed against development and isolated test databases; both at `cbdbf24900c6 (head)`; history `<base> -> cbdbf24900c6`, create phase 1 schema |
| Storefront dependencies/lint/build | PASS | node_modules already present; npm ci unnecessary; npm run lint and npm run build succeeded |
| Dashboard dependencies/lint/build | PASS | node_modules already present; npm ci unnecessary; npm run lint and npm run build succeeded |
| FastAPI runtime | PASS | Started Uvicorn; `/health`, `/docs`, `/openapi.json` returned HTTP 200 |
| Mode A slots / explicit staff | PASS | Expected 10:00–11:00 slot and staff; hold created with server-derived price, end time, reference and expiry |
| Omitted-staff assignment | PASS | Lowest available staff UUID selected deterministically; concurrent requests assigned distinct available staff |
| Overlap rejection | PASS | Non-identical overlapping interval rejected; shared merchant resource protected |
| Mode A concurrency | PASS | Two simultaneous explicit-staff requests produced exactly one 201 and one 409 SLOT_UNAVAILABLE |
| Mode B capacity/concurrency | PASS | Three simultaneous requests for two seats produced two 201 responses and one 409 BATCH_FULL |
| Mode C lead-time boundary | PASS | -1 minute rejected with LEAD_TIME_REQUIRED; exact boundary and +1 minute accepted |
| Expired holds | PASS | Expired PENDING_PAYMENT holds permit booking; added test proves appointment and batch availability restored after expiry |
| Active holds | PASS | Non-expired appointment hold removes assigned staff and rejects duplicate; batch hold decreases remaining capacity |
| Tenant read/update/delete isolation | PASS | Foreign services, custom fields and schedules return 404; staff update/delete isolated; cross-tenant DB relationships rejected |
| Seeded storefronts and offerings | PASS | All three merchant APIs, rendered listing pages and rendered service booking pages returned 200 with expected offering titles |
| All-mode availability | PASS | Live availability API returned nonempty slots for all three seeded merchants for 2030-01-07 |
| Public booking holds | PASS | Added test creates holds through public API for seeded appointment, batch and custom-order offerings on isolated test DB |
| No Razorpay call | PASS | Public holds remain PENDING_PAYMENT/PENDING with null Razorpay IDs; outbound HTTPX transports fail the added test if called; source review found no payment integration calls |
| Database reset safety | PASS | Test process explicitly uses ENVIRONMENT=test; TEST_DATABASE_URL set, reset enabled, URL distinct from DATABASE_URL; database host/name identity also checked against both development URLs, accounting for pooled host aliases. Resets used only the guarded test engine |

Initial sandboxed frontend builds encountered process/network restrictions. Authorized reruns with the necessary access passed; the final storefront build ran sequentially before runtime checks.

Both pytest runs emitted only a cache-write permission warning. This did not affect test execution or results. The second run tried an alternate cache directory, which was also restricted.

The only source addition is `backend/tests/test_phase1_acceptance.py`, covering seeded public offerings, all-mode holds, appointment/batch active and expired availability, and absence of outbound HTTPX payment requests. No application changes were required. No development database reset was performed.

**PHASE 1 VERIFIED — READY FOR PHASE 2**
