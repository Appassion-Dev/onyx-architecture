## Context

Diagnostic queries against `gads_conversion_uploads` revealed two structural defects in the Google Ads conversion pipeline that together degrade a meaningful number of estimates' attribution to Google Ads:

- **Cohort A**: converted but no qualified row was ever discovered. The majority are stuck at `estimates.work_status = 'created job from estimate'`, which is outside the qualified gate's allowlist `('complete rated','complete unrated')`. The qualified stage uses estimate `work_status`; the converted stage uses option `approval_status` — they are gated on different signals from the same lifecycle and drift apart.
- **Cohort B**: qualified row exists with `gclid IS NULL`. Causes are layered:
  1. The current resolver picks the **oldest** `customer_gclids` entry (`ORDER BY first_seen_at ASC LIMIT 1`) within a 90-day window. When the oldest is stale, it gets filtered out and the resolver returns NULL even when fresher in-window GCLIDs exist for the same customer.
  2. Discovery never re-resolves an existing row (`NOT EXISTS` gate against `gads_conversion_uploads`). Once NULL is written, NULL stays.
  3. The May 11 cleanup migration NULLed stale GCLIDs but added no re-resolution path, locking those rows in the NULL state.
  4. The upload cron runs frequently enough that pending rows commit to Google Ads as enhanced-conversion-only before late-arriving CallRail/booking_tag data has populated `customer_gclids`.

For the sample estimates investigated, every available resolver strategy (ASC, DESC, estimate-first, oldest-unfiltered) returns the *same correct GCLID* — the resolver design choice is not the cause of those NULLs. The proximate causes there are (1) the v2 cutover race writing NULL on first insert and (2) the qualified gate excluding `'created job from estimate'`.

This change addresses all four root causes at once because they are mutually reinforcing: fixing the gate without fixing re-attribution still leaves Cohort B; fixing re-attribution without slowing uploads still races; fixing uploads without re-attribution still has nothing to re-resolve to.

## Mapping to the seven proposal points

The seven changes enumerated in `proposal.md` map onto the design decisions below as follows. Spec deltas and `tasks.md` use the same numbering.

| # | Proposal point | Design decisions | Affected capabilities |
|---|---------------------------------------------------------------|------------------|------------------------------------------------|
| 1 | Rewrite resolver — newest in-window, never NULL when fresh    | Decision 3       | `customer-gclid-attribution`                   |
| 2 | Re-attribution pass for qualified/converted in discovery      | Decisions 4, 6   | `conversion-populate`, `customer-gclid-attribution` |
| 3 | Reduce upload cron to once per day                            | Decision 5       | `conversion-upload`                            |
| 4 | Qualified gate = "estimate has a priced option"               | Decisions 1, 8   | `pipeline-stage-qualified`                     |
| 5 | Converted gate = "a job exists for the estimate"              | Decisions 2, 8   | `pipeline-stage-converted`                     |
| 6 | Per-stage GCLID badge on the Conversions page                 | Decision 11      | `conversions-gclid-tag`                        |
| 7 | Resolve GCLID once per estimate per discovery, share across 3 stages (with per-stage window check at upload) | Decisions 9, 10  | `customer-gclid-attribution`, `conversion-populate`, `conversion-upload` |

## Goals / Non-Goals

**Goals:**
- Eliminate the gate asymmetry between qualified and converted by re-keying both gates on objective lifecycle events (priced option exists; job exists) rather than secondary status fields that lag behind reality.
- Replace the oldest-in-window GCLID selection with newest-in-window so a stale historical click does not suppress a usable fresh one.
- Make NULL-gclid pending rows recoverable by adding a re-attribution pass to discovery.
- Give the discovery + re-attribution loop time to settle before uploads commit by reducing upload cron frequency to once per day.
- Backfill existing NULL-gclid `pending` rows once at deploy time so the historical defect cohort is recovered along with the future one.

