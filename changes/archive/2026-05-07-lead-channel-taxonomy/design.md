## Context

The ONYX conversions pipeline surfaces booking-form estimates and correlated CallRail calls as "conversion candidates" for the Google Ads upload workflow. Estimates are synced from Housecall Pro (HCP) via `hcp-import-data`; form bookings are created directly in HCP via the `hcp-booking` edge function and tagged in the `booking_tags` table.

**Current state:**

- `vw_conversion_candidates` joins `estimates`, `callrail_leads`, `booking_tags`, and `customers`. The only attribution signal it surfaces from `booking_tags` is `gclid`.
- `customers.lead_source` and `estimates.lead_source` are populated from HCP's API response, which returns `null` for `lead_source` on booking-form estimates because we deliberately strip that field before sending it to HCP (HCP only accepts its own predefined values, not our channel strings).
- `customers.lead_source` is overwritten on every booking (`upsert` with no guard), meaning a repeat customer's original channel is silently replaced with their most recent booking's channel.
- Classification happens twice independently: a SQL `CASE` in `vw_gads_upload_reconciliation_daily` and a TypeScript `classifySourceBucket()` in `ConversionsPage.tsx`. Both use a coarse 4-bucket medium model (calls / form / thumbtack / other) rather than the business's 7-channel taxonomy.

**Constraints:**
- HCP's `lead_source` field on customer/estimate objects only accepts HCP-predefined values; we cannot write our channel strings there via the HCP API.
- `booking_tags(estimate_id, key)` has a UNIQUE constraint — values written at booking time are immutable per key per estimate. This makes `booking_tags` the most trustworthy attribution record.
- The `hcp-booking` edge function owns the booking-form code path. `hcp-import-data` owns the sync path; imported estimates receive HCP's `lead_source` value (which may be set by an in-field tech or dispatcher, not by us).
- No migration should reset or backfill existing `customers.lead_source` or `estimates.lead_source` rows. The SQL resolver must be robust to missing data.

## Goals / Non-Goals

**Goals:**
- Resolve the correct taxonomy channel string at booking-form submission time and persist it to `estimates.lead_source`.
- Prevent the original channel for a customer from being overwritten if the customer rebooking occurs within a 90-day attribution window.
- Surface `utm_source`, `utm_medium`, `hsa_src`, and `ref` from `booking_tags` as named view columns in `vw_conversion_candidates`.
- Introduce a single `channel` computed column in `vw_conversion_candidates` using a priority-ordered taxonomy CASE expression (eliminates SQL/TS duplication).
- Replace medium-based grouping in the `ConversionsPage` weekly rollup with taxonomy-channel grouping reading the view's `channel` column.

