# Conversions Classification in the Frontend — Changes Report

A walkthrough of the OpenSpec changes that, taken together, rebuilt how conversions are **classified** on the Conversions page — what stage a row belongs to, what marketing channel attributed it, which payload mechanism would push it to Google, and whether Google actually accepted it. Each entry notes status, then breaks the work into what landed in the **database** (the classifier logic itself, since most classification is computed in SQL views the FE consumes) and the **frontend** (how the page reads, groups, filters, and labels those classifications).

The scope is *classification* — how rows get labeled and bucketed — not detection criteria, upload mechanics, or layout polish. Where a change blends both, only the classification-relevant parts are summarized here.

---

## High-level overview

The Conversions page started as a single-axis classifier — every estimate was bucketed by a coarse **medium** (calls / form / thumbtack / other) and shown under a step strip whose tabs (`booking | qualified | converted`) were row filters rather than view modes. Over the period covered by this report, that single axis grew into four orthogonal classifiers, each surfaced as its own column on the rollup rail:

1. **Stage** — *which step of the funnel a row is at.* Locked in by `pipeline-stage-criteria-v3`, then loosened and decoupled by `conversion-detection-v2` so qualified/converted no longer require a prior booking row.
2. **Channel** — *which marketing channel attributed the lead.* `lead-channel-taxonomy` replaced the four-medium bucketing with the seven-channel ONYX taxonomy (Google Ads / GLS / GMB / Thumbtack / Organic / Direct / Others), moving the classifier out of TypeScript and into the `vw_conversion_candidates.channel` column. `classify-callrail-call-forwarding-as-direct` fixed a tail-case miss where CallRail call-forwarding leads were resolving to `Other` instead of `Direct`.
3. **Method** — *which payload shape Google Ads would receive for this row* (`with_gclid` / `user_data_only` / `none`). Introduced by `conversions-rollup-redesign` and classified in parity with the edge function's payload builder.
4. **Push & Acceptance** — *local upload outcome vs. Google-side acceptance.* Also `conversions-rollup-redesign`. The Push column splits "sent" rows into "no error" vs. "with error"; Acceptance pulls `google_successful_count / local_uploaded_count` from `vw_gads_upload_reconciliation_daily` directly into the rollup rail.

Two structural changes sit alongside those classifiers:

- **`conversion-view-modes`** turned the step tabs into a required **mode selector** that drives which date field, value field, upload action, and detail-panel layout the entire page uses. Before this, every tab grouped by `estimate_created_at` regardless of context; after, each mode groups by its own stage's `*_datetime`. This is the change that made the Stage classifier *consequential* — picking a tab now actually reframes the page around that stage rather than just filtering rows.
- **`conversions-rollup-redesign`** added an `all` mode that surfaces booked / qualified / converted side-by-side, with the rollup using **per-stage event dates** so a single estimate contributes one event-row per stage in the period each event actually occurred.

Net result by the end of the window: the page reads like a small set of classifier columns instead of a single funnel. A row's identity at a glance is `(Stage, Channel, Method, Push, Acceptance, Value)`, and each of those is a column rather than a derived inference.

---

## April 24 — Locking in the stage criteria (`booking → qualified → converted`)

**`pipeline-stage-criteria-v3`** — *archived*

The starting point. The previous criteria were too narrow on the front (booking required `is_booking_form = true`, missing phone and GLS leads) and too downstream on the back (qualified required `work_status`, converted required job completion). Smart Bidding needed a faster, broader stage signal. This change rewrote the three pipeline-stage classifiers from scratch.

### Database

- Booking criterion broadened: any estimate with a source signal qualifies (booking form, booking tags, correlated CallRail lead, or `lead_source` set). No longer restricted to `is_booking_form = true`.
- Qualified criterion simplified to: any estimate option with non-null `total_amount`. No `work_status` or `approval_status` check at this stage. Value = SUM of approved/pro-approved option amounts.
- Converted redefined from job completion to **estimate approval**: any option with `approval_status IN ('approved', 'pro approved')`. Pipeline is now fully estimate-centric; `jobs` no longer participates.
- Stage datetimes locked in: booking = `estimates.created_at`, qualified = `estimates.updated_at`, converted = `MAX(estimate_options.updated_at)` over approved options. These become the per-stage date fields every later change uses for grouping.
- All three stages discover GCLID-less rows as `pending`; the upload edge function skips them at send time with an error message. (Unified skip rule.)
- New SQL functions: `get_pending_booking_lead_conversions()`, `get_pending_qualified_lead_conversions()`, `get_pending_converted_lead_conversions()`; wrapper `discover_pending_conversions()` unchanged.

