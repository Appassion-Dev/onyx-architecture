## 1. Database Migration

- [x] 1.1 Create migration file `supabase/migrations/<timestamp>_discover_pending_conversions_for_estimate.sql`
- [x] 1.2 Implement `discover_pending_conversions_for_estimate(p_estimate_id text)` function mirroring `discover_pending_conversions()` logic scoped to a single estimate ID
- [x] 1.3 Grant `EXECUTE` on the function to `service_role`
- [x] 1.4 Apply migration to local Supabase instance and verify the function is callable via `supabase.rpc()`

## 2. Edge Function: Extend `google-ads-conversion-upload`

- [x] 2.1 Parse optional `estimate_ids: string[]` and `conversion_types: string[]` from the POST request body
- [x] 2.2 When `estimate_ids` is provided, add `.in('estimate_id', estimateIds)` filter to the pending-rows query
- [x] 2.3 When `conversion_types` is provided, add `.in('conversion_type', conversionTypes)` filter to the pending-rows query
- [x] 2.4 Verify empty body `{}` still processes all pending rows (cron behavior unchanged)
- [x] 2.5 Test scoped call with a single `estimate_id` + `conversion_type` returns correct subset

## 3. Remove Legacy Upload from `OnlineBookingsPage`

- [x] 3.1 Remove `gads_upload_status` field from `BookingRow` interface
- [x] 3.2 Remove `uploadingEstimate` state and setter
- [x] 3.3 Remove "Conversion Upload" `TableHead` column
- [x] 3.4 Remove the upload status badge and upload `Button` from each `TableRow`
- [x] 3.5 Verify the bookings table still renders correctly without the upload column

## 4. Remove Legacy Upload from `CallsPage`

- [x] 4.1 Remove `gads_upload_status` field from `CallRailRow` interface
- [x] 4.2 Remove `uploadingCall` state and setter
- [x] 4.3 Remove `gads_upload_status` from `SortCol` type and sort handler
- [x] 4.4 Remove "Conv. Upload" `TableHead` column and sort button
- [x] 4.5 Remove the upload status badge and upload `Button` from each call row
- [x] 4.6 Verify the calls table still renders correctly without the upload column

## 5. Remove Legacy Upload from `BookingManagerPage`

- [x] 5.1 Apply the same removals as OnlineBookingsPage (this is the legacy version of the same page)

## 6. Delete `gads-upload-booking` Edge Function

- [x] 6.1 Delete the folder `supabase/functions/gads-upload-booking/`
- [x] 6.2 Confirm no remaining UI references to `gads-upload-booking` in the codebase

## 7. Interactive `PhaseCell` — Hover and Countdown

- [x] 7.1 Add hover state tracking (`isHovered`) to `PhaseCell` component
- [x] 7.2 Hover icon crossfade: render status icon and upload icon stacked with `absolute` positioning; transition `opacity` 1→0 / 0→1 over `duration-150` on hover enter/exit (not an instant swap)
- [x] 7.3 Add countdown state (`isCountingDown`, `cancelled ref`) to `PhaseCell`
- [x] 7.4 On click of an uploadable cell, start countdown: render `Progress` bar at `value={100}` transitioning to `value={0}` with `duration-[5000ms] ease-linear` — easing MUST be linear so the bar reads as a clock
- [x] 7.5 Progress bar indicator color matches cell status accent: amber (`#ffb547`) for pending (first attempt), red (`#ee5d50`) for error retry — NOT `bg-primary` (indigo); track uses `bg-[#e9edf7]`
- [x] 7.6 On countdown start, transition the cell border from its status accent to `--primary` (indigo) over `duration-200` as a visual "arming" cue
- [x] 7.7 Cancel button entry: fade in with `opacity-0 → opacity-100` + `translate-y-1 → translate-y-0` over `duration-150`; clicking it sets cancelled ref and resets state
- [x] 7.8 On countdown expiry (5s `setTimeout`), if not cancelled, call `google-ads-conversion-upload` with `{ estimate_ids: [estimateId], conversion_types: [stageType] }`
- [x] 7.9 Show loading spinner in-cell while upload request is in flight
- [x] 7.10 Upload success flash: after refetch resolves with `status === 'uploaded'`, briefly flash `bg-[#01b574]/20` before settling to standard `bg-[#e8fdf4]` via `transition-colors duration-[600ms]`
- [x] 7.11 On upload response, call `refetch()` on the pipeline query to update the row
- [x] 7.12 Surface dry-run indicator: if the stage's config has `dry_run: true`, show ⚠ label or tooltip during countdown

