## Context

The `customer_gclids` table is the canonical store of customer-scoped GCLID attribution. Two write paths populate it from `callrail_leads`:

1. `discover_pending_conversions()` and `discover_pending_conversions_for_estimate(p_estimate_id)` — the discovery pre-pass invoked from the cron and the per-estimate RPC.
2. `backfill_customer_gclids()` — an idempotent one-shot used after schema changes or large data imports.

All three sites currently use the same shape for the CallRail source:

```sql
FROM callrail_leads cl
JOIN estimates e ON e.id::varchar = cl.estimate_id
WHERE cl.gclid IS NOT NULL
  AND e.customer_id IS NOT NULL
```

`callrail_leads.estimate_id` is populated by the `correlate_callrail_estimate` BEFORE-trigger (migration `20260406000001_callrail_estimate_correlation.sql`). The trigger first matches a customer by phone / email / name, then picks the **most recently created** estimate for that customer. The estimate field can be NULL when:

- the customer was matched but had no estimates at trigger time (call landed before any estimate existed),
- no customer matched (phone normalization failed, no contact info, name match missed),
- the trigger's resync function was never run after the customer's estimate appeared.

When `estimate_id` is NULL, the pre-pass's `JOIN estimates ON cl.estimate_id` produces zero rows for that CallRail lead, and its GCLID never reaches `customer_gclids` — even when `cl.customer_id` IS populated and would be a usable attribution key.

The trigger sets *both* `customer_id` and `estimate_id` from the same customer match. The pre-pass only needs `customer_id`. The `estimate_id` hop through `estimates` is a residual of an earlier design and contributes no useful filtering.

## Goals / Non-Goals

**Goals:**
- Stop dropping CallRail-sourced GCLIDs whose `callrail_leads.estimate_id` is NULL but whose `customer_id` is populated.
- Source CallRail GCLIDs via `callrail_leads.customer_id` directly in all three sites (batch pre-pass, per-estimate pre-pass, backfill function).
- Preserve all current behavior: `(customer_id, gclid)` uniqueness, `source = 'callrail'`, `first_seen_at = COALESCE(cl.call_started_at, …)`, ON CONFLICT DO NOTHING.

**Non-Goals:**
- Changing the trigger that sets `callrail_leads.estimate_id`. Out of scope; the field stays useful for `vw_conversion_candidates` per-estimate aggregates.
- Rewriting `vw_conversion_candidates` to derive per-estimate CallRail aggregates differently. Separate concern.
- Changing the resolver (oldest-vs-newest, lookback window, per-stage hoisting). That's `conversion-attribution-overhaul`'s scope.
- Removing `customer_gclids.estimate_id` from the schema. The column stays informational.
- Backfilling rows automatically as part of the migration. The operator runs `SELECT backfill_customer_gclids()` after deploy if desired.

## Decisions

### D1. Join key: `callrail_leads.customer_id` instead of via `estimates.id = cl.estimate_id`

The CallRail trigger writes both `customer_id` and `estimate_id` from the same match. The pre-pass consumes only `customer_id`. Joining through `estimates` adds a filter (`cl.estimate_id IS NOT NULL` and a matching `estimates` row exists) that has no semantic value for the pre-pass's contract — `customer_gclids` is customer-scoped, not estimate-scoped — and silently excludes valid attributions.

**Alternative considered: keep the estimate join, fix the trigger.** Rejected: the trigger correctly stores `customer_id` already; the bug is in the pre-pass's choice of join key, not in the trigger. Fixing the trigger to set `estimate_id` more aggressively would couple GCLID attribution to a heuristic ("staple the call to *some* estimate") that doesn't need to exist for this use case.

**Alternative considered: keep the estimate join, only widen to include calls without `estimate_id` via a UNION.** Rejected as needlessly complex — produces identical output as the direct `customer_id` join.

### D2. `customer_gclids.estimate_id` write value: `cl.estimate_id` (may be NULL)