### Frontend

- None directly. The view's column shapes are unchanged; the FE's existing stage columns now project the new criteria's values. The change calls out that `ConversionsPage.tsx` "may need column/display adjustments if value semantics change" but no FE work shipped under this slug — value-semantic FE work landed under [conversion-detection-v2](#may-1--decoupling-the-stages-and-introducing-customer-scoped-gclid-attribution).

**New capability folders:** `pipeline-stage-booking`, `pipeline-stage-qualified`, `pipeline-stage-converted`.

---

## May 1 — Decoupling the stages and introducing customer-scoped GCLID attribution

**`conversion-detection-v2`** — *archived*

Three weeks of operating the v3 stage criteria surfaced a structural problem: stages were chained. A row could not be discovered as qualified or converted without a prior `booking_lead` row, which silently dropped legitimate ad-attributed phone leads and HCP-created estimates. The change also refined the qualified gate, aligned the dashboard's `display_value` with the edge function's upload value, and introduced customer-scoped GCLID attribution so follow-up estimates for the same customer keep the original click.

### Database

- **Stages decoupled.** `booking_lead` is no longer a prerequisite for `qualified_lead` or `converted_lead` discovery — all three are now independent detectors.
- **Qualified gate refined** from "any option with `total_amount > 0`" to `estimates.work_status IN ('complete rated', 'complete unrated')` AND at least one option with `total_amount > 0`. Datetime moves to `estimates.updated_at` to capture the status-transition moment. Value formula changes from `SUM(approved options)` to `AVG(all options)`.
- **`display_value`** in `vw_conversion_candidates` changes from `SUM(approved options)` to `AVG(all options) / 100.0` so the dashboard and the upload payload agree on what value is shown for a qualified row.
- **`converted_lead`** gate keeps `∃ approved option` only; booking-lead prerequisite removed. GCLID resolution now reads `customer_gclids`.
- **`customer_gclids` table** (new) stores GCLID → customer associations. A pre-pass inside `discover_pending_conversions()` populates it from `booking_tags` and `callrail_leads`. A backfill function reclaims historical attributions.

### Frontend

- **Connector lines between stage cells removed.** The "connected strip" metaphor was visually claiming that booking → qualified → converted was a chain; now that the stages are independent events, the strip became misleading. Three independent cells, no visual chaining.
- **`work_status` rendered inside the Qualified stage cell** as a sub-label so the trigger condition is visible at a glance — operators can see *why* a row qualified without expanding the detail panel.
- The semantic shift of `display_value` from "approved total" to "average of presented options" silently affects the Value column on the page; no code change beyond what the view does, but the displayed number can move for any qualified row.

**New capability folders:** `customer-gclid-attribution`.

---

## May 7 — Replacing the four-medium bucket with the seven-channel taxonomy

**`lead-channel-taxonomy`** — *archived*

The biggest classification change of the period. The page had been grouping estimates by a coarse medium (`calls | form | thumbtack | other`) computed client-side in a TypeScript function called `classifySourceBucket()`. That bucketing obscured which marketing channel — the thing spend is actually allocated against — generated each lead. The ONYX lead-channel taxonomy defines seven semantic channels (Google Ads, GLS, GMB, Thumbtack, Organic, Direct, Others); this change wired that taxonomy through the view, the page, the filter bar, and the upload-reconciliation report.

### Database

- New `channel` column on [vw_conversion_candidates](supabase/migrations/) computed by a single SQL CASE that evaluates signals in taxonomy priority order: Thumbtack → Google Ads → GLS → GMB → Organic → Direct → Others. The classifier is now in one place, declarative, and shared by every consumer.
- The `booking_tags` lateral join in the view expanded to surface `utm_source`, `utm_medium`, `hsa_src`, and `ref` as named columns alongside `gclid` — the classifier needs them to disambiguate Google Ads (`gclid` present) from GLS (`hsa_src`) from generic UTM-tagged traffic.
- `vw_gads_upload_reconciliation_daily` source-bucket columns realigned to match the taxonomy labels so the Upload Report and the Conversions page agree on channel names.

### Frontend

- **`classifySourceBucket()` deleted; replaced with `classifyChannel()`** in [ConversionsPage.tsx](horizon-dashboard/src/components/pages/ConversionsPage.tsx). The new function is a thin pass-through that reads `vw_conversion_candidates.channel` — no client-side classification, no string heuristics. The classifier lives in SQL; the FE just reads it.
- **`buildHierarchy()` regrouped** to group by channel (7 taxonomy values) instead of source bucket (4 medium values). Month → Week → SourceGroup is now Month → Week → Channel, with one group per taxonomy value present in the window.
- **Filter bar dropdown options changed** from medium buckets (Calls / Form / Other) to taxonomy channels (Google Ads / GLS / GMB / Organic / Direct / Thumbtack / Other). Labels and colors updated to match.
- **`lead-channel-resolver` on the write side** (in `hcp-booking`) — included here for completeness because it determines what `estimates.lead_source` gets persisted as for new bookings, but the page itself reads the SQL classifier, not the persisted value.

