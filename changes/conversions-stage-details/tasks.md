## 1. BookingTagsTable component

- [x] 1.1 Add `BookingTagsTable` component that fetches `booking_tags` for an estimate and renders a key-value table with friendly label mapping (exclude `hsa_ver` and `ref`)
- [x] 1.2 Move `CallHistoryTable` into Booking Lead section; show "No calls recorded" when `call_count = 0`

## 2. EstimateOptionsTable component

- [x] 2.1 Add `EstimateOptionsTable` component that fetches `estimate_options` for an estimate, renders option name, amount, and approval status badge (green/yellow/red/gray)

## 3. JobDetailSection component

- [x] 3.1 Add `JobDetailSection` component that fetches jobs via estimate_options, renders job invoice number, work_status badge, total, and outstanding balance; shows "No job created yet" when no job found

## 4. Update expanded row layout

- [x] 4.1 Wire `BookingTagsTable` + `CallHistoryTable` into Booking Lead section using `has_form` and `call_count` from PipelineRow
- [x] 4.2 Wire `EstimateOptionsTable` into Qualified Lead section
- [x] 4.3 Always render Converted Lead section (even if `converted_status` is null) and wire `JobDetailSection` into it

## 5. Validation

- [x] 5.1 Verify expanded row shows form tags, calls, estimate options, and job details with sample data
