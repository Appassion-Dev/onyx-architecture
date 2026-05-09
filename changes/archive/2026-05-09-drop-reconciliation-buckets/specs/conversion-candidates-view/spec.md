## REMOVED Requirements

### Requirement: Reconciliation view exposes 4-bucket source breakdown
**Reason**: The 4-bucket aggregation (form / calls / thumbtack / other) was a legacy reporting layer that collapsed the 7-channel taxonomy back to 4 coarse categories. The only consumer (`ConversionReportingPage`) was never routed and never rendered the data. With the channel taxonomy authoritative, the buckets provide no value and create maintenance surface.

**Migration**: No migration needed for consumers — no live page read these columns. `UploadReportPage` (the live upload reporting page) only read `local_uploaded_count`, `gclid_count`, `google_successful_count`, `google_failed_count`, and `amount` from the view.

#### Scenario: Reconciliation view no longer includes bucket columns
- **WHEN** a query selects from `vw_gads_upload_reconciliation_daily`
- **THEN** the result does NOT include `form_uploaded_count`, `calls_uploaded_count`, `thumbtack_uploaded_count`, `other_uploaded_count`, `form_gclid_count`, `calls_gclid_count`, `thumbtack_gclid_count`, `other_gclid_count`, `form_amount`, `calls_amount`, `thumbtack_amount`, or `other_amount`

## ADDED Requirements

### Requirement: Reconciliation view schema is aligned with channel taxonomy
The `vw_gads_upload_reconciliation_daily` view SHALL NOT contain any source-bucket aggregation columns. The view's schema SHALL consist solely of: `event_key`, `event_label`, `event_sort_order`, `conversion_action_id`, `conversion_action_name`, `reporting_date`, `local_uploaded_count`, `gclid_count`, `amount`, `google_successful_count`, `google_failed_count`, `has_local_data`, `has_google_data`, and `latest_google_synced_at`.

#### Scenario: SELECT * returns no bucket columns
- **WHEN** `SELECT * FROM vw_gads_upload_reconciliation_daily` is executed
- **THEN** the result set contains no columns named `form_*`, `calls_*`, `thumbtack_*`, or `other_*`
