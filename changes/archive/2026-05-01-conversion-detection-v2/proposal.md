## Why

The current conversion detection pipeline has three problems: (1) stages are chained — qualified and converted leads can't be discovered without a prior `booking_lead` row, missing legitimate ad-attributed leads that came in by phone or were created directly in HousecallPro; (2) GCLID attribution is scoped to a single booking event, so follow-up estimates for the same customer lose the original click attribution; (3) value formulas are inconsistent — `display_value` in the view and `conversion_value` in the upload function use different logic, and for qualified leads the approved-options filter means $0 is uploaded for any estimate where approval hasn't happened yet.

## What Changes

- **BREAKING** Remove `booking_lead` as a prerequisite for `qualified_lead` and `converted_lead` discovery — all three stages are now independent detectors
- Introduce a `customer_gclids` table that stores GCLID → customer associations; discovery pre-pass populates it from `booking_tags` and `callrail_leads`
- `qualified_lead` GCLID resolution uses `customer_gclids` (via `customer_id`) with fallback to NULL; enhanced conversions handle attribution when GCLID is absent
- `converted_lead` GCLID resolution uses the same `customer_gclids` path
- Change `qualified_lead` value formula from `SUM(approved options)` to `AVG(all options)`
- Change `display_value` in `vw_conversion_candidates` from `SUM(approved options)` to `AVG(all options)` — aligning dashboard display with upload value
- `converted_lead` value formula remains `SUM(approved options)` — approval is still the gate and the value source
- `converted_lead` gate: `∃ approved option` only — booking_lead prerequisite removed
- `qualified_lead` gate: `estimates.work_status IN ('complete rated', 'complete unrated')` AND at least one option with `total_amount > 0` — booking_lead and approval prerequisites both removed; `conversion_datetime` is `estimates.updated_at` (captures the status transition moment)
- Backfill function to populate `customer_gclids` from historical `booking_tags` and `callrail_leads` data
- Remove visual chain connectors between pipeline stage cells — since stages are independent events, the connected-strip metaphor is incorrect
- Display `estimates.work_status` inside the qualified stage cell so the trigger condition is visible at a glance

## Capabilities

### New Capabilities

- `customer-gclid-attribution`: New `customer_gclids` table, population pre-pass in `discover_pending_conversions()`, backfill SQL function, and customer-scoped GCLID resolution used by qualified and converted detection functions

### Modified Capabilities

- `pipeline-stage-qualified`: Gate changes to `work_status IN ('complete rated', 'complete unrated')` with at least one option having `total_amount > 0`; booking_lead and approval requirements removed; value formula changes to AVG(all options); datetime is `estimates.updated_at`; GCLID sourced from `customer_gclids`
- `pipeline-stage-converted`: Gate removes booking_lead requirement (approval remains); GCLID sourced from `customer_gclids`
- `conversion-candidates-view`: `display_value` formula changes to AVG(all options) / 100.0
- `pipeline-phase-visuals`: Remove connector lines between stage cells; stages are now displayed as three independent cells with no visual chaining
- `conversion-pipeline-ui`: Qualified stage cell displays `work_status` from the estimate row as a sub-label

## Impact

- **Database**: New table `customer_gclids`; updated SQL functions `get_pending_qualified_lead_conversions()`, `get_pending_converted_lead_conversions()`, `discover_pending_conversions()`, `discover_pending_conversions_for_estimate()`; updated view `vw_conversion_candidates`; new backfill function
- **Edge functions**: No changes — `google-ads-conversion-upload` already handles NULL GCLID via enhanced conversions
- **Dashboard**: `display_value` shown in `ConversionsPage` changes semantics from "approved total" to "average of presented options"; qualified stage cell gains a `work_status` sub-label; connector lines between stage cells are removed
- **Existing `gads_conversion_uploads` rows**: Unaffected — frozen values at discovery time are not retroactively updated; backfill only populates `customer_gclids`