**New capability folders:** `lead-channel-resolver`, `conversion-channel-grouping`.

---

## May 9 — Turning the step tabs into a mode selector

**`conversion-view-modes`** — *archived*

The step tabs (`booking | qualified | converted | all | closed`) were row filters: pick a tab, hide rows that aren't at that stage. Everything else stayed the same — month/week grouping always used `estimate_created_at`, the Value column always used `display_value`, all three upload cells were always visible. That meant a qualified-in-April estimate appeared under January in the Qualified tab (because it was *created* in January), and value sums mixed averages and approved totals depending on which row was visible. This change turned the tabs into a **mode** that drives every per-stage decision on the page.

### Database

- None. Pure FE/UX change consuming the existing view columns.

### Frontend

- **`stepFilter` state becomes `conversionMode`.** "All" and "Closed" tabs removed; the four remaining tabs (`Pre-discovery · Booking · Qualified · Converted`) are now a required mode selector. Default is `Qualified`.
- **`getRowDateKeys()` becomes mode-aware** — the hierarchy date field switches per active mode: `estimate_created_at` for Pre-discovery, `booking_datetime` for Booking, `qualified_datetime` for Qualified, `converted_datetime` for Converted. The same row appears in different weeks depending on which mode is active, because each mode is asking a different question.
- **Value column becomes tab-aware.** Booking and Pre-discovery show `—`; Qualified shows `qualified_value` (AVG of all options); Converted shows `converted_value` (SUM of approved). The zero-value filter checks the tab-relevant value field rather than always `display_value`, and is hidden on Booking and Pre-discovery.
- **Pipeline column collapses to a single `PhaseCell`** for the active stage instead of always showing all three. Pre-discovery shows no cell at all.
- **Expanded detail panel** shows the active stage's section expanded and the other two collapsed (status badge + value only) for cross-reference.
- **GCLID coverage stat** and the bulk-upload button both scope to the active stage.
- A companion change, `pre-discovery-expanded-detail`, removed the `status != null` gates on the Booking and Qualified detail sections so pre-discovery estimates expand to a populated panel instead of a near-empty one.

**New capability folders:** `conversion-view-mode`.

---

## May 19 — Adding Method / Push / Acceptance as first-class rollup columns

**`conversions-rollup-redesign`** — *archived*

By mid-May, Stage and Channel were each their own classifier with its own column. But the rollup rail was still `Rows | GCLID | Uploaded | Sync | Value` — five columns that mostly answered "how many rows are there?" with no insight into *which payload mechanism would push them*, *whether the push actually succeeded locally*, or *whether Google accepted them on the other side*. The Upload Report page tracked acceptance, but cross-referencing it with the Conversions rail was manual. This change rebuilt the rail around three new classifiers (Method, Push, Acceptance) and added an `all` mode that shows booked / qualified / converted simultaneously.

### Database

- [vw_conversion_candidates](supabase/migrations/) extended with customer `email`, `mobile_number`, and service-address fields, plus a `customer_has_user_identifier` boolean. These let the Method classifier decide `with_gclid` vs `user_data_only` vs `none` without a second round trip.
- No new acceptance plumbing — the Acceptance column reuses the existing [vw_gads_upload_reconciliation_daily](supabase/migrations/) view that already powers the Upload Report page.

### Frontend

