## Why

The Google Ads conversion pipeline has accumulated attribution edge cases that mis-assign conversions across a customer's estimates. The Wydro case (#7679) is the first documented instance: a single customer interaction produced two estimates, and the booking-lead conversion landed on the *canceled duplicate* while the qualified/converted stages landed on the *real* estimate — a funnel split across two records.

This proposal is a **research-phase register**: a single place to capture known conversion issues with their root cause, blast radius, and candidate solutions, *before* committing to any implementation. No tasks, specs, or code changes are produced here. Each issue graduates into its own implementation change when prioritized.

## What Changes

- Introduce a conversion-pipeline **known-issues register** (this document), to be appended as new issues are found.
- Document **Issue #1 (Wydro #7679)** in full: symptom, root cause, evidence, blast radius, candidate solutions, and open questions.
- Document **Issue #2 (Luckhardt #7534)**: a repeat-customer estimate whose only available GCLID is older than Google Ads' 90-day click-conversion window — surfaced via the dashboard as `expired`.
- Document **Issue #3 (Cross #7454)**: a second concrete instance of the same repeat-customer pattern as Issue #2, with the added wrinkle that all three stages (not just booking) will resolve out-of-window once they fire. Captured to confirm Issue #2 is not a one-off and to make the "all stages can expire" variant explicit.
- Document **Issue #4 (Lowe #7428)**: a second concrete instance of the CallRail "most-recent estimate" tiebreak from Issue #1, manifesting as a *channel* mis-classification rather than a funnel split — calls preceding a booking-form estimate by ~3 minutes were bound to a sibling estimate created two days later, leaving #7428 falling through to `channel = 'Other'` in `vw_conversion_candidates` instead of `GLS`.
- Document **Issue #5 (Osmanski #7864)**: a *discovery-before-correlation race* — a fresh, correct GCLID from two CallRail calls was present in the data, but `booking_lead` discovery fired in the ~15-minute window after the estimate became scheduled+assigned yet before the calls were correlated and the `customer_gclids` prepass ran. All three COALESCE sources resolved NULL, the once-ever discovery guard then froze the row at `gclid = NULL`, and it uploaded gclid-less. A new root cause: not a wrong-estimate tiebreak (#1/#4) and not an out-of-window GCLID (#2/#3).
- Document **Issue #6 (Martija #7865)**: a *value-frozen-at-discovery* case — the `qualified_lead` conversion value is snapshotted by discovery as `AVG(estimate_options.total_amount)/100` the moment the estimate completes, and the once-ever `ON CONFLICT DO NOTHING` guard plus a value-blind uploader mean a price edit made an hour later never propagates. Google received $1,260 for an option now priced $4,990. Same "frozen-at-discovery, once-ever guard" family as Issue #5, but a different frozen field (`conversion_value`, not `gclid`), a different stage (`qualified_lead`), and a different failure mode: the snapshot was *correct when taken* and the source data changed afterward, so settle-delay fixes don't apply.
- Explicitly defer implementation: no `tasks.md`, no `specs/` deltas, no code edits in this phase.

## Known Issues

### Issue #1 — Booking lead attributed to a canceled duplicate estimate (Wydro #7679)

**Symptom.** For customer `cus_a244223681264c9192111c4e651eda6d` (Elizabeth Wydro), the `booking_lead` conversion was attributed to estimate **#7679** (`csr_ba85…`, `work_status = user canceled`, single `$0` option), while `qualified_lead` and `converted_lead` were attributed to a *different* estimate, **#7678** (`csr_4721…`, the worked estimate, 4 priced options, one pro-approved). The funnel is split across two estimate records for one customer interaction, and the booking sits on a canceled `$0` record.

**Evidence (live data, 2026-06).**
- #7678 created `2026-05-25 19:26:33`; #7679 created `2026-05-25 19:34:15` (8 min later, same customer).
- One CallRail lead (`CAL019e…`, Google Local Services Ads, `gclid = NULL`, call started `19:20:10`) is correlated to **#7679 only**.
- `gads_conversion_uploads`: `booking_lead` on #7679; `qualified_lead` + `converted_lead` on #7678.
- Customer has **no** `customer_gclids` rows, **no** `booking_tags` gclid, **no** CallRail gclid.

**Root cause (two interacting layers).**
1. **CallRail correlation tiebreak.** `correlate_callrail_estimate()` binds a call to the customer's **most recent** estimate (`ORDER BY created_at DESC LIMIT 1`), ignoring which estimate the call actually concerned and ignoring `work_status`. With two estimates 8 minutes apart, the call bound to the newer one (#7679), which was later canceled.
2. **Per-estimate booking-lead discovery follows the call.** `get_pending_booking_lead_conversions()` flags an estimate as a booking lead via a per-estimate signal (`is_booking_form`, `booking_tags`, or a correlated `callrail_leads` row). #7679 carried the only signal; #7678 carried none → the booking lead landed on #7679 and #7678 got none.

Two aggravating properties: the correlation is **sticky** (`resync_callrail_estimates()` only refills `estimate_id IS NULL`, so it never re-points after a cancel), and **no stage excludes canceled/void estimates**.