## 8. Null `PhaseCell` — Discover on Click

- [x] 8.1 When `status === null` and hovered, display a search/discover icon
- [x] 8.2 On click of a null cell, call `supabase.rpc('discover_pending_conversions_for_estimate', { p_estimate_id: estimateId })`
- [x] 8.3 Show a loading state in the cell while the RPC is in flight
- [x] 8.4 On success, call `refetch()` to update the row
- [x] 8.5 If the result shows 0 new rows for all stages, show toast: "No new conversions discovered for this estimate"

## 9. Bulk Upload — Week and Month Headers

- [x] 9.1 Add an Upload button to each week header row in `ConversionsPage`
- [x] 9.2 Add an Upload button to each month header row in `ConversionsPage`
- [x] 9.3 Compute `pendingEstimateIds` for each week/month bucket (estimate IDs where at least one stage is `'pending'`)
- [x] 9.4 Disable the Upload button if `pendingEstimateIds.length === 0` for that bucket
- [x] 9.5 On Upload button click, open a `Dialog` confirm modal with: count message ("Upload N pending conversions in…"), dry-run warning if applicable, Confirm and Cancel buttons
- [x] 9.6 On Cancel in modal, close modal with no action
- [x] 9.7 On Confirm in modal, close modal and show `toast.custom()` with `Progress` bar draining 100→0 over 5s with `ease-linear` easing, indicator color amber (`#ffb547`) matching the pending cell accent, "Uploading N conversions in 5s…" text, and Cancel button
- [x] 9.8 On countdown toast Cancel, dismiss toast with no upload
- [x] 9.9 On countdown expiry, call `google-ads-conversion-upload` with `{ estimate_ids: pendingEstimateIds }` for that bucket
- [x] 9.10 After upload response, call `refetch()` to refresh the page

## 10. Config Query for Dry-Run Awareness

- [x] 10.1 Fetch `gads_conversion_config` in `ConversionsPage` (or a shared hook) to know which stages have `dry_run: true`
- [x] 10.2 Pass dry-run config data to `PhaseCell` so it can show the ⚠ indicator
- [x] 10.3 Pass dry-run config data to bulk upload modal so it can show the warning

## 11. Motion Polish Verification

- [ ] 11.1 Confirm hover icon crossfade is smooth (no hard swap) on pending and error cells
- [ ] 11.2 Confirm countdown Progress bar drains at a constant rate (linear easing) — not slow-fast-slow
- [ ] 11.3 Confirm Progress bar is amber on pending cells and red on error-retry cells (not indigo)
- [ ] 11.4 Confirm Cancel button fades+slides in rather than appearing instantly
- [ ] 11.5 Confirm upload success produces a brief green flash before settling to the uploaded state
- [ ] 11.6 Confirm bulk countdown toast Progress bar also uses linear easing and amber color

## 12. Final Verification

- [ ] 12.1 Confirm no references to `gads-upload-booking` or `gads-upload-call` remain in the frontend codebase
- [ ] 12.2 Verify cron path still works: empty body `{}` to `google-ads-conversion-upload` processes all pending rows
- [ ] 12.3 Smoke test single-cell upload countdown and cancel on a pending row
- [ ] 12.4 Smoke test null cell discover → row transitions to pending
- [ ] 12.5 Smoke test week Upload → modal → toast → upload on a week with pending rows
