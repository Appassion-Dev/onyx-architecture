## 1. Discovery SQL — Qualified Lead

- [x] 1.1 Write migration replacing `get_pending_qualified_lead_conversions()`: add `AND cg.first_seen_at >= e.updated_at - INTERVAL '90 days'` to the `customer_gclids` subquery
- [x] 1.2 Verify the function compiles and returns expected rows against the local database (check both the windowed and NULL-GCLID paths)
- [x] 1.3 Confirm `ORDER BY first_seen_at ASC LIMIT 1` is still applied within the window (first-touch ordering preserved)

## 2. Discovery SQL — Converted Lead

- [x] 2.1 Write migration replacing `get_pending_converted_lead_conversions()`: add the same `AND cg.first_seen_at >= <conversion_event_ts> - INTERVAL '90 days'` filter (using the approved option timestamp as the reference point)
- [x] 2.2 Verify the function compiles and returns expected rows locally (windowed and NULL-GCLID paths)

## 3. Cleanup — Existing Stale Pending Rows

- [x] 3.1 Write a diagnostic query (read-only) to count `pending` rows where the stored GCLID has `first_seen_at < conversion_datetime - INTERVAL '90 days'`
- [x] 3.2 Write a cleanup migration that sets `gclid = NULL` for those rows (leaving `status = 'pending'`) so they are retried via enhanced conversions
- [ ] 3.3 Review diagnostic output before applying cleanup migration

## 4. Spec Updates

- [x] 4.1 Apply the `customer-gclid-attribution` delta spec: update `openspec/specs/customer-gclid-attribution/spec.md` with the MODIFIED GCLID resolution requirement and the new stale-rows remediation requirement
- [x] 4.2 Apply the `full-stack-architecture` delta spec: update `openspec/specs/full-stack-architecture/spec.md` with the two-window diagram and the arch-spec maintenance requirement

## 5. Validation

- [x] 5.1 Run `openspec validate --change "tighten-gclid-attribution-window"` (or equivalent) to confirm all artifacts are present
- [x] 5.2 Manually test qualified_lead discovery: create a test estimate with a `customer_gclids` row outside the 90-day window → confirm `gclid = NULL` is discovered
- [x] 5.3 Manually test qualified_lead discovery: create a test estimate with a `customer_gclids` row within the 90-day window → confirm correct GCLID is discovered
- [x] 5.4 Confirm cleanup migration correctly NULLs GCLIDs on the affected rows (run diagnostic query before and after)
