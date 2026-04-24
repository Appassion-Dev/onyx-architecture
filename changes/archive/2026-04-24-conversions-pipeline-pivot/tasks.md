## 1. Database: Pipeline View

- [x] 1.1 Create migration for `vw_gads_conversion_pipeline` view that pivots `gads_conversion_uploads` by estimate, joining `estimates`, `estimate_options`, `estimates_settings`, `customers`, `jobs`, `booking_tags`, `callrail_leads`
- [x] 1.2 Implement per-stage columns (booking_status, qualified_status, converted_status, plus upload_attempts, gclid, uploaded_at, error_message, conversion_value, conversion_datetime per stage)
- [x] 1.3 Implement `display_value` using CASE WHEN total_amount_source = 'JOB' logic matching `fn_get_sales_table_data`
- [x] 1.4 Implement `booking_source` column (form/call/null) from `is_booking_form` and `callrail_leads`
- [x] 1.5 Implement `is_closed` boolean (all existing stages uploaded or skipped)
- [x] 1.6 Grant SELECT on the new view to authenticated and service_role

## 2. Frontend: Pipeline Table Component

- [x] 2.1 Define `PipelineRow` TypeScript interface matching the new view columns
- [x] 2.2 Replace the data query in ConversionsPage to fetch from `vw_gads_conversion_pipeline` ordered by `estimate_created_at` desc
- [x] 2.3 Rewrite `buildHierarchy` to group by month → week → pipeline rows (remove type grouping level)
- [x] 2.4 Update `computeStats` for the new data shape (qty = estimate count, value = sum of display_value)

## 3. Frontend: Pipeline Row Rendering

- [x] 3.1 Create `PipelineStatusIcon` component mapping stage status to Lucide icons (CheckCircle2, Clock, XCircle, MinusCircle) with correct colors
- [x] 3.2 Create `ClosedIcon` component (CheckSquare green / Square gray)
- [x] 3.3 Rewrite `ConversionRowItem` as `PipelineRowItem` with columns: Est#, Customer, Source, Job#, Value, Booking, Qualified, Converted, Closed
- [x] 3.4 Implement expandable detail panel showing per-stage info (source, GCLID, value, uploaded_at, error_message, upload_attempts)

## 4. Frontend: Cleanup

- [x] 4.1 Remove type/status filter state and dropdowns from the page header
- [x] 4.2 Remove `TypeGroup` interface, `TYPE_SORT_ORDER`, `expandedTypes` state, and type-level collapsible rendering
- [x] 4.3 Update month/week headers to show simplified rollups (qty + value only)
- [x] 4.4 Verify Scan Now, Upload Pending, Settings, and Refresh buttons still work correctly with the new data shape
