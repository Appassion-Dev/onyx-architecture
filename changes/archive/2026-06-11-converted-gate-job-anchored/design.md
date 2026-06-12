## Context

`get_pending_converted_lead_conversions()` currently discovers converted leads by checking for an approved option (`approval_status IN ('approved','pro approved')`) and derives conversion metadata from that option:

- **Datetime**: `MAX(estimate_options.updated_at)` — when the option was approved
- **Value**: `SUM(approved options' total_amount) / 100.0` — sum of approved option prices

This is semantically wrong in two ways. First, option approval is a customer intent signal, not a booked-revenue event — the actual commitment is made when HCP automation auto-creates a job from the approved estimate. Second, the option's `total_amount` is a quoted price; the job's `total_amount` is the actual subtotal after work is performed, which is the authoritative revenue figure.

The May 11–17 changes report identified this as a **BREAKING** change under `conversion-attribution-overhaul`. This change implements it standalone.

## Goals / Non-Goals

**Goals:**
- Anchor converted conversion datetime to `jobs.created_at` — the moment HCP automation created the job
- Use `jobs.total_amount` as the conversion value — the authoritative subtotal
- Anchor the GCLID 90-day lookback window to `job.created_at` instead of the approved option's `updated_at`
- Populate the `job_id` return column from the linked job's `id`
- Preserve the approved-option gate (job existence alone is not sufficient; an approved option must exist)

**Non-Goals:**
- Changing the qualified-lead gate (separate concern)
- Modifying `discover_pending_conversions()` or `discover_pending_conversions_for_estimate()` architecture (they call this function; output shape change is contained)
- Retroactive reconciliation of existing `gads_conversion_uploads` rows (pending rows with NULL GCLID will be picked up by the re-attribution pass from `conversion-attribution-overhaul`)

## Decisions

### 1. Gate: approved option first, job data follows

The gate remains "at least one approved option." The job provides the timestamp and value *when it exists*. Since HCP automation auto-creates the job on approval, the job should exist by the time the option is approved in normal flow. A `LEFT JOIN` handles the job data gracefully:

```
Gate:  EXISTS(approved option)  ← primary discovery trigger
Datetime: COALESCE(job.created_at, NULL)  ← only populated when job exists
Value: COALESCE(job.total_amount, NULL)
```

In practice, because HCP auto-creates the job on approval, the job should always be present when an approved option is discovered. The `LEFT JOIN` is defensive — it keeps the query correct if the job is missing due to an automation failure.

### 2. Join path: `jobs.original_estimate_id = estimate_options.id`

Jobs are linked to a specific option via `jobs.original_estimate_id`. The join chain is:

```
estimates
  → estimate_options  (eo)  WHERE eo.approval_status IN ('approved','pro approved')
  → jobs  (j)  ON j.original_estimate_id = eo.id
```

This is the same pattern used throughout the sales views and prior conversion functions. It ensures the job is linked to the specific approved option, not just any option on the estimate.

### 3. GCLID lookback anchor: `job.created_at`

The 90-day click lookback window anchors to the job creation timestamp:

```sql
AND cg.first_seen_at >= j.created_at - INTERVAL '90 days'
```

This is more precise than the prior anchor (`MAX(approved option updated_at)`) because job creation is the committed event. A click within 90 days of job creation is more likely to be attribution-relevant than a click within 90 days of an earlier approval action.

### 4. `conversion_datetime` type remains `timestamptz`

`jobs.created_at` is stored as `timestamp with time zone` in Housecall Pro. The return type of `conversion_datetime` is unchanged — it remains `timestamptz`.

### 5. `job_id` return column populated

The function signature already includes `job_id text` as a return column but was always `NULL`. This change populates it from `j.id::text`.

## Risks / Trade-offs

**[Risk] Job automation failure leaves approved estimates undiscovered as converted**
→ If HCP automation fails to create the job, the approved option exists but the job is missing. The `LEFT JOIN` means `conversion_datetime` and `conversion_value` would be `NULL` — the estimate would be discovered but with null metadata. This is a data-quality gap, not a hard failure. Mitigation: monitor for approved-option estimates with no linked job (auditable via `vw_conversion_candidates`).

**[Risk] GCLID lookback window shifts**
→ Anchoring to `job.created_at` instead of `option.updated_at` changes which clicks are in-window. If job creation is significantly later than option approval, some clicks that were previously in-window may fall outside. This is the correct behavior — the click should be attributed to the job, not the approval.

**[Risk] `jobs.total_amount` may differ from option `total_amount`**
→ The job subtotal can differ from the approved option's quoted price (change orders, credits, etc.). This change switches to the job total as the authoritative figure. If the job total is `0` or `NULL`, the conversion value will be `0` — which is information, not a bug.

**[Risk] Existing pending `converted_lead` rows with NULL GCLID**
→ The re-attribution pass from `conversion-attribution-overhaul` handles NULL-gclid pending rows. This change does not need to address them directly.

## Migration Plan

1. Write new version of `get_pending_converted_lead_conversions()` in a new migration file
2. Test locally against existing seed data and known edge cases
3. Deploy migration — the function is `CREATE OR REPLACE`, so it's atomic
4. Monitor `vw_conversion_candidates` for the `converted_status` column and `job_total` values
5. No rollback needed for the function itself (atomic replace); if needed, the prior version can be restored via a rollback migration

## Open Questions

1. **Should the gate require the job to exist, or is approved-option-only sufficient?** Currently designed as approved-option gate with job data populated when the job exists. If job existence should be a hard gate, add `AND j.id IS NOT NULL` to the WHERE clause.

2. **Should `conversion_value = 0` or `NULL` when the job exists but `total_amount` is 0?** Currently `COALESCE(job.total_amount/100.0, 0)` — zero is returned as `0`. This matches the prior behavior for zero-value approved options.

3. **Is `jobs.created_at` reliably the auto-creation timestamp, or can it be backdated?** If jobs can be created manually with a custom `created_at`, the GCLID lookback anchor could be manipulated. Verify with the HCP data team whether `created_at` is set by the automation or can be user-set.
