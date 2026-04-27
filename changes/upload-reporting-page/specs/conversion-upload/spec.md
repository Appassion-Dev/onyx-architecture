## ADDED Requirements

### Requirement: Daily reconciliation view includes gclid count and conversion amount
The `vw_gads_upload_reconciliation_daily` view SHALL include two additional columns: `gclid_count` (the number of uploaded rows for that event_key and reporting_date where `gclid IS NOT NULL`) and `amount` (the sum of `conversion_value` for uploaded rows for that event_key and reporting_date). These columns SHALL be present at the aggregate level and also broken out per source bucket where the source-level columns follow the same naming pattern as the existing source bucket counts.

#### Scenario: gclid_count reflects uploaded rows with a non-null gclid
- **WHEN** the view is queried for a given event_key and reporting_date
- **THEN** `gclid_count` equals the count of uploaded rows in `gads_conversion_uploads` for that event_key and date where `gclid IS NOT NULL`

#### Scenario: amount reflects sum of conversion_value for uploaded rows
- **WHEN** the view is queried for a given event_key and reporting_date
- **THEN** `amount` equals the sum of `conversion_value` across all uploaded rows for that event_key and date, or 0 if no rows have a value

#### Scenario: gclid_count and amount are zero when no uploads exist
- **WHEN** there are no uploaded rows for an event_key on a given date
- **THEN** `gclid_count` is 0 and `amount` is 0

#### Scenario: Existing columns are unaffected
- **WHEN** the view is queried after this change
- **THEN** all previously existing columns (`local_uploaded_count`, `form_uploaded_count`, `calls_uploaded_count`, `thumbtack_uploaded_count`, `other_uploaded_count`, `google_successful_count`, `google_failed_count`, `has_local_data`, `has_google_data`, `latest_google_synced_at`) retain their existing behavior and values
