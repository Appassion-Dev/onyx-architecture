## 1. Rename BookingManagerPage → OnlineBookingsPage

- [ ] 1.1 Rename `horizon-dashboard/src/components/pages/BookingManagerPage.tsx` to `OnlineBookingsPage.tsx` and rename the exported component to `OnlineBookingsPage`
- [ ] 1.2 Update `App.tsx` import from `BookingManagerPage` to `OnlineBookingsPage` and change route path from `/bookings` to `/online-bookings`
- [ ] 1.3 Update `Sidebar.tsx` nav item: name from "Bookings" to "Online Bookings", path from `/bookings` to `/online-bookings`

## 2. Update ConversionsPage PipelineRow Interface

- [ ] 2.1 Remove `job_id`, `job_invoice_number`, `booking_source`, `booking_value`, `qualified_value`, `converted_value` from `PipelineRow` interface
- [ ] 2.2 Add `has_form` (boolean), `lead_source` (string | null), `callrail_sources` (string[] | null) to `PipelineRow` interface. Verify `call_count` and `display_value` remain.

## 3. Update ConversionsPage Rendering

- [ ] 3.1 Remove job_id and job_invoice_number column headers and cell renderers from the pipeline table
- [ ] 3.2 Replace the `booking_source` text display with multi-badge source rendering: "Form" badge if `has_form`, "Call (N)" badge if `call_count > 0`, `lead_source` badge if set, and individual `callrail_sources` badges. Deduplicate source strings across `lead_source` and `callrail_sources`.
- [ ] 3.3 Remove per-stage value column rendering (booking_value, qualified_value, converted_value). Ensure `display_value` is the single value column shown per estimate row.
- [ ] 3.4 Remove the `SOURCE_LABELS` record and any references to the old booking_source field

## 4. Update Pipeline View (SQL)

- [ ] 4.1 Add `callrail_sources` column to `vw_gads_conversion_pipeline`: aggregate distinct `callrail_leads.source` values per estimate as a text array via LATERAL subquery
- [ ] 4.2 Replace `booking_source` column with `has_form` boolean and `lead_source` text. Drop `job_id`, `job_invoice_number`, and per-stage value columns from the view.

## 5. Validate

- [ ] 5.1 Run the dashboard locally and verify the ConversionsPage renders with source badges, no job columns, and unified display_value
- [ ] 5.2 Verify the OnlineBookingsPage loads at `/online-bookings` and the sidebar link works
- [ ] 5.3 Query `vw_gads_conversion_pipeline` and confirm `callrail_sources`, `has_form`, `lead_source` columns are present with correct data
