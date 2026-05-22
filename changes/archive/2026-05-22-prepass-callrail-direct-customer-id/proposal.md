## Why

The `customer_gclids` discovery pre-pass (and its sibling backfill function) reach `callrail_leads → customer_id` indirectly through `JOIN estimates e ON e.id::varchar = cl.estimate_id`. That join silently drops every CallRail lead whose `estimate_id` is NULL — which happens whenever the BEFORE-trigger correlator (`correlate_callrail_estimate`) matched a customer but could not pick a "most recent estimate" at write time, or did not match the customer at all and only a later resync would attach it.

The CallRail lead's `customer_id` is already populated by the same trigger and is the actual value the pre-pass consumes; routing through `estimates` is structurally unnecessary and excludes usable GCLIDs from `customer_gclids`. Removing the indirection recovers those GCLIDs without changing any semantics that downstream resolvers depend on, and decouples GCLID attribution from the brittle "newest estimate at trigger time" heuristic.

## What Changes

- **Discovery pre-pass (Source 2: callrail_leads) joins by `customer_id` instead of through `estimates.id = cl.estimate_id`.** The two affected sites are the batch orchestrator `discover_pending_conversions()` and the per-estimate `discover_pending_conversions_for_estimate(p_estimate_id)`. Each becomes a `FROM callrail_leads cl WHERE cl.gclid IS NOT NULL AND cl.customer_id IS NOT NULL` (plus, in the per-estimate variant, `AND cl.customer_id = v_customer_id`).
- **`backfill_customer_gclids()` joins by `customer_id`** the same way.
- **`customer_gclids.estimate_id` writes:** the inserted `estimate_id` value for the CallRail source becomes `cl.estimate_id` directly (may be NULL) rather than the joined-through `e.id`. This column is informational — no resolver reads it — but documenting the change in semantics is worth calling out.
- **No change** to: the BEFORE-trigger correlator, `vw_conversion_candidates` (still uses `cl.estimate_id` for per-estimate aggregates), the resolver, the upload path, the qualified/converted detection functions, or the `(customer_id, gclid)` uniqueness contract.
- **No data migration required.** Running the backfill once after deploy reclaims the historically dropped rows. CallRail leads with NULL `customer_id` remain excluded (no way to attribute them to a customer).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `customer-gclid-attribution`: the pre-pass and backfill SHALL source CallRail GCLIDs via `callrail_leads.customer_id` directly, not via `JOIN estimates ON cl.estimate_id`. Eligibility broadens from "CallRail lead with both `customer_id` and `estimate_id` set" to "CallRail lead with `customer_id` set". The `(customer_id, gclid)` uniqueness behavior and the rest of the resolver are unchanged.

## Impact

- **Database**: one migration replacing the two pre-pass orchestrators (`discover_pending_conversions`, `discover_pending_conversions_for_estimate`) and the `backfill_customer_gclids` function. The newest existing definitions live in `supabase/migrations/20260520000002_gads_discover_set_lifecycle.sql` (lines 66-70 and 191-195) and `supabase/migrations/20260501000002_backfill_customer_gclids.sql` (lines 42-46).
- **Data**: existing `customer_gclids` rows are unaffected. Running `SELECT backfill_customer_gclids()` after deploy backfills the previously dropped CallRail-derived rows (those where `cl.customer_id IS NOT NULL AND cl.estimate_id IS NULL`).
- **Edge functions / dashboard**: no changes. Consumers read from `customer_gclids` and don't care which join produced a row.
- **`vw_conversion_candidates`**: untouched. The view still uses `cl.estimate_id` for per-estimate aggregates (`call_count`, `callrail_sources`, first-touch medium). Improving that linkage is a separate concern — explicitly out of scope here.
- **Tests**: add a pgTAP case covering a CallRail lead with `customer_id` set and `estimate_id` NULL — pre-pass should now insert a `customer_gclids` row for it. Existing tests under `supabase/tests/` should remain green.
- **Interaction with `conversion-attribution-overhaul`**: that change reworks the resolver selection logic but assumes `customer_gclids` is correctly populated. This change shores up that assumption and is independently mergeable. Touching the same pre-pass function means whichever change lands second will need to incorporate the other's edits.
- **Backwards compatibility**: non-breaking. Eligible-row set strictly grows; no existing row is removed or rewritten.
