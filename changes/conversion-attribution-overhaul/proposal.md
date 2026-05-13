## Why

Diagnostic analysis of `gads_conversion_uploads` revealed two large, distinct attribution defect classes affecting Google Ads bid optimization:

1. **Some estimates converted but never produced a `qualified_lead` upload row** because the qualified gate is keyed on `estimates.work_status IN ('complete rated','complete unrated')`, while in the real HCP lifecycle qualified-quality is established earlier (when an option is approved or a job is created). The most common stuck status is `'created job from estimate'`.
2. **A number of `qualified_lead` rows exist with `gclid IS NULL`** even though the same customer has a usable GCLID in `customer_gclids` today. Causes are (a) the resolver picks the *oldest* customer GCLID and drops to NULL when that one falls outside the 90-day click-lookback window, even when fresher in-window GCLIDs exist, (b) discovery never re-resolves an existing row (`NOT EXISTS` gate), and (c) uploads run frequently enough that NULL-gclid rows are committed to Google Ads as enhanced-conversion-only before late-arriving CallRail/booking_tag data has a chance to populate `customer_gclids`.

The combined defect surface spans a meaningful number of estimates with degraded or missing GCLID attribution. Fixing it materially improves the click-ID coverage Google Ads receives and unblocks Smart Bidding signal quality.

## What Changes

This proposal bundles seven concrete changes. They are numbered here and the same numbering is used throughout `design.md`, the spec deltas, and `tasks.md` so each idea is traceable end-to-end.

1. **(BREAKING) Rewrite the GCLID resolver — newest in-window, never NULL when a fresh GCLID exists.** Replace the current "oldest, ASC" pick with **newest in-window DESC** against `customer_gclids` within the 90-day click-lookback window. The resolver returns NULL only when the customer has *no* in-window GCLID. This kills the failure mode where a stale oldest entry gets filtered out and the resolver returns NULL even though fresher in-window GCLIDs exist for the same customer. — *Capability: `customer-gclid-attribution`.*
2. **Add a re-attribution pass to discovery for qualified and converted leads.** `discover_pending_conversions()` and `discover_pending_conversions_for_estimate()` SHALL re-run the modern resolver against existing `gads_conversion_uploads` rows where `status = 'pending' AND gclid IS NULL AND conversion_type IN ('qualified_lead','converted_lead')`, updating the GCLID in place. Once `pending` is left (`uploaded`/`failed`), rows are not retroactively touched. This breaks the "NULL is sticky" lifecycle. — *Capability: `conversion-populate`.*
3. **Reduce the upload cron frequency to once per day.** Give the discovery + re-attribution loop a longer settling window so late-arriving CallRail / `booking_tags` data has a chance to populate `customer_gclids` before any `pending` row gets committed to Google Ads as enhanced-conversion-only. The manual UI upload path is unaffected by the cadence change. — *Capability: `conversion-upload`.*
4. **(BREAKING) Change the qualified-lead discovery gate to "estimate has a priced option".** Rewrite `get_pending_qualified_lead_conversions()` so the qualified gate fires when an estimate has at least one `estimate_options` row with `total_amount > 0`, removing the `estimates.work_status` allowlist. Qualified now reflects priced-scope establishment, not the rating step. — *Capability: `pipeline-stage-qualified`.*
5. **(BREAKING) Change the converted-lead discovery gate to "a job exists for the estimate".** Rewrite `get_pending_converted_lead_conversions()` so the converted gate fires when a `jobs` row exists for the estimate (via `jobs.original_estimate_id`), replacing the current `estimate_options.approval_status IN ('approved','pro approved')` gate. Converted now reflects "a job exists" rather than option-approval state. — *Capability: `pipeline-stage-converted`.*
6. **Make the Conversions page GCLID badge per-stage so it is coherent with the column-level GCLID total.** In `booking`/`qualified`/`converted` modes the badge SHALL reflect the GCLID actually stored on that stage's `gads_conversion_uploads` row (`booking_gclid` / `qualified_gclid` / `converted_gclid`), not the estimate-wide `all_gclids` pool. The pool view is preserved only in `pre-discovery` mode. Result: the badge and the column-level GCLID total are tautologically coherent in every stage view. — *Capability: `conversions-gclid-tag`.*
7. **(BREAKING) Resolve the GCLID once per discovery run per estimate and reuse it across all three stages.** Hoist the resolver call out of the per-stage detection functions into the discovery wrapper. A single resolved value is written to the booking, qualified, and converted rows for that estimate, so all three stages always carry the same `gclid` for a given customer/estimate (whether the GCLID was identified in `customer_gclids` from booking_tags/CallRail or just resolved during discovery). The per-stage 90-day window check is enforced at **upload time** — a stage drops the GCLID from its outbound payload and falls back to enhanced conversions if its own `conversion_datetime` puts the stored GCLID out of window — but the stored value on the row remains the canonical per-estimate pick. — *Capability: `customer-gclid-attribution` (resolver hoisting + upload-time window check), `conversion-populate` (single shared call wired into discovery).*

