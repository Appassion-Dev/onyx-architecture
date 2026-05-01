## Context

The conversion detection pipeline currently has three tightly coupled SQL functions (`get_pending_booking_lead_conversions`, `get_pending_qualified_lead_conversions`, `get_pending_converted_lead_conversions`) and a batch orchestrator (`discover_pending_conversions`). Qualified and converted detection both require a prior `booking_lead` row on the same estimate — a dependency that silently drops legitimate ad-attributed leads created outside the booking form (phone calls, direct HCP entry). GCLID attribution is scoped per estimate via `booking_tags` and `callrail_leads`, meaning follow-up estimates for the same customer have no GCLID even though the original click is on record. Value formulas differ between the view (`display_value`) and the upload functions (`conversion_value`), causing confusion about what the UI shows vs. what Google receives.

## Goals / Non-Goals

**Goals:**
- Make all three detection stages fully independent (no upstream stage prerequisites)
- Introduce `customer_gclids` as a normalized attribution table so any estimate for a repeat customer can inherit the original click
- Align `qualified_lead` conversion_value and `display_value` to use AVG of all options
- Provide a one-time backfill function to populate `customer_gclids` from historical data
- Retain `converted_lead` value as SUM of approved options (semantically: committed spend)

**Non-Goals:**
- Changes to the `booking_lead` detection function or criteria
- Changes to the Google Ads upload edge function (`google-ads-conversion-upload`)
- Multi-GCLID-per-customer disambiguation (first GCLID seen wins, duplicate resolution out of scope)
- Retroactive recalculation of already-discovered `gads_conversion_uploads` rows
- Attribution deduplication across customer records that share contact info

## Decisions

### D1 — New `customer_gclids` table, not inline GCLID enrichment

**Decision**: Introduce a dedicated `customer_gclids` table with `(customer_id, gclid, source, first_seen_at, estimate_id)`. Discovery pre-pass UPSERTs into it.

**Alternatives considered**:
- *Inline lookup in each function*: Keep COALESCE(booking_tags, callrail) but extend to also scan all estimates for that customer. Too expensive — O(estimates per customer) correlated subquery in a function that runs per-estimate.
- *Column on customers table*: `customers.gclid text`. Simple but lossy — can't store multiple GCLIDs over time, can't audit source.

**Rationale**: Dedicated table is auditable, supports UNIQUE(customer_id, gclid) deduplication, naturally extensible, and the pre-pass pattern keeps discovery functions simple.

---

### D2 — Pre-pass runs inside `discover_pending_conversions()` and `discover_pending_conversions_for_estimate()`

**Decision**: Both the batch orchestrator and the per-estimate RPC run the `customer_gclids` upsert step before the three detection passes.

**Rationale**: Ensures `customer_gclids` is populated before qualified/converted functions read from it, within the same execution context. No separate cron job or trigger needed.

---

### D3 — Qualified lead gate requires ≥ 1 priced option; value formula averages all options

**Decision**: Two separate conditions apply to `qualified_lead`:
1. **Discovery gate**: `estimates.work_status IN ('complete rated', 'complete unrated')` AND `EXISTS (SELECT 1 FROM estimate_options WHERE estimate_id = e.id AND total_amount > 0)`. An estimate with no priced options has no measurable scope and is excluded.
2. **Value formula**: `AVG(eo.total_amount) / 100.0` across ALL options (no filter on `approval_status` or `total_amount`) once the gate passes. This includes any $0 placeholder options in the average.

**Alternatives considered**:
- *AVG only where total_amount > 0*: Excludes $0 placeholders from the average too. Rejected — overly opinionated about what constitutes a "real" option; the gate already ensures at least one priced option exists.
- *SUM(approved)*: Current behavior — produces $0 when no approvals exist at discovery time, defeating the purpose of early-funnel value signaling.

**Rationale**: The gate (≥ 1 option with total_amount > 0) guarantees the estimate has real scope before it is discovered. The value formula then represents expected opportunity value — what we pitched — not committed spend (that belongs to converted_lead, which uses SUM of approved). Averaging all options, including any $0 ones, avoids a secondary filter that would silently change the denominator.

---

### D4 — `customer_gclids` UNIQUE on `(customer_id, gclid)`

**Decision**: A customer can accumulate multiple GCLIDs over time (separate ad clicks on different visits). All are stored. The detection functions use the earliest (`ORDER BY first_seen_at ASC LIMIT 1`) — first-touch attribution.

**Alternatives considered**:
- *Last-touch*: Most recent GCLID. Could be a remarketing click, not the original acquisition.
- *UNIQUE(customer_id)* — one GCLID per customer: Simpler but loses the history and can't distinguish new campaigns.

**Rationale**: First-touch is standard for acquisition conversion reporting. Google Ads GCLID attribution is already tied to specific click windows; using the earliest GCLID maximizes the chance it's still within the valid window.

---

### D5 — Converted lead gate remains "has approved option" (no booking_lead required)

**Decision**: Remove the `booking_lead EXISTS` gate from `get_pending_converted_lead_conversions()`. The only remaining gate is `∃ approved option` and `NOT EXISTS converted_lead row`.

**Rationale**: Consistent with the "fully independent detectors" principle. Estimates from phone-in customers or direct HCP jobs can produce a converted_lead signal as long as attribution (GCLID or enhanced) is resolvable.

---

### D6 — Backfill via one-time SQL function, not a migration DML block

**Decision**: Provide a `backfill_customer_gclids()` SQL function that the user runs manually, not an inline `INSERT ... SELECT` in the migration file.

**Rationale**: Backfill volume is unknown. A migration-time DML block could time out or lock tables. A callable function can be retried, monitored, and run during low-traffic hours. It is idempotent (ON CONFLICT DO NOTHING).

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Estimates with no customer_id (rare HCP data quality issue) | GCLID lookup returns NULL; estimate is still discovered, falls back to enhanced conversions |
| Customer_gclids pre-pass adds latency to cron cycle | UPSERT is index-driven on (customer_id, gclid); expected < 10ms overhead on current data volume |
| AVG diluted by $0 placeholder options in mixed estimates | Gate excludes all-zero-option estimates; mixed estimates (some $0, some priced) are accepted — $0 options are included in the average denominator intentionally |
| Existing qualified_lead rows have stale SUM(approved) values | Not recalculated — frozen at discovery time. Only new discoveries use AVG formula |
| First-touch GCLID may be outside Google's 90-day attribution window | Upload edge function already handles this — returns partial_failure; row stays pending for retry or manual review |

## Migration Plan

1. Deploy migration: create `customer_gclids` table with indexes
2. Deploy migration: update `discover_pending_conversions()` and `discover_pending_conversions_for_estimate()` with pre-pass
3. Deploy migration: replace `get_pending_qualified_lead_conversions()` (remove booking_lead gate, add work_status gate, add priced-options gate, AVG value formula, customer_gclids GCLID lookup)
4. Deploy migration: replace `get_pending_converted_lead_conversions()` (remove booking_lead gate, customer_gclids GCLID lookup)
5. Deploy migration: update `vw_conversion_candidates` — display_value to AVG formula, add work_status to SELECT list
6. Deploy migration: create `backfill_customer_gclids()` function
7. Run backfill manually: `SELECT backfill_customer_gclids();`
8. Verify `customer_gclids` row count; confirm qualified/converted discovery picks up previously-orphaned estimates

**Rollback**: Each migration is a `CREATE OR REPLACE FUNCTION` or view — re-running the prior migration file restores previous behavior. The `customer_gclids` table can be dropped without affecting other tables (no foreign keys pointing at it).

## Open Questions

- None — all design decisions resolved in exploration session.