**Blast radius.** Not yet quantified (open question below). Note that `booking_lead` carries a NULL value, so Google Ads still receives exactly one booking count per interaction regardless of which estimate it lands on; the value-bearing stages (qualified/converted) landed correctly here. The concrete harms are (a) internal pipeline-view incoherence (funnel split, booking on a canceled record) and (b) the edge case where a lead **books but never qualifies** — there its *only* conversion would sit on the wrong/canceled estimate.

**Does migration `20260526000002_booking_lead_repeat_customer_gclid.sql` fix this? No.** That migration (a) is not deployed, and (b) even if deployed would not help: its new branch is per-customer `EXISTS customer_gclids`, but this customer has zero GCLID rows (the LSA call had no gclid), so the branch can't fire. It is also purely additive — it never moves the booking off #7679, adds no canceled-estimate guard, and in the hypothetical where a `customer_gclids` row existed it would make *both* estimates eligible, producing a **second** booking lead (double-count) rather than consolidating onto the right one. That migration targets a different problem ([Issue #2](#issue-2--repeat-customer-estimate-discovered-but-out-of-googles-90-day-window-luckhardt-7534)): repeat customers whose GCLID was captured on a prior estimate.

**Candidate solutions (for later evaluation — not committed).**
- *Correlation tiebreak.* Prefer the estimate nearest the call's `call_started_at` rather than strictly newest; and/or exclude `work_status` canceled/void estimates from the candidate set. (In this case both would have picked #7678.)
- *Re-correlate on cancellation.* Allow `resync_callrail_estimates()` (or a trigger) to re-point a call when its bound estimate becomes canceled and a sibling active estimate exists.
- *Customer-level booking attribution.* Attribute one `booking_lead` per customer to a single chosen estimate (e.g. first active estimate), mirroring how qualified/converted already use customer-scoped first-touch. Larger discovery-layer change; must guard against double-counting.
- *Upstream dedup.* Prevent two estimates per booking in the HCP flow. Highest leverage but mostly outside this codebase.
- *Accept + document only.* If blast radius is negligible, accept the current Google-Ads-facing outcome and rely on the documentation already added to the architecture spec. (Current standing decision.)

**Open questions.**
- How many customers have a split/duplicate-estimate funnel, or a `booking_lead` sitting on a canceled estimate? (Needs a survey query before sizing any fix.)
- Are book-but-never-qualify leads on canceled estimates actually occurring, or is this purely theoretical?
- Why is migration `20260526000002` present on disk but unapplied — pending deploy, or abandoned?

### Issue #2 — Repeat-customer estimate discovered but out of Google's 90-day window (Luckhardt #7534)

**Symptom.** Estimate **#7534** (`csr_8c68d6a763ca493ca012978d207bcb40`, `work_status = pro canceled`) for customer `cus_1d218679c7584be7b76ecdcc14661a9b` (Wesley Luckhardt) is not discovered by `discover_pending_conversions()` at all — no `gads_conversion_uploads` rows exist for it. The customer is a known Google-Ads-sourced repeat customer; their GCLID was captured on a prior estimate (#5887) from a CallRail call in January, and lives in `customer_gclids`. The May follow-up estimate has no per-estimate attribution signal of its own, so today's discovery skips it silently. With the proposed migration `20260526000002` applied, discovery picks it up — but the resolved GCLID is ~115 days old at the time of the conversion event, so the upload step lands the row as `status = 'expired'` with `error_message = 'Outside Google Ads 90-day conversion window'`.

**Evidence (live data, 2026-06).**
- #5887 created `2026-01-07`, `lead_source = 'Online Booking'`, with one CallRail lead (`gclid = Cj0KCQiAgvPK…`, `call_started_at = 2026-01-15 14:26:29Z`). Its three `gads_conversion_uploads` rows all landed `status = 'expired'` with the same window message.
- `customer_gclids` row for this customer: one entry, `source = 'callrail'`, `first_seen_at = 2026-01-15`, sourced from the prepass against #5887.
- #7534 created `2026-05-10`, `is_booking_form = false`, `lead_source = NULL`, no `booking_tags`, no `callrail_leads` correlated by `estimate_id`. Its single `estimate_options` row is `approval_status = NULL`, `status = 'deleted'`, `total_amount = 0`.
- `gads_conversion_uploads` for #7534: **zero rows** of any conversion type.
- Simulating the proposed migration against live data returns #7534 with the January GCLID; gap between `cg.first_seen_at` and `e.created_at` is ~115 days.

**Root cause.** Two compounding constraints, not a bug:
1. **Per-estimate eligibility gates.** `get_pending_booking_lead_conversions()` keys eligibility on per-estimate signals (`is_booking_form`, `booking_tags`, `callrail_leads.estimate_id`). Repeat estimates from a known PPC customer that lack their own ad-touch signal are invisible to discovery. `qualified_lead` and `converted_lead` also exclude #7534, but correctly — `work_status = 'pro canceled'` and no `approved`/`pro approved` option with positive amount.
2. **Google Ads click-conversion window.** Even when discovery is fixed (migration `20260526000002`), the only GCLID available for this customer predates the conversion event by more than 90 days. Google's API rejects the click ID as expired. This is a property of Google's product, not a bug in this pipeline; there is no fresher GCLID to use.