In addition, `vw_conversion_candidates` and any dependent views/reports SHALL be reviewed and updated as needed to reflect the new gate semantics for qualified (#4) and converted (#5).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `pipeline-stage-qualified`: gate changes from `estimates.work_status` allowlist to "any priced `estimate_options` row exists".
- `pipeline-stage-converted`: gate changes from `estimate_options.approval_status` to "a `jobs` row exists for the estimate".
- `customer-gclid-attribution`: resolver selection changes from oldest (ASC) to newest in-window (DESC within 90 days), with explicit NULL only when no in-window GCLID exists; the resolver is invoked **once per discovery run per estimate** and the result is shared across all three stage rows; the per-stage 90-day window check is enforced at upload time, not at discovery time.
- `conversion-populate`: discovery functions gain a re-attribution pass that updates `gclid` on existing pending rows when `customer_gclids` has acquired a usable in-window GCLID since the row was inserted; per-estimate GCLID resolution is hoisted out of the per-stage detection functions into a single shared call.
- `conversion-upload`: upload schedule reduced to once per day to allow time for re-attribution before NULL-gclid rows are committed; the per-stage 90-day window check is enforced here (drops the GCLID for the affected stage and proceeds via enhanced conversions).
- `conversions-gclid-tag`: badge data source changes from estimate-wide `all_gclids` to the per-stage `gads_conversion_uploads.gclid` for the active conversion mode; `pre-discovery` mode retains the pool view.

## Impact

- **Database**: new migrations rewriting `get_pending_qualified_lead_conversions()`, `get_pending_converted_lead_conversions()`, `discover_pending_conversions()`, `discover_pending_conversions_for_estimate()`. Cron schedule change for the upload edge function.
- **Views**: `vw_conversion_candidates` and `vw_gads_upload_reconciliation_daily` may need adjustments if their stage semantics depend on the previous gate definitions.
- **Edge functions**: `google-ads-conversion-upload` cron schedule reduced to daily; the upload function gains a per-stage in-window check that drops the row's `gclid` to NULL on the outbound payload (without rewriting the stored row) when the stored GCLID's `customer_gclids.first_seen_at` is more than 90 days before the stage's `conversion_datetime`.
- **Dashboard**: Conversions page badge logic updated; no schema change required for the badge fix because per-stage GCLID columns are already exposed by `vw_conversion_candidates`.
- **Backwards compatibility**: existing `gads_conversion_uploads` rows are not retroactively reconciled with the new gate definitions (those become stratigraphic/fossil rows). The re-attribution pass WILL however update `gclid` on existing NULL-gclid pending rows.
- **Conversion event timing in Google Ads**: qualified and converted events will fire earlier in the funnel than today (qualified at priced-option creation; converted at job creation). Smart Bidding models may need a brief re-learning period.
- **Tests**: existing pgTAP tests under `supabase/tests/` covering the qualified/converted gates and the GCLID lookback window need updating; new tests should cover the re-attribution pass and the in-window DESC selection.
