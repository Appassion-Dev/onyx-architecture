## MODIFIED Requirements

### Requirement: Upload pending conversions to Google Ads
The system SHALL provide an edge function that reads all rows from `gads_conversion_uploads` with `status = 'pending'` and `conversion_datetime` within the last 90 days (Google Ads rejects conversions outside this window), checks `gads_conversion_config` for each row's `conversion_type` (skipping types where `enabled = false` or `dry_run = true`), resolves the `conversion_action` resource name, fetches customer contact data (email and mobile_number) via `estimates.customer_id` -> `customers` for enhanced conversions using `.limit()` sized to the batch to bypass PostgREST's default 1000-row cap, builds Google Ads API conversion payloads, and uploads them via the `uploadClickConversions` endpoint in a single batched API call. On each attempt (success or failure), the function increments `upload_attempts`. Rows with `conversion_datetime` older than 90 days SHALL be bulk-updated to `status = 'expired'` in the same run.

#### Scenario: Pending row with GCLID is uploaded
- **WHEN** a pending row has `gclid` populated and a matching enabled `conversion_type` in `gads_conversion_config` with a non-null `conversion_action_id`
- **THEN** the function resolves the `conversion_action` resource name from config, builds an `AdsConversion` payload with the GCLID, conversion action, datetime, value (if present), and currency, and includes it in the batch upload. If the estimate's customer has email or mobile_number, they are hashed and included as `userIdentifiers` alongside the GCLID.

#### Scenario: Pending row without GCLID but with hashed identifiers
- **WHEN** a pending row has `gclid = NULL` but the estimate's customer has email or mobile_number
- **THEN** the function builds the payload with `userIdentifiers` (SHA-256 hashed email and/or phone) and consent fields for enhanced conversions

#### Scenario: Pending row with neither GCLID nor contact data
- **WHEN** a pending row has no GCLID and the estimate's customer has no email or mobile_number
- **THEN** the row's status is updated to `'skipped'` with an error message

#### Scenario: Pending row outside 90-day window is expired
- **WHEN** a pending row has `conversion_datetime` older than 90 days from the current time
- **THEN** the row's status is updated to `'expired'` with error message "Outside Google Ads 90-day conversion window" and it is NOT included in the upload batch

#### Scenario: Successful upload updates audit status
- **WHEN** the Google Ads API accepts the conversion
- **THEN** the row's status is updated from `'pending'` to `'uploaded'`, `uploaded_at` is set to now, `upload_attempts` is incremented, `error_message` is cleared (set to NULL), and the resolved `conversion_action` resource name is written to the row as a historical record

#### Scenario: Partial failure keeps row pending
- **WHEN** the Google Ads API returns a partial failure for a specific conversion
- **THEN** that row's status remains `'pending'`, `upload_attempts` is incremented, `error_message` is set to the error from the API, and the resolved `conversion_action` is still written to the row. The next cron run will re-attempt this row.

#### Scenario: Upload function is idempotent
- **WHEN** the upload function runs and finds no `'pending'` rows within the 90-day window (or all pending rows belong to disabled/dry_run types)
- **THEN** it returns immediately with `{ uploaded: 0, skipped: 0 }` and makes no API calls