**Non-Goals:**
- Backfilling `estimates.lead_source` or `customers.lead_source` for pre-fix historical rows (existing view fallback chain handles them).
- Changing how HCP imports set `estimates.lead_source` (the sync path is out of scope; those values may reflect a dispatcher's manual assignment).
- Removing `booking_tags` entries or altering their UNIQUE constraint.
- Any change to the CallRail correlator logic (`correlate_callrail_estimate` trigger).

## Decisions

### D1 — Write channel to `estimates.lead_source` (not a new column)

**Decision:** Reuse the existing `estimates.lead_source` TEXT column rather than adding a new `estimates.booking_channel` column.

**Rationale:** The column is already joined in `vw_conversion_candidates`. Adding a parallel column would require every consumer to decide which column to read. For booking-form estimates, the current value is null (HCP returns null), so writing to it introduces no data conflict. HCP-imported estimates may already have a non-null HCP-assigned value; the SQL resolver's fallback chain handles this transparently.

**Alternative considered:** New `estimates.booking_channel` column. Rejected because it doubles the schema surface area for a capability that fits within the existing intent of `lead_source`.

---

### D2 — 90-day attribution guard: anchor to `customers.created_at`, no-update on conflict

**Decision:** In `supabase-writer.ts`, before upserting the customer, read the existing customer row (`lead_source`, `created_at`). If the row exists AND `created_at` is within 90 days of the current booking time AND `lead_source` is non-null, use the existing `lead_source` as the resolved channel instead of the one computed from the current booking's URL tags. Always write the resolved channel to `estimates.lead_source` regardless.

**Rationale:** Anchoring to `customers.created_at` (first booking date) matches the intent of "the channel that first acquired this customer." Rolling the window forward on each visit would allow an organic visit to overwrite an original paid-channel attribution, which defeats the purpose. The guard only applies if the existing `lead_source` is non-null; if the first booking was also processed by broken code and has null, we do not preserve that null.

**Alternative considered:** Ignore-duplicates on the customers upsert and never update `lead_source`. Rejected: a customer created before this fix was deployed would permanently keep `null` as their lead source because the original booking wrote null.

---

### D3 — `buildLeadSource()` output drives the resolution; `booking_tags` is the fallback

**Decision:** The resolved channel written to `estimates.lead_source` comes from `buildLeadSource()` (already in `horizon-dashboard/src/lib/lead-source.ts`). The SQL view's `channel` CASE reads `estimates.lead_source` first, then falls back to `booking_tags` signals, then to `callrail_leads` signals, then to "Other".

**Rationale:** `buildLeadSource()` already implements the correct taxonomy priority chain (gclid → fbclid → ttclid → msclkid → utm_source → referrer domain → "Online Booking"). Centralizing the resolution at write-time means the view can simply read a pre-resolved string rather than re-implementing the resolution logic in SQL across multiple columns.

**Fallback chain in SQL (for pre-fix rows and call-only conversions):**
1. `estimates.lead_source` (non-null string, written by the fix)
2. `booking_tags` gclid present → `'Google Ads'`
3. `booking_tags` hsa_src = 'LocalServicesAds' → `'GLS'`
4. `booking_tags` utm_source → map to taxonomy channel
5. `booking_tags` ref matches google.com/localservices → `'GLS'`
6. `callrail_leads.source` present → map to taxonomy channel
7. `'Other'`

---

### D4 — Single SQL `channel` column; TypeScript reads it, does not reclassify

**Decision:** The `channel` taxonomy string lives in `vw_conversion_candidates` as a CASE expression. `ConversionsPage.tsx` reads `row.channel` directly instead of running its own classification logic. The existing TypeScript `classifySourceBucket()` function is removed.

**Rationale:** Eliminates dual-maintenance. Adding a new channel or tweaking priority order requires one SQL migration, not coordinated TS + SQL changes.

**Risk:** If a consumer needs a channel value offline (e.g., a local filter before the view is loaded), there is no TS-side channel resolver. This is acceptable for the current use case (all filtering happens against the view response).

---

### D5 — Update `vw_gads_upload_reconciliation_daily` to reference the new `channel` column

**Decision:** Replace the hardcoded 4-bucket `source_bucket` CASE in the reconciliation view with a reference to `vw_conversion_candidates.channel`.

**Rationale:** The reconciliation view already joins on `vw_conversion_candidates`; using the pre-resolved `channel` value is a one-line change and removes the third copy of the classification logic.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Pre-fix rows have `estimates.lead_source = null`; SQL fallback chain must correctly handle all-null state | Fallback chain terminates with `'Other'` unconditionally; tested against known null rows in local DB |
| `buildLeadSource()` runs in the browser (horizon-dashboard) and result is sent over the network; a malicious actor could forge the channel string | `booking_tags` (server-side-written URL params) are the authoritative record; `estimates.lead_source` is a convenience denormalization used for display only — not used in billing or access control |
| 90-day guard anchored to `created_at` means a customer who books organic in month 1 and paid in month 4 has month 4 paid booking attributed to organic | Acceptable: the 90-day window is industry-standard for first-touch attribution. Business confirmed they want first-touch within the window. |
| Reconciliation view consumers may depend on the current 4-bucket `source_bucket` column labels | Audit all consumers of `vw_gads_upload_reconciliation_daily` before migration; the labels change from `form/calls/thumbtack/other` to taxonomy names |
| `hcp-booking` edge function calls the Supabase DB twice for repeat customers (read then write) | One additional query per booking for repeat customers only; latency impact is negligible at current booking volume |

## Migration Plan

1. Deploy updated `supabase-writer.ts` to the `hcp-booking` edge function (new bookings begin writing correct channel to `estimates.lead_source`).
2. Apply migration: recreate `vw_conversion_candidates` with expanded `booking_tags` lateral and `channel` CASE column.
3. Apply migration: update `vw_gads_upload_reconciliation_daily` to reference `channel` from the updated view.
4. Deploy updated `ConversionsPage.tsx` (reads `channel` column, uses taxonomy grouping).

**Rollback:** Each step is independently reversible. The edge function change can be reverted by redeploying the previous version (no schema change). The view migration can be rolled back by reverting the migration SQL (views are recreatable). The TS change is frontend-only (redeploy the prior build).

## Open Questions

1. **`customers.lead_source` write strategy for post-90-day repeat customers:** Should we update `customers.lead_source` to the new channel when the customer is outside the attribution window? Current plan says yes (overwrite), but this means `customers.lead_source` always reflects the most recent channel rather than the original. Confirm with business.

2. **`utm_source` → taxonomy channel mapping completeness:** The mapping from raw `utm_source` values to taxonomy channels (e.g., `'google'` → `'Google Ads'` vs `'Organic'` depending on whether `gclid` is present) needs a full enumeration. Defer to tasks spec.

3. **Conversions filter bar option labels:** The UI currently has a "Source" filter with options [All, Calls, Form, Other]. When grouping shifts to channels, the dropdown options change significantly. Confirm whether the filter should show raw channel names or a condensed set (e.g., "Paid" / "Organic" / "Thumbtack").

4. **GMB detection via `ref` field:** The `ref` booking tag stores the parent page URL. GMB bookings arrive with a `ref` containing `google.com/localservices`. This detection is fragile (URL pattern matching). Confirm the expected `ref` values from a sample of GMB bookings before implementing.
