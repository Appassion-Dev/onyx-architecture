## Why

The client needs CSV exports of Google Ads conversion uploads in their spreadsheet template format (Email, Phone Number, Conversion Name, Conversion Time, Conversion Value, Conversion Currency, Google Click ID, JSON Sent, JSON Echo) so they can review exactly what was sent to Google Ads and what Google echoed back, per week and across the whole 90-day window. The existing "Export CSV" (the `export_converted_leads` RPC) only covers converted leads, uses an internal ops-column format, and carries none of the request/response payload evidence.

## What Changes

- Add a CSV download icon to each month header (`MonthRow`) and each week header (`WeekBlock`) on the conversions page that exports that month's/week's conversion uploads, pre-filtered to the rows/events the group is currently showing under the active conversion mode filter.
- Rewire the existing page-level "Export CSV" button (`ConversionsHeroHeader`) to export **all** conversion types for **all** estimates loaded in the 90-day window, ignoring the current mode filter, in the same template format.
- Both exports share one format with columns: Email, Phone Number, Conversion Name, Conversion Time, Conversion Value, Conversion Currency, Google Click ID, JSON Sent, JSON Echo, Error.
- Conversion Name uses the exact live Google Ads conversion action names from `gads_conversion_config.conversion_action_name` (currently `BOOKING_CONFIRMED`, `Qualified Leads`, `Converted Leads`) — never hardcoded, so renames in the Ads account cannot drift the CSV.
- JSON Sent / JSON Echo / Error come from the deployed `vw_gads_upload_payload_slices` view (`request_slice`, `response_results_slice`, `error_slice` falling back to `error_message`), narrowed to the row's own conversion type per the `gads-upload-payload-slices` spec.
- **BREAKING**: The old converted-leads export is removed entirely — the `useConvertedLeadsExport` hook is deleted and the `export_converted_leads()` RPC function is dropped via migration. The old ops-format CSV is no longer producible.

## Capabilities

### New Capabilities
- `gads-template-csv-export`: Month-level, week-level, and page-level CSV export of conversion uploads in the Google Ads template format, sourced from `vw_gads_upload_payload_slices` merged with on-screen pipeline rows.

### Modified Capabilities
- None. (The `full-stack-architecture` spec is a single "reference document exists" requirement; its requirement-level behavior is unchanged. The reference doc's `export_converted_leads` section is updated as an implementation task, not a spec delta.)

## Impact

- **Frontend**: `MonthRow.tsx` and `WeekBlock.tsx` (new icon buttons), `ConversionsHeroHeader` / `ConversionsPage.tsx` (rewired export handler), new shared export hook/helper (replaces `src/lib/hooks/useConvertedLeadsExport.ts`, which is deleted).
- **Database**: One forward migration dropping `export_converted_leads()`. No view/table changes — `vw_gads_upload_payload_slices` and `gads_conversion_config` are already deployed and granted to `authenticated`.
- **Dependencies**: None added; CSV is built manually and downloaded via Blob, matching the existing pattern.
- **Out of scope**: Per-attempt history (slices view is latest-attempt only), changes to any existing views.
