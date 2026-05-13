## Context

Google Ads enforces two independent time constraints on offline conversion uploads. They are measured against different reference points and are commonly conflated:

```
                    click_through_lookback_window_days
                    (per-ConversionAction setting, default 30d, max 90d)
                    ◄──────────────────────────────────►
                                                        │
       Click ──────────────────────────────────► Conversion ────────────────────► Upload
       (GCLID born)                             (conversion_datetime)            (now)
       first_seen_at                                       ◄────────────────────►
                                                           Upload recency window
                                                           90 days (hard API limit)
```

**Window 1 — Upload recency** (`conversion_datetime` age relative to upload time): enforced by the edge function via `status = 'expired'` for rows where `conversion_datetime < now() - 90d`. Already implemented correctly.

**Window 2 — Click lookback** (GCLID click age relative to `conversion_datetime`): configured in Google Ads per conversion action as `click_through_lookback_window_days`. **Not currently enforced in discovery.** When the oldest `customer_gclids` row for a customer predates the conversion event beyond this window, Google Ads rejects the upload. The row stays `pending`, accumulates retry counts, and never expires via Window 1 (because `conversion_datetime` itself is recent).

The current discovery query for qualified and converted leads:
```sql
(SELECT cg.gclid
 FROM public.customer_gclids cg
 WHERE cg.customer_id = e.customer_id
 ORDER BY cg.first_seen_at ASC   -- picks oldest → worst case for Window 2
 LIMIT 1)
```

## Goals / Non-Goals

**Goals:**
- Filter `customer_gclids` selection to GCLIDs whose `first_seen_at` falls within the conversion event's lookback window
- Eliminate the "perpetual pending" failure pattern caused by stale GCLIDs
- Identify and remediate existing `pending` rows affected by this gap
- Update the architecture spec to document both constraints and establish the norm that it is kept current after each feature implementation

**Non-Goals:**
- Changing the upload edge function (Window 1 is correct)
- Making `click_through_lookback_window_days` dynamically configurable per conversion type (hardcode a safe default)
- Modifying `booking_lead` discovery (uses per-estimate GCLID, not `customer_gclids`)

## Decisions

### D1: Reference point for the lookback filter is `conversion_datetime`, not `now()`

**Decision:** Filter `first_seen_at >= e.updated_at - INTERVAL '90 days'` (for qualified_lead) and `>= MAX(approved option updated_at) - INTERVAL '90 days'` (for converted_lead), not `>= now() - 90 days`.

**Rationale:** The click lookback is measured by Google from the *conversion event timestamp*, not from when we upload. Using `now()` would be a moving target — a conversion that happened 85 days ago would accept a GCLID that is 86 days old today, but reject it tomorrow. Using `e.updated_at` (or the approved option timestamp) is semantically correct and stable.

**Alternative considered:** `now() - 90d`. Simpler and symmetric with the upload recency expiry, but conceptually wrong — it shifts as time passes, causing inconsistent behavior for the same historical conversion on different days.

### D2: Hardcode 90 days as the lookback window constant

**Decision:** Use `INTERVAL '90 days'` in the discovery SQL. Do not read `click_through_lookback_window_days` from a config table.

**Rationale:** 90 days is the *maximum* allowed by Google Ads. Filtering to ≤ 90 days is always safe — it's conservative (may produce NULL GCLID in edge cases) but never produces an unuploadable GCLID. Making this dynamic adds schema complexity that isn't warranted.

**Caveat:** Accounts using a shorter lookback window (e.g., 30 days) may still send GCLIDs that Google rejects via Window 2 if the actual account setting is < 90 days. This is acceptable — the fix eliminates the most egregious failures (old cross-customer GCLIDs hundreds of days old). The partial case can be addressed later if diagnostics show remaining rejections.

### D3: NULL GCLID fallback — keep the row, rely on enhanced conversions

**Decision:** When the lookback filter returns no eligible GCLID, discover the row with `gclid = NULL`. The upload phase already supports NULL GCLID — it falls back to enhanced conversions (hashed email/phone).

**Rationale:** Discarding the discovery row entirely would silently drop conversions where the customer has contact data. A NULL-GCLID row reaching the upload phase is better than no row at all.

### D4: `first_seen_at` is a proxy for click time — accept the imprecision

**Decision:** Accept that `first_seen_at` in `customer_gclids` is *when we recorded the GCLID*, not *when the click happened*. For booking form GCLIDs this is `e.created_at` (accurate). For CallRail, it's `cl.call_started_at` (the call time, not the click — may lag by days). The fallback is `now()` at prepass execution time, which can be artificially recent.

**Implication:** The filter is a best-effort approximation. GCLIDs with `first_seen_at = now()` (stale fallback records) will pass the filter even if the actual click was outside the window. This is acceptable — it only over-accepts, not over-rejects.

### D5: Arch spec update procedure — standing requirement

**Decision:** Add to `openspec/specs/full-stack-architecture/spec.md` a standing requirement that the architecture spec be updated whenever a pipeline feature implementation is completed. This makes spec drift a violation, not a habit.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Existing pending rows with stale GCLIDs continue to retry indefinitely | One-time cleanup: update or re-discover affected rows. Include a targeted SQL script. |
| Account's actual `click_through_lookback_window_days` < 90 days → some rows still fail | Acceptable partial improvement. Monitor upload diagnostics post-deploy; address shorter window accounts in follow-up. |
| `first_seen_at` fallback to `now()` creates false-fresh records that pass the filter | Low impact — these records over-accept (may send a GCLID Google rejects) but no worse than current behavior. |
| NULL GCLID rows increase — enhanced conversion match rate may not cover all | Enhanced conversions require hashed contact data; if customer has no email/phone, conversion is truly unattributable. This is honest, not a regression. |

## Migration Plan

1. **Deploy new migration** replacing `get_pending_qualified_lead_conversions()` and `get_pending_converted_lead_conversions()` with lookback-filtered GCLID subqueries.
2. **Run cleanup query** (local only, non-destructive read first): identify `pending` rows where `gclid IS NOT NULL` and `customer_gclids.first_seen_at < conversion_datetime - INTERVAL '90 days'`.
3. **Write cleanup migration** that sets `status = 'stale_gclid'` (or NULLs the GCLID and resets to pending) for affected rows, so they are re-processed with correct logic.
4. **Update specs**: `customer-gclid-attribution/spec.md` and `full-stack-architecture/spec.md`.
5. **No edge function changes required.**

**Rollback:** Revert the SQL migration. No schema changes, so rollback is a function replacement only.

## Open Questions

1. Should we introduce a `'stale_gclid'` status value or simply NULL the GCLID and leave the row `pending`? The latter avoids schema churn but loses auditability.
2. Do we know the actual `click_through_lookback_window_days` configured in the Google Ads account? If it's 30 days, the 90-day constant still allows some failures. Worth checking the account setting.
3. Should the cleanup migration also check `booking_lead` rows? (Per the proposal, booking_lead uses per-estimate GCLID lookup, not `customer_gclids`, so it should be unaffected — but worth confirming.)
