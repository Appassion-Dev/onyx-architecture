## Context

The qualified gate (`get_pending_qualified_lead_conversions()`) is deployed with the finalization definition from `2026-06-05-qualified-gate-finalization`: it fires on `work_status IN ('complete rated','complete unrated','created job from estimate')` + a priced option, with `conversion_datetime = estimates.updated_at`, GCLID = oldest in-window (ASC, anchored on `updated_at`), value = average of all options.

That change deliberately deferred using `work_timestamps.completed_at` as the timestamp "until the table carries clean data," and revived the importer to make that possible. Live state now (verified 2026-06-05):

- `work_timestamps` is **clean**: 2,000 rows = 1,000 distinct estimates + 1,000 distinct jobs, deterministic ids (`ts_est_<id>` / `ts_job_<id>`), no duplication, last import today. The orphaned `transformWorkTimestamps` is wired into the importer's related-records phase.
- Coverage is **partial**: of the **4,904** estimates in the qualified cohort (finalized + priced), **580** have a `work_timestamps` row and **452** have a non-NULL `completed_at`. So `completed_at` can drive the timestamp for ~**9.2%** of the cohort today; the rest fall back to `updated_at`.
- On the covered subset, `updated_at` lags `completed_at` by an average of **~0.37 days** — a real but modest accuracy gain.
- `work_timestamps.completed_at` is `timestamp without time zone`; the importer stores HCP's UTC ISO value verbatim (`import-estimates.ts:176`), so the stored wall-clock is UTC. `estimates.updated_at` and the function's `conversion_datetime` return column are `timestamptz`.

## Goals / Non-Goals

**Goals:**
- Make `conversion_datetime` prefer the literal completion signal: `COALESCE(work_timestamps.completed_at (as UTC), estimates.updated_at)`.
- Keep the gate fully covered and degrade gracefully — a value is always produced, and `completed_at`'s share grows automatically as imports backfill the table.
- Align `ORDER BY` to the coalesced expression so pending rows sort by the timestamp they'll actually upload with.

**Non-Goals:**
- Changing the finalization gate criteria, the GCLID resolver or its 90-day window anchor, or the conversion value formula.
- Backfilling `work_timestamps` (operational; runs via normal imports — out of scope).
- Adopting `on_my_way_at` / `started_at`, or using `completed_at` for the converted-lead gate.

## Decisions

### Decision 1: `conversion_datetime = COALESCE(completed_at AT TIME ZONE 'UTC', updated_at)`
Replace the `e.updated_at` projection with a correlated lookup:
```sql
COALESCE(
  (SELECT MAX(wt.completed_at)
   FROM public.work_timestamps wt
   WHERE wt.estimate_id = e.id) AT TIME ZONE 'UTC',
  e.updated_at
) AS conversion_datetime
```
**Rationale:** `completed_at` is the literal visit-completion moment; `updated_at` is a lagging proxy. Preferring `completed_at` where present is strictly more faithful, and `updated_at` (100% covered) guarantees a value otherwise. `AT TIME ZONE 'UTC'` converts the naive UTC `timestamp` to `timestamptz`, making the COALESCE operands and the return type consistent.

### Decision 2: Use `MAX()` scalar subquery, not a JOIN
The deterministic id guarantees ≤1 `work_timestamps` row per estimate, so a `LEFT JOIN` would not fan out today. A correlated `SELECT MAX(completed_at)` is used anyway because (a) it cannot multiply result rows even if a stray duplicate ever appears, and (b) it mirrors the existing inline-subquery style of the GCLID and value projections. `MAX` over an all-NULL or empty set returns `NULL`, which the `COALESCE` then resolves to `updated_at` — so "row missing" and "row present but `completed_at` NULL" collapse to the same correct fallback.

### Decision 3: GCLID window anchor stays on `updated_at`
The 90-day attribution window keeps `cg.first_seen_at >= e.updated_at - INTERVAL '90 days'`. `updated_at` is fully covered, so anchoring the window there keeps GCLID resolution identical and consistent across all rows; anchoring on a ~12%-covered `completed_at` would make attribution behavior depend on import coverage. The ~0.37 d shift would be negligible against a 90-day window regardless. (Out of this change's stated scope.)

### Decision 4: `ORDER BY` the same coalesced expression
Change `ORDER BY e.updated_at ASC` to order by the identical `COALESCE(... AT TIME ZONE 'UTC', e.updated_at)` so the pending list is ordered by the actual conversion timestamp. Cosmetic for correctness of pagination/ordering; no behavioral effect on which rows are returned.

### Decision 5: New migration, not an in-place edit
Unlike the prior change (which edited an **undeployed** migration in place), `get_pending_qualified_lead_conversions()` is now **deployed**. So this change adds a **new** later-timestamped migration with a `CREATE OR REPLACE FUNCTION` carrying the full updated body. History stays append-only and the deployed migration is left intact.

## Risks / Trade-offs

- **[Trade-off] Small immediate effect.** Only ~9% of the cohort has a usable `completed_at` today, so most timestamps are unchanged. **Mitigation:** accepted — the COALESCE is forward-compatible; coverage (and thus accuracy) improves automatically as imports backfill `work_timestamps`, with no further code change.
- **[Risk] Timezone misinterpretation.** If HCP ever sent non-UTC values, `AT TIME ZONE 'UTC'` would skew them. **Mitigation:** verified the importer stores HCP's UTC ISO string verbatim and the live `max(completed_at)` has no offset/fractional drift inconsistent with UTC; HCP's API is UTC.
- **[Risk] `completed_at` after `updated_at`.** In rare cases a later-recorded completion could push `conversion_datetime` slightly past `updated_at`. **Mitigation:** harmless — it is still the literal completion moment and remains within the estimate's lifecycle; measured average is `updated_at` *later*, not earlier.
- **[Trade-off] Conversion timing shift in Google Ads.** Affected rows move ~0.37 d earlier. **Mitigation:** small magnitude on a small subset; Smart Bidding impact negligible.
- **[Risk] Stray duplicate `work_timestamps` rows.** Would otherwise fan out the gate. **Mitigation:** `MAX()` scalar subquery (Decision 2) collapses to one value regardless.

## Migration Plan

1. Add a new migration `supabase/migrations/<ts>_qualified_gate_completed_at_datetime.sql` with `CREATE OR REPLACE FUNCTION public.get_pending_qualified_lead_conversions()` — full current body, changing only the `conversion_datetime` projection (Decision 1) and the `ORDER BY` (Decision 4); GCLID resolver, value, gate `WHERE`, de-dup, grants unchanged.
2. Verify against live data: rows with a covered `completed_at` return it (as UTC); uncovered rows return `updated_at`; row counts and de-dup unchanged versus the current gate.
3. Hand deploy to the user (do not run `supabase db push`).

**Rollback:** `CREATE OR REPLACE FUNCTION` — revert by re-applying the prior (finalization) body. No data is mutated.

## Open Questions

- ~~Should the GCLID window anchor also move to `completed_at`?~~ **Resolved:** no — keep on `updated_at` for full-coverage consistency (Decision 3); revisit only if attribution is re-examined.
- Confirm there is no appetite to backfill `work_timestamps` as part of this change (assumed out of scope; coverage grows via normal imports).
