## Context

The conversions page builds a Month → Week → Source hierarchy client-side from `vw_conversion_candidates` (90-day window, [useConversionsPipeline.ts](../../../horizon-dashboard/src/components/conversions/hooks/useConversionsPipeline.ts)). Each `WeekGroup` already holds its mode-filtered `rows` / `events`, so "pre-filtered week export" is a projection of in-memory data plus one fetch for payload slices.

Per-upload request/response evidence is already deployed in `vw_gads_upload_payload_slices` (change `2026-06-11-gads-upload-payload-slices-view`): `request_slice` (JSON sent to Google), `response_results_slice` (Google's echo), `error_slice`, `response_slice_kind`, plus all `gads_conversion_uploads` columns including `conversion_currency`. The frontend already consumes it in [usePayloadSlices.ts](../../../horizon-dashboard/src/components/conversions/components/pipeline-row/usePayloadSlices.ts), including the `entriesForType()` helper that narrows slices to one conversion type.

The client's template columns "JASON Sent" / "JASON Echo" are misspellings of **JSON Sent / JSON Echo** — the request and response slices. The exact Google Ads conversion action names live in `gads_conversion_config.conversion_action_name` (live values: `BOOKING_CONFIRMED`, `Qualified Leads`, `Converted Leads`) and are already loaded on the page via `useConversionConfigs()` and threaded down to `WeekBlock`.

The existing "Export CSV" button ([ConversionsPage.tsx:151](../../../horizon-dashboard/src/components/conversions/ConversionsPage.tsx)) calls the `export_converted_leads()` RPC via `useConvertedLeadsExport` — converted-only, internal ops format, no payload evidence. It is fully replaced.

## Goals / Non-Goals

**Goals:**
- One shared CSV format (Email, Phone Number, Conversion Name, Conversion Time, Conversion Value, Conversion Currency, Google Click ID, JSON Sent, JSON Echo, Error) used by all export surfaces.
- Month-level and week-level icons: each exports exactly what that group is showing under the active mode filter.
- Page-level button: exports all conversion types for all estimates in the loaded 90-day window, ignoring mode and filter bar.
- Conversion names always sourced from `gads_conversion_config`, never hardcoded.
- Remove the legacy export end-to-end (hook + RPC).

**Non-Goals:**
- Per-attempt history (slices view is latest-attempt only, by design).
- Any change to existing views/tables or to the detail-panel slice display.
- Producing a file directly importable by Google Ads' offline-conversion uploader (the JSON/Error columns make this a review/audit file; the conversion columns still mirror the upload payload).

## Decisions

### Decision: Client-side merge — slices fetched by estimate_id, identity from PipelineRow
On export, collect the `(estimate_id, stage)` pairs from the clicked scope, fetch `vw_gads_upload_payload_slices` with `.in('estimate_id', ids)` (chunked, see below), then merge client-side: Email/Phone come from the in-memory `PipelineRow` (`customer_email`, `customer_mobile`), everything else from the slice row keyed by `(estimate_id, conversion_type)`.

- *Why not a new RPC/view with customer join?* The page already holds customer identity for every visible row; a server-side join would duplicate `export_converted_leads`'s mistake — a second bespoke export artifact to keep in sync. Client merge keeps the DB surface unchanged (zero migrations besides the drop) and guarantees CSV ≡ screen.
- *Why fetch slices at click time rather than with the pipeline query?* Slices are jsonb payloads; loading them for every row on page load would bloat the hot path the slices-view design explicitly isolated them from.

### Decision: Scope semantics per surface
- **Month and week icons**: same rule at both grains — mode `all` → one CSV row per the group's `events` entry (its `stage` selects the upload row). Single-stage modes (`booking`/`qualified`/`converted`) → one CSV row per the group's `rows` entry for that stage. Mode `pre-discovery` → icons hidden (those rows precede uploads; the file would be empty of evidence). `MonthGroup` and `WeekGroup` both already carry `rows` and `events`, so one scope-collection function serves both.
- **Page button**: all `rows` from `useConversionsPipeline` (the unfiltered 90-day result, not `filteredRows`), every upload row the slices view returns for those estimates, all three conversion types.
- Visible rows whose upload is still `pending`/un-batched export with populated conversion columns and blank JSON Sent/Echo — an honest "not sent yet" signal.

### Decision: Column sourcing
| CSV column | Source |
|---|---|
| Email | `PipelineRow.customer_email` |
| Phone Number | `PipelineRow.customer_mobile` |
| Conversion Name | `configs.find(c => c.conversion_type === slice.conversion_type)?.conversion_action_name`, fallback `conversion_type` |
| Conversion Time | slice `conversion_datetime`, formatted `yyyy-MM-dd HH:mm:ss±HH:mm` (Google Ads upload format, matching payload-builder) |
| Conversion Value | slice `conversion_value` (blank when null — booking has none) |
| Conversion Currency | slice `conversion_currency` |
| Google Click ID | slice `gclid` (blank for ECL/user-data rows) |
| JSON Sent | `entriesForType(request_slice, conversion_action)` serialized |
| JSON Echo | `entriesForType(response_results_slice, conversion_action)` serialized |
| Error | `entriesForType(error_slice, conversion_action)` when non-empty, else `error_message`, else blank |

JSON columns reuse the narrowing rule from the `gads-upload-payload-slices` spec via the existing `entriesForType()` helper (exported from `usePayloadSlices.ts`). View columns are used directly rather than re-deriving from `request_slice` — they are the payload-builder's inputs, so identical by construction and present before upload.

### Decision: One shared export module, existing CSV/Blob pattern
A new `exportUploadsCsv.ts` under `components/conversions/lib/` exposes one function taking `{ pairs, rowsByEstimateId, configs, filename }`. It chunks `.in()` queries at 200 ids, builds CSV with the same manual quote-escaping (`"` → `""`) and Blob anchor-click download as the legacy hook. No CSV library. Filenames: `gads-conversions-<monthKey>.csv` / `gads-conversions-<weekKey>.csv` / `gads-conversions-90d.csv`.

### Decision: Complete removal of the legacy export
`useConvertedLeadsExport.ts` is deleted, `ConversionsHeroHeader`'s `onExport` rewired, and a forward migration drops `export_converted_leads(date, date)`. Per user decision the old ops-format CSV must not survive as a second code path. Rollback: re-apply migration `20260513000001` to restore the function.

### Decision: Month and week icon placement
A small download icon button sits in each group header: next to `monthLabel` in [MonthRow.tsx](../../../horizon-dashboard/src/components/conversions/components/hierarchy/MonthRow.tsx) and next to `weekLabel` in [WeekBlock.tsx](../../../horizon-dashboard/src/components/conversions/components/hierarchy/WeekBlock.tsx). The month header is an expand/collapse toggle (click + Enter/Space keyboard handling), so the month button MUST `stopPropagation` (and not bubble keyboard activation) to avoid toggling expansion on export. The week header is not a toggle; its button calls `stopPropagation` defensively for symmetry. Both show a disabled/spinner state while that group's export is in flight.

## Risks / Trade-offs

- **[Large `.in()` lists at page level]** 90 days ≈ hundreds–low thousands of estimate ids → chunk at 200 ids/query, run sequentially, concatenate. Bounded and infrequent (button click).
- **[JSON in CSV cells]** Commas/quotes/newlines in payload JSON → strict CSV quoting; JSON is serialized compact (no pretty-print) to keep cells single-line. Excel's 32,767-char cell cap is far above per-estimate slice sizes.
- **[Conversion name drift]** Names come from config at export time; if `conversion_action_name` is null (unconfigured), fall back to `conversion_type` so the column is never blank.
- **[Mode filter ≠ filter bar]** Month/week exports honor the mode filter only (the hierarchy is already built from mode-filtered rows; the filter bar also narrows `filteredRows` → hierarchy, so group exports naturally match what's on screen). Page export deliberately bypasses both — documented in the spec so the asymmetry is intentional, not a bug.
- **[Legacy RPC consumers]** Grep shows `export_converted_leads` is called only by the deleted hook; the drop migration is safe. Verified against live DB before archiving.

## Migration Plan

1. Frontend: add export module + week icon + rewire page button; delete legacy hook (one PR, atomic).
2. DB: forward migration `DROP FUNCTION IF EXISTS public.export_converted_leads(date, date);` (confirm exact signature from live catalog before writing — migration files may drift from deployed DB).
3. Rollback: revert frontend commit; restore function from migration `20260513000001`.

## Open Questions

- None blocking. (Confirmed with user: page-level ignores mode filter; legacy RPC fully removed.)