**Non-Goals:**
- Reconciling already-uploaded fossil rows whose status is `'uploaded'`. Once a conversion is sent to Google Ads we cannot un-send it; we only fix what is still recoverable (`status = 'pending'` and not yet committed).
- Changing GCLID resolution for the booking_lead stage. Booking uses per-estimate `booking_tags`/`callrail_leads` lookup and is working correctly.
- Introducing a new `customer_gclids` source beyond `booking_tags` and `callrail_leads`.
- Changing the 90-day click-lookback window itself. Google Ads enforces this at the API level; we only change *which* in-window GCLID we pick.
- Enhanced-conversion behavior for rows that genuinely have no resolvable GCLID. Those continue to flow as today.

## Decisions

### Decision 1: Qualified gate becomes "any priced option exists" — implements proposal point #4
The qualified gate is changed from `e.work_status IN ('complete rated','complete unrated')` to `EXISTS (estimate_options eo WHERE eo.estimate_id = e.id AND eo.total_amount > 0)`. The `work_status` check is dropped entirely.

**Rationale:** Qualified represents "this lead has measurable scope" — semantically closer to option pricing than to job rating. The current gate makes qualified arrive *after* converted in many lifecycles (because the estimate's own work_status only flips to `'complete rated'` once the job is rated, which often happens days after conversion). The new gate fires at the moment the lead is genuinely qualified.

**Alternatives considered:**
- Keep `work_status` and *also* fire when options are approved → still leaves the asymmetry in place; just adds an OR.
- Use `approval_status IN ('approved','pro approved')` to mirror the current converted gate → would make qualified and converted near-simultaneous; loses the funnel-stage distinction.

### Decision 2: Converted gate becomes "a job exists for the estimate" — implements proposal point #5
The converted gate is changed from `EXISTS (estimate_options.approval_status IN ('approved','pro approved'))` to `EXISTS (jobs WHERE jobs.original_estimate_id = e.id)`. The conversion_value is the most-recent job's `total_amount / 100.0`; the conversion_datetime is that job's `updated_at`; the `job_id` column on the upload row references that job.

**Rationale:** A job existing is the unambiguous, downstream-of-everything signal that the estimate converted into work. Option approval status is a leading indicator that can be reversed (a customer can decline after initial approval) and is sometimes set without a job being created. Job existence is what HCP itself uses as the conversion event.

**Alternatives considered:**
- Keep approval_status → leaves the qualified/converted gates checking different things in the same lifecycle, which is the current bug.
- Require job to be in a specific completion status → reproduces the qualified-gate problem at the converted layer.

### Decision 3: Resolver selects newest in-window, not oldest — implements proposal point #1
The customer-scoped GCLID resolver used by qualified and converted changes from:

```sql
ORDER BY first_seen_at ASC LIMIT 1
```

to:

```sql
WHERE first_seen_at >= conversion_datetime - INTERVAL '90 days'
ORDER BY first_seen_at DESC LIMIT 1
```

The 90-day filter is retained (it is a Google Ads API constraint). The selection within the eligible set flips to last-touch.

**Rationale:** The current ASC-then-filter pattern produces NULL whenever the oldest GCLID is the only one outside the window, even when newer in-window GCLIDs exist. DESC-then-filter cannot produce that failure mode: if any in-window GCLID exists for the customer, the resolver returns one. For multi-GCLID customers, last-touch is also more consistent with what Google Ads is most likely to still recognize at upload time.

**Alternatives considered:**
- Oldest in-window (`ASC` with the same `WHERE` clause) → eliminates the worst failure mode but still picks the most-likely-to-age-out GCLID.
- Estimate-first with customer fallback → reasonable but reintroduces the case where two estimates for the same customer get attributed to different GCLIDs; harder to reason about for analytics.

### Decision 4: Discovery includes a re-attribution pass for NULL-gclid pending rows — implements proposal point #2
Both `discover_pending_conversions()` and `discover_pending_conversions_for_estimate()` gain a step (after the customer_gclids pre-pass, before the per-stage discovery) that runs:

```sql
UPDATE gads_conversion_uploads u
SET gclid = (
    SELECT cg.gclid FROM customer_gclids cg
    JOIN estimates e ON e.id = u.estimate_id
    WHERE cg.customer_id = e.customer_id
      AND cg.first_seen_at >= u.conversion_datetime - INTERVAL '90 days'
    ORDER BY cg.first_seen_at DESC LIMIT 1
)
WHERE u.status = 'pending'
  AND u.gclid IS NULL
  AND u.conversion_type IN ('qualified_lead','converted_lead');
```

Only `pending` rows are touched. `uploaded`/`expired`/`skipped`/`failed` rows are not retroactively modified.

**Rationale:** This breaks the "NULL is sticky" lifecycle described in Cohort B without changing the discovery resolver itself. It also handles future cases naturally — if a CallRail row arrives a day after qualified discovery, the next discovery pass picks it up.

**Alternatives considered:**
- Drop the `NOT EXISTS` gate in the discovery resolver entirely so existing rows get re-evaluated → far broader blast radius; would also re-evaluate value/datetime, not just gclid.
- Trigger-based re-attribution on `customer_gclids` insert → operationally heavier; adds row-level processing to a high-volume insert path.

### Decision 5: Upload cron reduced to once per day — implements proposal point #3
The `google-ads-conversion-upload` cron schedule is reduced from its current cadence to once per day (suggested: 09:00 ET, after the morning discovery sweep has completed).

**Rationale:** The discovery + re-attribution loop only helps if late-arriving attribution data has time to land before the upload commits. With uploads running once daily, a CallRail webhook arriving hours after a form submission still has a chance to populate `customer_gclids` and be picked up by re-attribution before the next upload. Faster cadence races the data and forces enhanced-conversion-only uploads.

**Alternatives considered:**
- Twice daily → modest improvement but still loses CallRail rows that arrive overnight relative to the morning upload.
- Hourly with a maturity gate (e.g., only upload rows older than N hours) → equivalent in effect to daily, but with more moving parts.
- Keep current cadence and rely solely on re-attribution → re-attribution can only fix `pending` rows; once uploaded, the gclid is locked in Google Ads.

### Decision 6: One-time backfill at deploy time — supports proposal point #2
A migration runs a single `UPDATE` equivalent to the re-attribution pass, scoped to all existing `pending` rows. This recovers the historical Cohort B (~4,905 qualified rows + however many converted rows have the same shape) in one pass.

**Rationale:** Without the backfill, cohort B remains broken until each row happens to be touched by a future discovery cycle — which never happens for `pending` rows under the current `NOT EXISTS` gate. Re-attribution is added to discovery, but discovery only inserts; the backfill provides the matching update for already-discovered rows.

### Decision 7: No retroactive reconciliation of uploaded rows — boundary on points #1, #2, #4, #5
Rows with `status = 'uploaded'` are left untouched, even if the new gate definitions would no longer produce them or the resolver would now return a different gclid.

**Rationale:** Once an event is uploaded to Google Ads, it exists in the Ads conversion ledger. Modifying our local row does not reach back to Google. The only honest options are (a) treat the local row as the historical record of what we sent and leave it, or (b) add a separate `superseded_at` column to track which rows would no longer fit current logic. Option (a) is simpler and what we choose. Future audits can join against the current gate definitions to detect fossils explicitly.

### Decision 8: Use `e.updated_at` and the most-recent job's `updated_at` as the conversion_datetime anchor — supports proposal points #4 and #5
For the new qualified gate (priced option), `conversion_datetime` continues to use `e.updated_at` — this is the closest available signal to "when the option was priced," because options don't carry a separate `priced_at` column. For the new converted gate (job exists), `conversion_datetime` becomes `MAX(j.updated_at)` across jobs for the estimate.

**Rationale:** Keeps the existing column semantics. The 90-day window math and the existing `idx_gads_pending_datetime` partial index continue to work without schema change.

### Decision 9: Resolve GCLID once per estimate per discovery run, share across stages — implements proposal point #7

The GCLID resolver is hoisted out of `get_pending_qualified_lead_conversions()` and `get_pending_converted_lead_conversions()` and called once per estimate per discovery run. The resolved value is written to all three stage rows (booking, qualified, converted) for that estimate, so the three rows always carry the same `gclid` for a given customer/estimate within a single discovery cycle.

The resolver itself is the same DESC newest-in-window query from Decision 3:

```sql
-- Per-estimate canonical GCLID for a discovery run.
-- Anchor: MAX(stage_dt) so we pick the GCLID most likely to still validate
-- against Google Ads' click cache for the latest active stage.
SELECT cg.gclid
FROM customer_gclids cg
WHERE cg.customer_id = (SELECT customer_id FROM estimates WHERE id = p_estimate_id)
  AND cg.first_seen_at >= (
        GREATEST(
          (SELECT e.updated_at FROM estimates e WHERE e.id = p_estimate_id),
          (SELECT MAX(j.updated_at) FROM jobs j WHERE j.original_estimate_id = p_estimate_id)
        )
      ) - INTERVAL '90 days'
ORDER BY cg.first_seen_at DESC
LIMIT 1;
```

Concretely the discovery flow becomes:

```
discover_pending_conversions_for_estimate(eid)
        │
        ▼
   resolve_estimate_gclid(eid)        ← runs ONCE per estimate
        │
        ▼
   GCLID_X (or NULL)
        │
   ┌────┼────┐
   ▼    ▼    ▼
 book  qual  conv                     ← all three stage rows get GCLID_X
```

The booking-stage discovery continues to *prefer* per-estimate signals (`booking_tags`/`callrail_leads`) when populating `customer_gclids` via the pre-pass — that part is unchanged. What changes is the read side: once `customer_gclids` is up to date, the canonical GCLID for the estimate is computed once and reused.

**Rationale:**

- The GCLID is a property of the lead (the customer's click context), not of the funnel stage. Three stages firing for the same estimate should not disagree about which click attributed the lead — it's an analytical and bidding-signal liability when they do.
- Coherent stage GCLIDs make Decision 1 from thread #1 (per-stage badge) tautologically consistent: badge and column total now read the same data, and within a single discovery run the three stage badges for one estimate agree.
- Hoisting the resolver also halves the number of subqueries against `customer_gclids` per estimate (one call instead of two-or-three).

**Anchor choice (MAX over MIN):**

- **MAX** = anchor to the latest stage's `conversion_datetime` (so for an estimate with booking on Day 0, qualified on Day 30, converted on Day 90, the 90-day window cutoff is Day 0 = converted_dt − 90).
- **MIN** would anchor to the earliest stage, narrowing the eligible set.
- We pick MAX because more uploads succeed and because Google Ads validates uploads against its current click cache at upload time; the latest stage is the one most likely to still be live in Ads. The trade-off is that we may pick a GCLID that the booking stage's own 90-day check (Decision 10) then drops at upload — that's correct behavior, not a regression.

**Cross-run coherence:** within a single discovery run, the three stages are guaranteed to share a GCLID. Across discovery runs (e.g., booking discovered on day 1, converted discovered on day 5), the resolver may return a different value if `customer_gclids` has changed in between — the re-attribution pass (Decision 4) extends to fix this: when re-attribution updates a NULL gclid, it MAY also be permitted to overwrite a stale-by-newer-discovery gclid on a `pending` row, but we explicitly defer that broader re-write to a future change. For now: re-attribution touches NULL only; the canonical resolver runs at insert time, and stages discovered together share a value.

**Alternatives considered:**

- Persistent `estimate_attributions` table with the canonical gclid — structurally cleaner across runs, but introduces a new sync surface between that table and `gads_conversion_uploads.gclid` (which the upload function reads). Out of scope for this change; revisit if cross-run divergence proves to be a practical problem.
- Anchor on MIN (earliest stage) for first-touch purity — rejected; reduces the eligible set and biases toward stale GCLIDs.
- Anchor on `now()` — rejected; the conversion event timestamp is what Google Ads validates against, not the upload moment.

### Decision 10: Per-stage 90-day window check enforced at upload time — implements proposal point #7

Because the resolver in Decision 9 anchors on `MAX(stage_dt)`, the chosen GCLID may be in-window for the converted stage but out-of-window for the booking stage (if booking happened > 90 days before the GCLID's `first_seen_at`, or vice versa). The upload edge function `google-ads-conversion-upload` SHALL, for each row it sends, re-check the stored GCLID against the row's own `conversion_datetime` and the GCLID's `customer_gclids.first_seen_at`. If the GCLID is out of window for *that stage*, the function SHALL omit the GCLID from the outbound API payload (sending the row as enhanced-conversion-only) WITHOUT modifying the stored row.

```
upload row {stage=booking, conversion_datetime=Day0, gclid=GCLID_X (first_seen Day 30)}
   ↓
   first_seen Day 30 - Day 0 = 30 days  → in window?
   No: 30 days AFTER conversion_datetime is also out of window
   (window is [conversion_datetime - 90d, conversion_datetime])
   ↓
   send payload WITHOUT gclid; row stays as-is in DB with GCLID_X
```

**Rationale:**

- Keeps Decision 9's "single canonical GCLID per estimate" property at the storage layer (badges and analytics see one value per estimate) while honoring Google Ads' API-level constraint at the wire layer.
- Avoids a destructive write at upload time. If a future re-attribution run finds a better in-window GCLID for the affected stage, it can update the row; we don't lose information by overwriting at upload.
- The dashboard can compare `gads_conversion_uploads.gclid` against `customer_gclids.first_seen_at` to surface "stored GCLID, but uploaded as enhanced-conversion-only because it was out of window for this stage" for audit purposes — a future enhancement, not in scope here.

**Alternatives considered:**

- Resolve per-stage at discovery (current behavior pre-Decision 9) — restores stage incoherence; rejected.
- Overwrite the stored gclid to NULL at upload time when out-of-window — destructive; loses the canonical-per-estimate property; rejected.
- Use the GCLID anyway and let Google reject — wastes Ads API budget on guaranteed-failed requests; rejected.

### Decision 11: Per-stage GCLID badge on the Conversions page — implements proposal point #6

In the Conversions page (`horizon-dashboard/src/components/pages/ConversionsPage.tsx`), the per-row GCLID badge SHALL render based on the active conversion mode:

| Mode            | Badge data source                         | Badge label / content                          |
|-----------------|-------------------------------------------|------------------------------------------------|
| `pre-discovery` | `row.all_gclids` (estimate-wide pool)     | `GCLID ×N` (current behavior, unchanged)       |
| `booking`       | `row.booking_gclid` (single value or NULL)| `GCLID` when set; hidden when NULL             |
| `qualified`     | `row.qualified_gclid`                     | `GCLID` when set; hidden when NULL             |
| `converted`     | `row.converted_gclid`                     | `GCLID` when set; hidden when NULL             |

The badge tooltip in stage modes shows the single GCLID value in monospace. In `pre-discovery` mode it continues to list all values from `all_gclids`.

When the badge is hidden in a stage mode (because that stage's stored gclid is NULL), the row SHALL still display a small attribution hint when `row.all_gclids` is non-empty, e.g., a muted "n in pool" indicator with a tooltip listing the pool. This preserves the diagnostic value of "we have GCLIDs for this customer, just not on this stage row" without conflating it with the per-stage badge.

**Rationale:**

- Coherence with the column-level GCLID totals (which read `*_gclid` per stage). Today the badge says "this estimate has 2 GCLIDs in its pool" while the column says "0 of these qualified rows have a gclid" — the two reads measure different things, and Decisions 9/10 above make the per-stage value the meaningful one.
- The badge becomes a per-row instance of the same metric the column header shows. They sum trivially; off-by-one debugging stops being a thing.
- The pool-hint preserves the existing diagnostic capability without overloading the primary badge.

**Alternatives considered:**

- Show both badges (per-stage + pool) side by side — visually noisy; double the click target ambiguity; rejected.
- Render a coloured "matches pool" / "drift from pool" tag — interesting but adds taxonomy that's hard to read at row density; rejected for this change, can revisit.
- Only render the per-stage badge with no pool hint — loses the diagnostic. The pool-hint is small and only appears when relevant.

**Data flow note:** `vw_conversion_candidates` already exposes `booking_gclid`, `qualified_gclid`, `converted_gclid`, and `all_gclids`. No view or table change is needed for the badge fix — this is a pure client-side update tied to `MODE_CONFIG[conversionMode]`.

## Risks / Trade-offs

- **[Risk] Conversion event timing in Google Ads shifts earlier** → Smart Bidding models will see qualified events firing at priced-option creation rather than at job rating. Brief learning-period turbulence is expected. Mitigation: deploy on a Monday so a full week of new signal accumulates before evaluating; document the change in the marketing ops log.

- **[Risk] Backfill could re-attribute large batches incorrectly if `customer_gclids` itself is wrong** → Mitigation: the backfill uses the same resolver as future discovery, so its correctness is identical to the resolver's. Run on a copy first; the UPDATE is idempotent (re-running with the same `customer_gclids` produces the same result) and can be scoped by date.

- **[Risk] DESC selection may overcredit remarketing** → A customer who clicked an ad once long ago and again via remarketing yesterday will now be attributed to the remarketing click. This may not match every marketing team's preferred attribution model. Mitigation: this is a deliberate policy choice documented in Decision 3; can be revisited as a separate change if needed.

- **[Risk] Daily upload cadence delays good rows by up to 24 hours** → A row discovered at 10:00 with a valid GCLID now waits until the next morning to upload. Mitigation: 24h is well within the 90-day Google Ads window; no rows expire from this delay alone.

- **[Risk] New converted gate (job exists) may fire for jobs that get cancelled later** → If a job is created and then cancelled, we will already have uploaded a converted_lead. This matches HCP's own conversion semantics. Mitigation: none needed; this is the intended definition.

- **[Risk] Existing `vw_conversion_candidates` view has columns derived from the old gate definitions** → If any consumer of the view relies on the prior qualified/converted semantics, they may see different rows than before. Mitigation: audit the view and dependent dashboards as part of the implementation; the view's pivot of `gads_conversion_uploads` rows is unchanged in shape.

- **[Trade-off] Larger qualified cohort means more uploads to Google Ads** → Recovering ~1,082 missing qualified events plus all future similarly-shaped estimates increases API call volume. Daily-instead-of-frequent cadence keeps total call count manageable.

- **[Trade-off] No history-trail for re-attribution** → When the re-attribution pass updates a row's gclid, no audit row records the prior value. If this becomes important for forensics, a separate `gads_conversion_uploads_audit` table can be added later; for now it is out of scope.

## Migration Plan

1. **Deploy migrations in order** (single `supabase db push`):
   - Rewrite `get_pending_qualified_lead_conversions()` (new gate + DESC in-window resolver)
   - Rewrite `get_pending_converted_lead_conversions()` (new gate + DESC in-window resolver)
   - Rewrite `discover_pending_conversions()` and `discover_pending_conversions_for_estimate()` to include the re-attribution pass after the customer_gclids pre-pass
   - One-time backfill UPDATE for existing `pending` NULL-gclid rows
   - Optional: refresh `vw_conversion_candidates` if any computed column depends on the old gate semantics
2. **Update upload cron schedule** in `supabase/config.toml` (or wherever cron is configured) to once daily.
3. **Update or add pgTAP tests** under `supabase/tests/`:
   - Qualified gate fires on priced option, not on `work_status`
   - Converted gate fires on job existence
   - DESC in-window resolver returns newest in-window GCLID; returns NULL only when none in window
   - Re-attribution pass updates NULL pending rows when `customer_gclids` has an in-window entry
   - Re-attribution pass does NOT touch `uploaded`/`expired`/`skipped` rows
4. **Verify locally** by running discovery against a representative dataset and comparing pre/post NULL-gclid counts.
5. **Hand the deploy to the user** per the safety rules — do not run `supabase db push` against remote, do not deploy edge functions.

**Rollback strategy:** Each migration is a `CREATE OR REPLACE FUNCTION`, so reverting is a matter of re-applying the prior migration's function bodies. The backfill UPDATE is not reversible (we don't store the prior gclid values), but rolling back the function definitions does restore the prior behavior for new rows. If a rollback is needed, the practical recovery is: (a) re-deploy the prior function definitions, (b) accept that the backfill remains applied (which is strictly better than the pre-backfill state), and (c) re-evaluate.

## Open Questions

- Should the daily upload cron run before or after the daily discovery cron? (Recommended: discovery first, then upload — so re-attribution runs against the freshest `customer_gclids` before any commits.)
- For the converted-gate "most recent job" selection, do we want `ORDER BY j.created_at DESC LIMIT 1` or `ORDER BY j.updated_at DESC LIMIT 1`? (`vw_conversion_candidates` currently uses `created_at DESC` for its job pivot; consistency favors that.)
- Is there a downstream dashboard query that filters by `qualified_status = 'uploaded'` and depends on the old gate definition? (Audit before deploy.)
