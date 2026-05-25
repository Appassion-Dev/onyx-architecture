## Why

`vw_conversion_candidates.channel` currently resolves to `'Other'` for 3 estimates belonging to 1 customer (Curt Chandler — estimates #5953, #7543, plus one sibling) whose CallRail lead has `source = 'Call forwarding'` and `medium = 'direct'` — the canonical "customer dialed a CallRail tracking number directly" signal. The existing CallRail branch of the channel CASE scans `callrail_sources` for `LIKE '%direct%'`, which matches the literal `source = 'Direct'` value but misses the `'Call forwarding'` tracker-mode value entirely. The previously-archived `2026-05-22-prepass-callrail-direct-customer-id` change (and its sibling migration `20260522000001_vw_conversion_candidates_callrail_by_customer.sql`) already corrected the upstream correlation — the call row IS now attached to the estimate via `customer_id` — so the only remaining defect is in the channel classifier itself.

The wider population of `callrail_leads` rows with `source = 'Call forwarding'` (40 total) does not translate into more affected estimates: 39 of the 40 are calls from numbers that have never matched any customer (telco CNAM strings like "TAMPA CENTRA FL", business spam like "WELLCARE"/"ONSTAR", unidentified callers). The BEFORE-trigger correlator correctly fails to attribute them — there is no customer to attribute them to. Investigation confirms zero of those 39 phones map to a customer record at any point in time. They are call-tracking noise, not missing attributions.

## What Changes

- Add one new branch to the `channel` CASE in `vw_conversion_candidates`: a CallRail lead with `source` matching `LOWER(src.value) LIKE '%call forwarding%'` SHALL resolve to `'Direct'`. The branch is placed alongside the existing `%direct%` CallRail branch (after GMB/Google Ads/GLS/Thumbtack/Organic, so a hypothetical `'Google Local Services / direct'` row still correctly resolves to GLS via the earlier `%local services%` branch).
- No change to: the `call_agg` LATERAL projection (still aggregates `source`/`campaign`/`gclid` only), the BEFORE-trigger correlator, the discovery pre-pass, the resolver, or `vw_gads_upload_reconciliation_daily`'s source-bucket mapping (Direct still maps to `'form'`).
- No data migration. The view recomputes on read; the 40 affected rows reclassify the moment the migration deploys.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `conversion-channel-grouping`: the priority chain's step 6 (CallRail-source mapping) SHALL recognize `source ILIKE '%call forwarding%'` as `'Direct'`. Other steps unchanged. Taxonomy values and ordering unchanged.

## Impact

- **Database**: one migration replacing `vw_conversion_candidates` (CASCADE drop also recreates `vw_gads_upload_reconciliation_daily`, mirroring `20260522000001_vw_conversion_candidates_callrail_by_customer.sql`). Schema unchanged; only the channel CASE body grows by one branch.
- **Data**: 3 production estimates (1 customer) currently classified as `'Other'` reclassify to `'Direct'` on next read. No row that was already classified to a specific channel changes — the new branch sits after every higher-precedence CallRail branch.
- **Edge functions / dashboard**: no changes. The Conversions page weekly rollup picks up the new Direct rows automatically; the existing Direct group label and ordering are unchanged.
- **`vw_gads_upload_reconciliation_daily`**: untouched semantically. The `Direct` channel already maps to the `'form'` source_bucket in that view's `local_classified` CTE; whether that bucket label is accurate for call-origin Direct attribution is a separate concern, explicitly out of scope here.
- **Tests**: add a pgTAP case covering a fixture row where the customer has a CallRail lead with `source = 'Call forwarding'` — the view's `channel` for that estimate SHALL be `'Direct'`. Existing channel tests should remain green.
- **Out of scope**:
  - `Van Wrap / direct` (3 rows) — same class of bug, different source string. Separate concern.
  - Projecting `cl.medium` / `cl.utm_medium` into `call_agg` so the classifier can read Direct from CallRail's structured medium fields rather than inferring it from source strings. Structural fix; separate concern.
  - `Facebook Ads / paid-social` (1 row) — distinct branch entirely; not addressed.
- **Backwards compatibility**: non-breaking. Affected-row set strictly shifts from `'Other'` → `'Direct'`; no row moves to a different specific channel.
