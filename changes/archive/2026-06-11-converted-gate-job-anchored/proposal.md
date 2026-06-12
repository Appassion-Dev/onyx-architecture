## Why

The current `get_pending_converted_lead_conversions()` uses option approval as the conversion gate and timestamp — but option approval is a customer intent signal, not an operational commitment. When HCP automation auto-creates a job from an approved estimate, that `jobs.created_at` is the immutable moment of the sale. Anchoring the converted discovery to the job rather than the approval produces more accurate conversion timestamps and values aligned with the actual booked revenue.

## What Changes

- **BREAKING** Gate: require both an approved option (`approval_status IN ('approved','pro approved')`) AND a linked job (`jobs.original_estimate_id = estimate_option.id`). The job proves the estimate transitioned from quote to booked work.
- **BREAKING** Conversion datetime: use `jobs.created_at` instead of `MAX(estimate_options.updated_at)`. This is the moment HCP automation created the job, not when the customer approved.
- **BREAKING** Conversion value: use `jobs.total_amount` (the job subtotal) instead of `SUM(approved options' total_amount)`. The job total is the authoritative booked revenue figure.
- **BREAKING** GCLID lookback window anchor: the 90-day click window anchors to `job.created_at` instead of the approved option's `updated_at`.
- Return `job_id` populated from the linked job's `id` (currently always `NULL`).

## Capabilities

### New Capabilities
- `converted-job-anchored`: Discovery gate, timestamp, and value for the converted stage anchored to the linked job rather than option approval.

### Modified Capabilities
- `pipeline-stage-converted`: Requirements for discovery gate, conversion datetime, and conversion value all change. Delta spec required.

## Impact

- `get_pending_converted_lead_conversions()` — primary function being rewritten
- `vw_conversion_candidates` — may need adjustment if it derives converted stage value/datetime from the function or mirrors its logic
- `discover_pending_conversions()` and `discover_pending_conversions_for_estimate()` — both call the converted function; downstream effects are contained but the discovery output shape changes
- `export_converted_leads()` — uses `conversion_datetime` from `gads_conversion_uploads`; the datetime written at upload time will now be `job.created_at` instead of option approval datetime