**Blast radius.** From the simulation against live data, the migration unlocks **70 previously invisible repeat-customer estimates**. Of those, **64 fall within Google's 90-day click window** (will upload as `uploaded`) and **6 fall outside** it (will land as `expired`, same disposition as #7534 and the historical #5887 rows). The expired tail is small in absolute terms but unbounded in growth: every long-tenured customer's late follow-up estimate is a candidate. The harm is not in Google Ads (`expired` rows do not double-count or distort metrics there) but in the **dashboard pipeline view**: today these expired rows are styled with a muted clock icon ([`getPhaseConfig.tsx:116`](horizon-dashboard/src/components/conversions/lib/getPhaseConfig.tsx#L116)) that is easy to misread as "in progress / not yet uploaded" rather than "permanently un-uploadable by Google's rules". An operator looking at the pipeline cannot tell, at a glance, whether an expired row is a transient queue state or a terminal "we tried, Google said no".

**Does migration `20260526000002_booking_lead_repeat_customer_gclid.sql` fix this?** **Discovery: yes. Upload: no.** After the migration, #7534 enters the pipeline with the correct first-touch GCLID and a terminal `expired` disposition. The migration cannot make Google accept an old click — that limit is fixed at the platform level. This issue is therefore not really a *pipeline* issue once the migration is applied; it becomes a **dashboard clarity** issue.

**Candidate solutions (for later evaluation — not committed).**
- *Distinguish `expired` from transient states in the pipeline UI.* Replace the muted clock with a clearly terminal styling (e.g. a distinct color/badge such as "Expired — outside Google's 90-day window") and a tooltip explaining that the click is too old for Google to accept. The dashboard already has the `expired` status from the upload edge function; this is purely a presentation change in [`getPhaseConfig.tsx`](horizon-dashboard/src/components/conversions/lib/getPhaseConfig.tsx). (**Standing recommendation.**)
- *Surface a per-row reason chip.* Render `error_message` (`'Outside Google Ads 90-day conversion window'`) directly in the row, not just on hover/expand, so the cause is visible at a glance.
- *Aggregate counter.* In the pipeline header or summary, show a count of `expired` conversions alongside `pending` / `uploaded` / `failed`, so the expired tail is visible without scrolling.
- *Suppress discovery for out-of-window GCLIDs.* Add `AND cg.first_seen_at >= e.created_at - INTERVAL '90 days'` to the new branch in `get_pending_booking_lead_conversions()`. Hides the row entirely rather than surfacing it as expired. **Not recommended** — it loses the audit trail that "this lead was attributable but Google's rules prevented upload."
- *Accept + document only.* Treat `expired` as a known terminal state, rely on documentation. Lower bar than the UI work but leaves the misreading risk in place.

**Open questions.**
- How big is the steady-state `expired` cohort once migration `20260526000002` is applied? (Initial backfill: 6 of 70. Ongoing rate depends on repeat-customer cadence.)
- Are operators currently confused by `expired` rows, or is this a pre-emptive concern? (Needs a quick user check before sizing the UI work.)
- Should `expired` rows be filtered out of the default pipeline view (with an opt-in toggle) rather than re-styled in place?

### Issue #3 — Repeat-customer follow-up estimate: booking undiscovered today, all stages out-of-window after migration (Cross #7454)

**Symptom.** Estimate **#7454** (`csr_59b04a304551478a928f2dc2331ddc9e`, `work_status = needs scheduling`) for customer `cus_c8565fcd4f504861b05b0c3737e16fd5` (Sarah Cross) has zero `gads_conversion_uploads` rows. The customer's only stored GCLID dates from a CallRail call on a *prior* estimate (#7367), captured 2026-01-25 — already ~100 days old at #7454's creation on 2026-05-05.

**Evidence (live data, 2026-06).**
- #7367 created `2026-04-27`, `work_status = complete rated`. Its three `gads_conversion_uploads` rows are all `status = 'uploaded'`, `lifecycle = 'sent'` (with `gclid = NULL` on the rows — sent as enhanced/no-GCLID).
- `customer_gclids` row for this customer: `gclid = Cj0KCQiAm9fLBhCQARIsAJoNOcs…`, `source = 'callrail'`, `first_seen_at = 2026-01-25`, `estimate_id = csr_bd61a7b73e504b43b4213d25114bafec` (i.e. linked to #7367, not #7454).
- #7454 created `2026-05-05`, `is_booking_form = false`, no `booking_tags`, no `callrail_leads` with `estimate_id = #7454`. Its sole `estimate_options` row is `status = 'submitted for signoff'`, `approval_status = NULL`, `total_amount = 385800` (cents).
- `gads_conversion_uploads` for #7454: **zero rows** of any conversion type.
- Calling the deployed `get_pending_booking_lead_conversions()` against #7454: empty result. Calling the deployed `get_pending_qualified_lead_conversions()` and `get_pending_converted_lead_conversions()`: empty (work_status / approval gates not yet met — these would *eventually* fire).

**Root cause.** Same compounding constraints as [Issue #2](#issue-2--repeat-customer-estimate-discovered-but-out-of-googles-90-day-window-luckhardt-7534), but with all three stages in play (Luckhardt's qualified/converted were independently excluded by `pro canceled` / no approved option):
1. **booking_lead — per-estimate eligibility gate.** Deployed `get_pending_booking_lead_conversions()` keys on `is_booking_form` / `booking_tags` / `callrail_leads.estimate_id`. #7454 satisfies none of these. The repeat-customer branch added by migration `20260526000002` would discover it via `customer_gclids`, but the migration is unapplied (only `20260526000001` is present in `schema_migrations`; `pg_get_functiondef` confirms the function still has 3 OR branches and 2 COALESCE branches).
2. **qualified_lead and converted_lead — 90-day lookback on the `customer_gclids` branch.** Both already read `customer_gclids`, but filter `cg.first_seen_at >= e.updated_at - INTERVAL '90 days'` (converted: anchored to `MAX(eo.updated_at)` for approved options). Sarah's Jan-25 GCLID is outside that window for any May-2026+ event → the subquery returns NULL → discovery would create rows with `gclid = NULL`, same disposition as her #7367 uploads.

**Blast radius.** One concrete case today, but structurally identical to Issue #2's 70-estimate cohort. Every late follow-up estimate from a long-tenured PPC customer is a candidate. The harm is downstream and presentational: rows that *will* land as `expired` are not flagged distinctly from transient `pending` states in the dashboard, so an operator scanning the pipeline cannot tell at a glance that these are terminal "Google won't accept" outcomes vs. work still in progress.

**Does migration `20260526000002_booking_lead_repeat_customer_gclid.sql` fix this?** **Partial.** Applying it surfaces #7454's booking_lead with the Jan-25 GCLID; the upload step will then land it as `status = 'expired'` (>90 days). Qualified and converted are unaffected by that migration — they already query `customer_gclids` but apply the lookback window; when #7454 reaches `complete rated` and/or gets an approved option, their pending rows will be created with `gclid = NULL`. No code change makes Google accept the old click.

**Solution.**
- *Booking — apply the unapplied migration.* Deploy `20260526000002_booking_lead_repeat_customer_gclid.sql`. This is a deliverable, not a research item: the patch already exists on disk and is sized for a single deploy step. Once applied, #7454 (and the ~70 other repeat-customer estimates from the Issue #2 simulation) become visible to discovery; the ~6 of those with out-of-window GCLIDs land as `expired` per design.
- *All stages — flag `expired` clearly in the dashboard.* Distinguish `expired` from transient states in the pipeline view, so rows with an old/no-GCLID terminal disposition read as "permanently un-uploadable" rather than "in progress". Mechanically a presentation change in [`getPhaseConfig.tsx`](horizon-dashboard/src/components/conversions/lib/getPhaseConfig.tsx) (and any companion row/legend), matching the **standing recommendation** in Issue #2. Sarah's case strengthens the case for this UI work: every one of her #7454 stages can independently land in this state.

**Open questions.**
- Is migration `20260526000002` pending deploy, or stalled — and is there anything blocking it? (Carried over from Issue #1.)
- Should the dashboard distinguish `expired` rows that arrived *with* a GCLID (resolved but too old) from rows that arrived *without* one (qualified/converted with `gclid = NULL`)? Both are terminal but the cause is different.

### Issue #4 — CallRail calls bound to a non-adjacent sibling estimate, leaving channel = 'Other' (Lowe #7428)

**Symptom.** Estimate **#7428** (`csr_bbe73ab20d9247c59aa492da725ed560`, `is_booking_form = true`) for customer `cus_ab1c8bc4ef1d4bc5864bcb71e96952da` (Joshua Lowe) resolves to `channel = 'Other'` in `vw_conversion_candidates` even though the same customer placed two `'Google Local Services Ads'` CallRail calls ~3 minutes *before* #7428 was created. The calls — which should have classified #7428 as `GLS` via the taxonomy's CallRail rule ([20260507000001_lead_channel_taxonomy.sql:173-178](supabase/migrations/20260507000001_lead_channel_taxonomy.sql#L173-L178)) — are instead bound to a different sibling estimate (#7462) created two days later. As a result `call_agg.call_count = 0` for #7428 (lateral keyed on `cl.estimate_id = e.id`), the booking-form attribution chain has no `gclid`/`utm_source`/`hsa_src` and a `ref` that points to the company's own domain (Google SERP click signature `sa=X&ved=…`, not `google.com/localservices`), so the taxonomy falls through to step 7 → **Other**.

**Evidence (live data, 2026-06).** Customer Joshua Lowe's estimate + call timeline:
- 2026-05-03 19:25:50 — CallRail call (`CAL019def4ddaa1…`, `source = 'Google Local Services Ads'`, `duration = 36s`, `first_call = true`, `gclid = NULL`) → `estimate_id = csr_6796bd67…` (**#7462**).
- 2026-05-03 19:26:47 — CallRail call (`CAL019def4ebd18…`, same source, 45s) → `estimate_id = #7462`.
- 2026-05-03 **19:29:23** — Estimate **#7428** created (`is_booking_form = true`, single `booking_tag`: `ref = https://onyxelectricfl.com/?sa=X&ved=2ahUKEw…&nis=8&ch=1`; no `gclid`/`utm_source`/`utm_medium`/`hsa_src` tags). **~3 min after the calls.**
- 2026-05-05 21:41:26 — Estimate #7461 created (`lead_source = 'Reserve with Google'` → channel = `GMB`).
- 2026-05-05 21:44:21 — Estimate **#7462** created (`lead_source = 'Reserve with Google'`, `work_status = 'user canceled'`). **Calls bound here.**
- 2026-05-12 14:27:49 — CallRail call (`CAL019e1c9640bc…`, same source, 133s) → `estimate_id = #7462`.
- 2026-05-18 13:44:17 — Estimate #7606 created (no signals → `channel = 'Other'`).

`vw_conversion_candidates` for #7428: `channel = 'Other'`, `call_count = 0`, `callrail_sources = NULL`, `form_gclid = NULL`, `form_hsa_src = NULL`, `form_utm_source = NULL`, `form_ref = 'https://onyxelectricfl.com/?sa=X&ved=…'`.

**Root cause.** Same `correlate_callrail_estimate()` tiebreak as Issue #1 ([20260406000001_callrail_estimate_correlation.sql:88-92](supabase/migrations/20260406000001_callrail_estimate_correlation.sql#L88-L92)): `ORDER BY e.created_at DESC LIMIT 1` per customer, no consideration of `call_started_at` proximity or `work_status`. Compounded by `resync_callrail_estimates(p_force = true)` ([same migration:121-123](supabase/migrations/20260406000001_callrail_estimate_correlation.sql#L121-L123)), which nulls out `estimate_id` and re-fires the BEFORE trigger — so historical calls get *re-stamped* to whichever estimate is newest at resync time, sliding the 2026-05-03 calls forward onto #7462 even though #7428 already existed as a temporally-adjacent candidate. The taxonomy view then has no path to recovery: the lateral join is strictly `cl.estimate_id = e.id`, and the `ref`-based GLS rule only matches `google\.com/localservices` (the customer's own landing URL with Google SERP params does not match).

Distinct from Issue #1 in *manifestation*: Wydro split a single funnel across two estimates 8 minutes apart (booking on one, qualified/converted on another). Lowe leaves the originally-targeted estimate completely unattributed and parks all the signal on a later sibling that was itself later canceled. Both share the same correlation root cause.

**Blast radius.** Not yet quantified. Two distinct downstream harms beyond Issue #1's:
- **Channel taxonomy under-counts GLS.** `vw_gads_upload_reconciliation_daily`'s 4-bucket mapping ([20260507000001_lead_channel_taxonomy.sql:361-368](supabase/migrations/20260507000001_lead_channel_taxonomy.sql#L361-L368)) groups #7428 into `other` instead of `form` (where `GLS` maps), so reconciliation reporting drifts away from truth as repeat-customer LSA leads accumulate.
- **Stage attribution lands on a canceled record.** Any conversion on #7462 (which is `user canceled`) inherits the GLS signal that belonged to the active estimate. The booking_lead on #7428, if/when discovered, would inherit none of it.

**Does migration `20260526000002` fix this? No.** That migration's repeat-customer branch keys on `customer_gclids`, which is empty here — every CallRail row for this customer has `gclid = NULL` (LSA calls don't carry a GCLID), and there are no `booking_tags` GCLIDs either. The migration cannot fire, and even if it could, it wouldn't move the calls off #7462.

**Candidate solutions (for later evaluation — not committed).** This case strengthens the case for the **correlation tiebreak** candidate already listed under [Issue #1](#issue-1--booking-lead-attributed-to-a-canceled-duplicate-estimate-wydro-7679); no new candidate is introduced.
- *Time-proximity tiebreak.* Bind a call to the estimate whose `created_at` is closest to `call_started_at` (within a configurable window, e.g. ±48h), falling back to most-recent only when no estimate exists in that window. Would have routed all 3 of Lowe's calls to #7428.
- *Exclude canceled/void estimates from the candidate set.* Would have excluded #7462 even under the current "most-recent" rule, sliding the calls back to #7461 (still wrong, but at least GMB rather than the canceled GLS sibling) — useful as a complement to time-proximity, not a replacement.
- *Re-correlate when a call's bound estimate is canceled.* Inherited from Issue #1.
- *Stop nuking on resync.* Restrict `resync_callrail_estimates(p_force = true)` so it doesn't *demote* an originally-correct binding when a later sibling estimate appears — or remove the `p_force` path entirely once the trigger is improved.

**Open questions.**
- How many CallRail leads are bound to an estimate whose `created_at` is far from their `call_started_at`? (Survey query: `ABS(EXTRACT(EPOCH FROM (e.created_at - cl.call_started_at)))` distribution per customer-with-multiple-estimates. Needed before sizing the tiebreak fix.)
- For customers with clustered estimates from a single interaction window, should a call bind one-to-one (current model) or many-to-one across that cluster?
- What was the actual sequence here — did the BEFORE INSERT trigger originally bind these calls to a pre-#7428 estimate, or has `resync_callrail_estimates(true)` been run since (slowly walking the bindings forward as new estimates appear)? Either way the fix is the same, but the answer informs whether the resync function itself needs to change.

### Issue #5 — Fresh GCLID present but booking lead uploaded gclid-less: discovery fired before call correlation (Osmanski #7864)

**Symptom.** For customer `cus_4942339c882d4076ba7c4bb42a023a3e` (Craig Osmanski), estimate **#7864** (`csr_8adcd2922ed44b78a269159bb357c1b0`) has its single `booking_lead` conversion (`gads_conversion_uploads.id = 14507`) uploaded with **`gclid = NULL`** (`status = 'uploaded'`, `lifecycle = 'sent'`), even though **both** CallRail calls tied to this estimate carry a valid, in-window Google Ads GCLID and a `customer_gclids` row holds the same GCLID. Unlike Issues #2/#3 the GCLID is fresh (same-day) and unlike Issues #1/#4 it is correctly correlated to *this* estimate — it was simply not yet linked at the instant discovery ran.

**Evidence (live data, 2026-06).**
- #7864 created `2026-06-10 12:55:43` (via `hcp-booking`), `lead_source = 'Website'`, `work_status = 'user canceled'`, `is_booking_form = false`. (It was booked through the form — `hcp-booking` upserts `is_booking_form = true` — but the every-minute HCP estimates import later re-upserted the row and reset the flag to `false`. The current schedule-gate does not key on `is_booking_form`, so this does not affect eligibility, but it means the *commented-out* legacy `is_booking_form` signal would no longer help either.)
- Two `callrail_leads` rows, both `source = 'Google Ads'`, `medium = 'ppc'`, `campaign = '1-10 PIN [05/2024]'`, both `gclid = Cj0KCQjwlqTRBhCBARIsANrkrxjh2T7V6SYZM7CE8tBFH6tB1_h-XJJGzi_HWwCIFl3acFqBI6_hb3QaAl-BEALw_wcB`, now both `estimate_id = #7864`, `customer_id = cus_4942…`:
  - `CAL019eb18e…` — `call_started_at = 12:43:10`, `received_at = 12:45:01` (**before** the customer/estimate existed → `customer_id`/`estimate_id` NULL at insert).
  - `CAL019eb195…` — `call_started_at = 12:50:33`, `received_at = 13:15:02`.
- `customer_gclids`: one row for this customer, same GCLID, `source = 'callrail'`, `first_seen_at = 12:43:10` (note: `first_seen_at` is the *call* time, not the prepass insert time — the row is created by the prepass inside `discover_pending_conversions()` only once a `callrail_leads` row carries this `customer_id`).
- `booking_tags` for #7864: **empty** — no `gclid` tag was passed through the booking form.
- `gads_conversion_uploads` for #7864: exactly one row (`booking_lead`, `gclid = NULL`, `conversion_datetime = 12:55:43` = `created_at`, `uploaded_at = 14:22:22`). No `qualified_lead` / `converted_lead` rows.
- Cron run times (`cron.job_run_details`, 2026-06-10): `discover_pending_conversions()` (jobid 28, `*/15`) ran at `13:00:00.32`, `13:15:00.31`, `13:30:00.38`, `13:45:00.37`, `14:00`, `14:15`; `resync_callrail_estimates(false)` (jobid 27, `*/30`) ran at `13:00:00.32`, `13:30:00.39`, `14:00`. The 13:15 discover run started `13:15:00.31` — **2.3 s before** call 2 was even received (`13:15:02.6`).
- Live `pg_get_functiondef('get_pending_booking_lead_conversions()')` confirms the deployed gate is schedule+assignment with a 3-way GCLID COALESCE (`booking_tags` → `callrail_leads` by `estimate_id` → `customer_gclids` by `customer_id`) and a once-ever `NOT EXISTS (booking_lead row)` guard.

**Root cause — discovery/correlation ordering race plus a non-idempotent guard.** `booking_lead` discovery and GCLID resolution are bound to the *same* once-ever moment, and that moment can precede attribution:
1. **Discovery fires as soon as scheduled+assigned.** The estimate was created at 12:55:43 with a `schedules` row; the every-minute HCP import added an `estimate_assignments` row within a few minutes, satisfying the schedule gate by the `13:00:00.32` discover run. The row was enqueued there.
2. **At that instant, all three GCLID sources were empty.** `booking_tags` had no gclid; no `callrail_leads` row yet carried `estimate_id = #7864` (call 1 was received before the customer existed and was still unlinked; call 2 wasn't received until 13:15:02); and the prepass `INSERT INTO customer_gclids … FROM callrail_leads WHERE customer_id IS NOT NULL` found no call bearing this `customer_id` yet, so `customer_gclids` was still empty. COALESCE → NULL.
3. **The guard freezes the NULL.** Once the row exists, `NOT EXISTS (booking_lead row)` excludes the estimate from every later discover run. Call correlation completed afterwards (call 2 at 13:15:02; call 1 re-pointed by `resync_callrail_estimates()` at 13:30) and the 13:30 prepass populated `customer_gclids` — but discovery never re-resolves GCLID for an already-enqueued row, so it stayed NULL through the 14:22 upload.

In short: correlation eventually lands correctly, but discovery and GCLID resolution are a single non-repeatable event that fired first. CallRail-driven bookings are the natural trigger because the *call* often precedes the *estimate*, and `callrail_leads` inserted before the customer exists start life unlinked.

**Blast radius.** Not yet quantified (open question below). Because `booking_lead` carries a NULL value, Google still receives exactly one booking count — but gclid-less, so it is attributed only via enhanced/identifier-based matching, not click-level. Click-level attribution to the originating campaign (`'1-10 PIN [05/2024]'`) is lost for these. Candidate population: any booking where a CallRail call precedes estimate creation and the estimate becomes scheduled+assigned within the same ~15-minute discover cycle before correlation + prepass complete. (Distinct from the wrong-estimate cases in #1/#4 — here the calls are on the right estimate — and from the out-of-window cases in #2/#3 — here the GCLID is fresh and would upload cleanly if it had been resolved.)

**Does migration `20260526000002` fix this? No.** The deployed `get_pending_booking_lead_conversions()` already contains the `customer_gclids` COALESCE branch this issue would need; the problem is not a missing branch but *timing* — the branch resolves NULL because the prepass hadn't populated `customer_gclids` at discovery time, and the once-ever guard prevents re-resolution. No additive discovery branch helps; the fix must make GCLID resolution repeatable or defer it.

**Candidate solutions (for later evaluation — not committed).**
- *Re-resolve GCLID at upload time.* The upload pickup ([`google-ads-conversion-upload/pickup.ts:33-34`](supabase/functions/google-ads-conversion-upload/pickup.ts#L33-L34)) reads the frozen `gclid` straight off the row. For still-`queued` `booking_lead` rows with `gclid IS NULL`, re-run the same COALESCE (or read `customer_gclids` / `callrail_leads`) at send time, so a GCLID that arrived after discovery is picked up before upload. Smallest, most targeted fix.
- *Backfill pass in discovery.* Before the once-ever insert, `UPDATE gads_conversion_uploads SET gclid = … WHERE conversion_type = 'booking_lead' AND gclid IS NULL AND lifecycle IN ('queued','retrying')` from the resolver — i.e. make GCLID resolution idempotent even though *eligibility* stays once-ever.
- *Discovery settle delay.* Only discover `booking_lead` for estimates whose `created_at` is older than a grace window (e.g. ≥30–60 min), giving CallRail correlation + the prepass time to land before the GCLID is frozen. Simple, but delays all booking conversions and doesn't help if correlation lags beyond the window.
- *Order the tick.* Ensure `resync_callrail_estimates()` + the `customer_gclids` prepass run (and commit) before `booking_lead` discovery within the same cycle, so a just-correlated call is visible to the COALESCE. Reduces but does not eliminate the race (a call received mid-cycle still misses).
- *Accept + document only.* If blast radius is negligible and enhanced-conversion matching recovers most value, accept the gclid-less upload and document it.

**Open questions.**
- How many `booking_lead` rows have `gclid = NULL` while a GCLID is now resolvable from `callrail_leads` (by `estimate_id`) or `customer_gclids` (by `customer_id`)? (Survey query before sizing — this is the direct blast-radius measure and the validation set for the "re-resolve at upload" fix.)
- Does Google's enhanced-conversion / identifier-based matching recover campaign attribution for these gclid-less booking leads, or is click-level attribution fully lost?
- Should `booking_lead` discovery and GCLID resolution be decoupled — eligibility once-ever, GCLID re-resolvable until the row is actually sent?
- Is the HCP import resetting `is_booking_form` to `false` on booking-form estimates a separate data-integrity bug worth its own entry, independent of this attribution race?

### Issue #6 — Qualified-lead value frozen at discovery; option repriced afterward uploads stale value (Martija #7865)

**Symptom.** For customer `cus_35c73da6203848339991d0a712d7bf60` (Kerien Martija), estimate **#7865** (`csr_6aa510a2c838474591992676996eb29d`, `work_status = complete unrated`) has its `qualified_lead` conversion (`gads_conversion_uploads.id = 14535`) uploaded with **`conversion_value = 1260`**, while the estimate's single option is priced **$4,990** (`total_amount = 499000` cents). The upload was fully successful (`status = 'uploaded'`, `lifecycle = 'sent'`, fresh in-window GCLID, batch accepted 5/5, HTTP 200) — unlike Issues #1–#5 nothing failed, expired, or landed on the wrong estimate. Google simply received a value ~4× lower than the option's price, because the price was edited *after* discovery snapshotted it.

**Evidence (live data, 2026-06).**
- #7865 created `2026-06-10 13:06:35`; appointment completed `2026-06-11 12:36:31` (`work_timestamps.completed_at`, matching the row's `conversion_datetime` exactly; the estimate's own `updated_at` is `2026-06-10 13:19:27`, so the datetime came from the work-timestamp branch of the COALESCE).
- Single `estimate_options` row (`est_457dbdd887ae47dabba9d944336f2d9a`, "Option #1"): `total_amount = 499000`, `status = 'submitted for signoff'`, **`updated_at = 2026-06-11 13:39:18`** — the reprice landed between discovery and upload.
- `gads_conversion_uploads` row 14535: `conversion_value = 1260.0000000000000000` — *exactly* `126000 / 100`, i.e. a single option priced **$1,260** at snapshot time. The AVG math being exact is the smoking gun; there is no option-price history table to show the prior value directly.
- `cron.job_run_details` (jobid 28, `discover_pending_conversions()`, `*/15`): runs at `12:30`, `12:45`, `13:00`, `13:15`, `13:30`, `13:45`, `14:00` on 2026-06-11, all succeeded. The estimate became eligible at 12:36:31; row ID ordering (14535 precedes 14536, whose `conversion_datetime` is `13:11:58` and was inserted by the 13:15 run) pins the insert to the **12:45 or 13:00 run** — before the 13:39:18 reprice.
- Upload batch `3787cc3e-f663-4556-b3a7-f4d7ee96604e` (`sent_at = 2026-06-11 14:00:01`, hourly jobid 29): `request_body` contains `"conversionValue": 1260, "currencyCode": "USD", "orderId": "csr_6aa510a2…"` — Google accepted $1,260.
- No `converted_lead` row exists yet (option not approved); when it fires it will recompute from the then-current option set, so the *converted* stage would self-correct — the stale value is specific to the qualified stage.

**Root cause — value snapshotted once-ever at discovery, never re-read.** Same architectural defect as [Issue #5](#issue-5--fresh-gclid-present-but-booking-lead-uploaded-gclid-less-discovery-fired-before-call-correlation-osmanski-7864)'s "frozen-at-discovery" guard, applied to a different field:
1. **Discovery computes the value inline.** `get_pending_qualified_lead_conversions()` returns `COALESCE(AVG(eo.total_amount)/100, 0)` evaluated at detection time, and `discover_pending_conversions()` writes it into the queue row with `ON CONFLICT (estimate_id, conversion_type) DO NOTHING` — the row is never revisited.
2. **The reprice arrived after the snapshot.** The appointment completed 12:36:31 with the option at $1,260; discovery (12:45/13:00) froze that value; the rep repriced to $4,990 at 13:39:18 ("submitted for signoff").
3. **The uploader is value-blind.** `pickup.ts` reads the frozen `conversion_value` straight off the row; the hourly 14:00 run sent the stale $1,260.

Distinct from Issue #5 in failure mode, not just field: there the correct data *existed but hadn't been linked yet* (a settle delay or tick reordering shrinks the race); here the snapshot was **correct when taken and the source changed afterward**. Post-appointment repricing is normal sales workflow, so no grace window eliminates this — only making value resolution repeatable (or restating after the fact) does.

**Blast radius.** Not yet quantified (open question below). The harm is **monetary, not attributional**: a wrong `conversionValue` feeds Google's value-based bidding — here a 4× understatement; an edit in the other direction would overstate. Unlike Issues #1–#5 the damage is invisible in the dashboard: the row reads `uploaded`/`sent`, i.e. success. Candidate population: any estimate whose option prices change between appointment completion (+ ≤15-min discovery) and… ever — the divergence is permanent. The same mechanism applies to `converted_lead` values if options are edited after approval-time discovery.

**Does migration `20260526000002` fix this? No.** It only adds a repeat-customer GCLID branch to *booking* discovery; it touches neither value computation nor re-resolution.

**Candidate solutions (for later evaluation — not committed).**
- *Re-resolve `conversion_value` at upload time.* Generalize Issue #5's "re-resolve at upload" candidate: for still-`queued` value-bearing rows, recompute `AVG(estimate_options.total_amount)/100` at send time (the pickup query already joins `estimates`). Closes the discovery→upload gap (here ~1 h) but not post-upload edits.
- *Restate after the fact via Google Ads conversion adjustments.* Upload a `RESTATEMENT` adjustment keyed on `orderId` (= estimate ID) when a sent row's value diverges from the current option average. The only mechanism that catches edits made *after* upload; value restatements exist in Google's API where GCLID fixes do not. Could remediate #7865 itself ($1,260 → $4,990).
- *Backfill pass in discovery.* Before the once-ever insert, `UPDATE` still-queued value-bearing rows whose stored value diverges from the current recomputation — value resolution becomes idempotent while eligibility stays once-ever (mirrors Issue #5's backfill candidate).
- *Accept + document only.* If most repricing happens before completion or the aggregate value drift is small, accept and document.

**Open questions.**
- Blast radius survey: how many sent `qualified_lead` / `converted_lead` rows have `conversion_value` ≠ the current `AVG(estimate_options.total_amount)/100` for their estimate, and what is the aggregate dollar drift? (Direct sizing for both the upload-time fix and the restatement backlog.)
- Does the qualified-stage value materially drive bidding, or does `converted_lead` dominate value-based strategies? (If the latter, the converted stage's natural self-correction may cap the harm.)
- Should value resolution — like Issue #5's GCLID resolution — be decoupled from once-ever eligibility and stay re-resolvable until the row is sent? (Shared design decision; the two issues should likely graduate together.)
- Is `AVG` across all options (including $0 ones) the right value semantics for a qualified lead at all, or should it be e.g. the max/likely option? (Pre-existing design choice; surfaced here because the snapshot froze it.)

## Capabilities

### New Capabilities
<!-- None committed in research phase. Likely future candidates, to be defined when an issue graduates into an implementation change:
     callrail-correlation-tiebreak, booking-lead-cancellation-guard, dashboard-expired-conversion-clarity. -->
- _None — research phase. Capabilities will be defined per-issue when one graduates to implementation._

### Modified Capabilities
<!-- None yet. Note: pipeline-stage-booking and full-stack-architecture already document current behavior. -->
- _None._

## Impact

- **Documentation only in this phase.** No code or schema changes.
- **Components referenced** (for future fixes, not touched now): `correlate_callrail_estimate()` trigger, `resync_callrail_estimates()`, `get_pending_booking_lead_conversions()`, and the `callrail_leads` ↔ `estimates` correlation. The behavior is already documented in `openspec/specs/full-stack-architecture/spec.md` (Stage 7 multi-estimate caveat, Stage 9a).
- **Dependency note:** migration `20260526000002` is unapplied and does not address any issue here; tracked as an open question, not a fix.
