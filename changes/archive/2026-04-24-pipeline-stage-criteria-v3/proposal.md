## Why

The current Google Ads conversion pipeline defines stage criteria that are too narrow (booking only counts form submissions) and too downstream (qualified requires work_status, converted requires job completion). This misses leads from phone calls, Google Local Services, and other channels, and delays conversion signals that Google's Smart Bidding needs. The stage definitions need to be broadened and simplified to reflect the actual business lifecycle: booked → quoted → approved.

## What Changes

- **Booking lead criteria broadened**: Any estimate with a source signal qualifies — booking form, booking tags, correlated CallRail lead, or lead_source set. No longer restricted to `is_booking_form = true`.
- **Qualified lead criteria simplified**: An estimate is qualified when any estimate option has a non-null `total_amount`. No work_status or approval_status check. Value = SUM of approved/pro-approved option amounts.
- **Converted lead redefined**: Moves from job completion to estimate approval. An estimate is converted when any option has `approval_status IN ('approved', 'pro approved')`. Value = SUM of approved/pro-approved option amounts. **BREAKING**: The `jobs` table is no longer used; the pipeline is fully estimate-centric.
- **Datetime sources updated**: Booking uses `estimates.created_at`, qualified uses `estimates.updated_at`, converted uses `MAX(estimate_options.updated_at)` for approved options.
- **Upload skip rule unified**: All three stages discover estimates without GCLID/enhanced identifiers as pending, but skip them at upload time with an error message.

## Capabilities

### New Capabilities
- `pipeline-stage-booking`: Criteria, value, and datetime logic for the booking lead conversion stage
- `pipeline-stage-qualified`: Criteria, value, and datetime logic for the qualified lead conversion stage
- `pipeline-stage-converted`: Criteria, value, and datetime logic for the converted lead conversion stage

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- **SQL functions**: `get_pending_booking_lead_conversions()`, `get_pending_qualified_lead_conversions()`, `get_pending_converted_lead_conversions()` must be rewritten
- **SQL wrapper**: `discover_pending_conversions()` unchanged (calls the three functions above)
- **Pipeline view**: `vw_gads_conversion_pipeline` must be updated to reflect new criteria and value calculations
- **Edge function**: `google-ads-conversion-upload` upload/skip logic unchanged, but the rows it receives will differ
- **Dashboard**: `ConversionsPage.tsx` may need column/display adjustments if value semantics change
- **Schema**: `gads_conversion_uploads` table structure unchanged; `gads_conversion_config` unchanged
- **Removed dependency**: `jobs` table no longer participates in the pipeline