- **`ConversionMode` gains `'all'`.** `STEP_TABS` re-orders to `Pre-Discovery · All Conv · Booking · Qualified · Converted`. In `all` mode the hierarchy uses per-stage event dates: each `(estimate, stage)` event is bucketed by that stage's own `*_datetime`, so a single estimate that progressed through all three stages contributes one event-row per stage, each in the period its event actually occurred. Rollup totals exactly equal the count of visible event-rows.
- **Rail columns replaced** from `Rows | GCLID | Uploaded | Sync | Value` to `Stage | Method | Push | Acceptance | Value`. In `all` mode each cell shows three sub-values (booked / qualified / converted); in single-stage mode it shows one.
- **Method classifier** in the FE. For every conversion-candidate row the page bucket it as `with_gclid` (GCLID stored on the stage's `gads_conversion_uploads` row), `user_data_only` (no GCLID but customer has hashed email and/or phone — enhanced-conversion path), or `none` (cannot be uploaded). Classification is kept in parity with [payload-builder.ts](supabase/functions/google-ads-conversion-upload/payload-builder.ts) — same buckets, same decision tree — so the column predicts the edge function's behavior.
- **Push classifier** in the FE. Splits the rollup window's `gads_conversion_uploads` rows into `total sent`, `sent with no error`, `sent with error` from the existing per-stage status/attempt/error columns on `vw_conversion_candidates`.
- **Acceptance classifier** in the FE. New hook fetches `vw_gads_upload_reconciliation_daily` rows scoped to the visible hierarchy window (reusing the TZ + week-keying logic from `lib/uploadReport.ts`). Renders as `google_successful_count / local_uploaded_count` with a percent on Month and Week rows only (not SourceGroup, not per-estimate). In `all` mode, broken down by `event_key` for booked / qualified / converted.
- [computeStats.ts](horizon-dashboard/src/components/conversions/lib/computeStats.ts) return shape changes from a flat `RollupStats` to `{ stageCounts, methodCounts, pushCounts, value }` per stage — directly mirroring the new column set.
- New `RollupMetricCell` primitive supports the tri-cell per-stage layout used in `all` mode.

**New capability folders:** `rollup-metric-columns`, `rollup-acceptance-metric`.

---

## May 25 — Patching the channel classifier for CallRail call-forwarding leads

**`classify-callrail-call-forwarding-as-direct`** — *archived*

A small tail-case fix on the Channel classifier. With the seven-channel taxonomy in place, `vw_conversion_candidates.channel` was resolving to `'Other'` for three estimates belonging to one customer whose CallRail lead had `source = 'Call forwarding'` and `medium = 'direct'` — the canonical "customer dialed a CallRail tracking number directly" signal. The existing CallRail branch scanned for `LIKE '%direct%'` and matched the literal `'Direct'` value but missed the `'Call forwarding'` tracker-mode value entirely.

### Database

- One migration replacing `vw_conversion_candidates` (CASCADE drop also recreates `vw_gads_upload_reconciliation_daily`). Schema unchanged; the channel CASE grows by one branch: `LOWER(src.value) LIKE '%call forwarding%'` → `'Direct'`. Positioned after every higher-precedence CallRail branch so a hypothetical `'Google Local Services / direct'` row still resolves to GLS via the earlier `%local services%` branch.
- No data migration. The view recomputes on read; three production estimates reclassify from `'Other'` → `'Direct'` the moment the migration deploys.

### Frontend

- None. The weekly rollup picks up the reclassified rows automatically; the Direct group label and ordering are unchanged.

---

## Themes

1. **Classification moved from TypeScript to SQL.** The biggest structural shift across these changes is that the FE no longer *computes* classifications — it *reads* them. `classifySourceBucket()` was replaced by a view column. The Method classifier is mirrored from the edge function's payload builder. Acceptance is read from a reconciliation view. The remaining FE classifier work is presentation (chip rendering, group ordering, tri-cell layouts) rather than logic. That makes the classifiers shareable between the page, the upload report, and the edge function without drift.

2. **Each classifier got its own column instead of being collapsed into a single label.** The rail went from one ambiguous "where is this row?" axis to five orthogonal columns (Stage / Method / Push / Acceptance / Channel-as-group / Value). A row's identity is now a tuple, and each component is independently filterable, groupable, and aggregable. This is what made the `all` mode possible — you can show booked / qualified / converted side-by-side because they're just three values of the Stage classifier, not three different page configurations.

3. **Tab semantics shifted from "filter" to "mode".** Pre-`conversion-view-modes`, picking a tab hid rows. Post-, picking a tab also changed which date field grouped the hierarchy, which value column rendered, which upload action was available, and which detail-panel section was expanded. That elevation is why the Stage classifier became consequential — the same row genuinely looks like a different row depending on which mode you're in, because each mode is asking a different question about it.

4. **Decoupling stages enabled cross-stage classification work.** Once `conversion-detection-v2` removed the booking-lead prerequisite for qualified and converted, every later classifier could treat the three stages as independent events of the same shape. That is what lets `all` mode bucket one estimate as three event-rows by per-stage event dates, and what lets the Method / Push / Acceptance columns render the same way for any active stage without special-cased branches.

5. **Tail-case fixes get cheaper as the classifier consolidates.** The CallRail call-forwarding fix is one CASE branch in one view. That is the payoff for centralizing channel classification — what would have been an edit in `ConversionsPage.tsx`, the upload-reconciliation view, and any other consumer is now a one-line addition where the classifier actually lives.