When the source row no longer guarantees a non-NULL `estimate_id`, the inserted value can be NULL. This column is informational (no resolver reads it; the per-estimate RPC uses `customer_id` to scope its query). Leaving it as `cl.estimate_id` preserves the closest available provenance — "the estimate the trigger stapled this call to, if any" — without inventing a value.

**Alternative considered: synthesize an estimate_id by re-running the trigger's "newest estimate" pick at pre-pass time.** Rejected: duplicates the trigger's heuristic at a second site, and worsens the original problem this change is fixing (decoupling GCLID attribution from that heuristic).

### D3. No data migration; rely on the existing backfill function

The migration replaces three function bodies. Historical CallRail rows whose GCLIDs were previously dropped are recovered by running `SELECT backfill_customer_gclids()` after deploy — the same backfill that already exists, now with the corrected join.

**Alternative considered: include an inline backfill in the migration's deploy step.** Rejected: backfill should be operator-initiated to avoid surprising the cron schedule with a long-running upsert during a migration window.

### D4. Three sites, one migration

Both pre-pass orchestrators and the backfill function share the same join pattern and the same correctness condition. Putting them in one migration keeps the change atomic — there's no useful intermediate state where one site has been updated and another hasn't.

## Risks / Trade-offs

- **[Risk] Eligible-row growth surfaces previously hidden bad data.** Some CallRail leads with `customer_id` set but invalid `gclid` values may now insert into `customer_gclids`. The existing `cl.gclid IS NOT NULL` filter catches NULL but not malformed strings. → Mitigation: rely on the resolver's existing 90-day in-window filter to reject obvious noise; if malformed GCLIDs become a real problem the upload-time validator catches them before sending to Google Ads.
- **[Risk] Merge conflict with `conversion-attribution-overhaul`.** Both changes edit the discovery pre-pass functions. → Mitigation: this change is intentionally narrow (only the `FROM`/`JOIN` block for Source 2). Whichever lands second incorporates the other's edits in the same place. Document this in tasks.md.
- **[Risk] A customer-scoped GCLID pull is broader than an estimate-scoped one.** A CallRail lead with `customer_id` matched but no estimate yet now contributes its GCLID to `customer_gclids` immediately, where before it only contributed after an estimate was created (and re-discovery ran). → Mitigation: this is the intended improvement. The resolver still applies the 90-day window per conversion event, so contributing a GCLID earlier cannot cause an out-of-window attribution.
- **[Trade-off] `customer_gclids.estimate_id` becomes weaker.** It may now be NULL for CallRail-sourced rows. → Mitigation: column is informational; no resolver reads it. Documented in the modified requirement.

## Migration Plan

1. **Pre-deploy verification.** Run a read-only query that reports how many CallRail rows would become newly eligible:
   ```sql
   SELECT COUNT(*) FROM callrail_leads cl
   WHERE cl.gclid IS NOT NULL
     AND cl.customer_id IS NOT NULL
     AND cl.estimate_id IS NULL;
   ```
   A non-zero count confirms the change has measurable effect; a zero count means the bug exists in theory but is currently latent.

2. **Deploy the migration.** Single migration replacing `discover_pending_conversions()`, `discover_pending_conversions_for_estimate(text)`, and `backfill_customer_gclids()`. Schema unchanged; only function bodies change.

3. **Run the backfill.** `SELECT * FROM backfill_customer_gclids();` Returns `(booking_form_rows, callrail_rows)`. The `callrail_rows` delta compared to a prior run is the number of historically dropped rows now recovered.

4. **Verify.** Spot-check a few customers known to have `estimate_id`-NULL CallRail leads — they should now appear in `customer_gclids`.

5. **Rollback.** Re-apply the prior migration definitions. Existing `customer_gclids` rows are not deleted on rollback; they're idempotently re-asserted on the next forward deploy.

## Open Questions

- None blocking. The interaction with `conversion-attribution-overhaul` is an ordering question for delivery, not a design question.
