## ADDED Requirements

### Requirement: Upload pending conversions to Google Ads
The system SHALL provide an edge function that reads all rows from `gads_conversion_uploads` with `status = 'pending'`, checks `gads_conversion_config` for each row's `conversion_type` (skipping types where `enabled = false` or `dry_run = true`), resolves the `conversion_action` resource name, fetches customer contact data (email and mobile_number) via `estimates.customer_id` → `customers` for enhanced conversions, builds Google Ads API conversion payloads, and uploads them via the `uploadClickConversions` endpoint. On each attempt (success or failure), the function increments `upload_attempts`.

#### Scenario: Pending row with GCLID is uploaded
- **WHEN** a pending row has `gclid` populated and a matching enabled `conversion_type` in `gads_conversion_config` with a non-null `conversion_action_id`
- **THEN** the function resolves the `conversion_action` resource name from config, builds an `AdsConversion` payload with the GCLID, conversion action, datetime, value (if present), and currency, and includes it in the batch upload. If the estimate's customer has email or mobile_number, they are hashed and included as `userIdentifiers` alongside the GCLID.

#### Scenario: Pending row without GCLID but with hashed identifiers
- **WHEN** a pending row has `gclid = NULL` but the estimate's customer has email or mobile_number
- **THEN** the function builds the payload with `userIdentifiers` (SHA-256 hashed email and/or phone) and consent fields for enhanced conversions

#### Scenario: Pending row with neither GCLID nor contact data
- **WHEN** a pending row has no GCLID and the estimate's customer has no email or mobile_number
- **THEN** the row's status is updated to `'skipped'` with an error message

#### Scenario: Successful upload updates audit status
- **WHEN** the Google Ads API accepts the conversion
- **THEN** the row's status is updated from `'pending'` to `'uploaded'`, `uploaded_at` is set to now, `upload_attempts` is incremented, `error_message` is cleared (set to NULL), and the resolved `conversion_action` resource name is written to the row as a historical record

#### Scenario: Partial failure keeps row pending
- **WHEN** the Google Ads API returns a partial failure for a specific conversion
- **THEN** that row's status remains `'pending'`, `upload_attempts` is incremented, `error_message` is set to the error from the API, and the resolved `conversion_action` is still written to the row. The next cron run will re-attempt this row.

#### Scenario: Upload function is idempotent
- **WHEN** the upload function runs and finds no `'pending'` rows (or all pending rows belong to disabled/dry_run types)
- **THEN** it returns immediately with `{ uploaded: 0, skipped: 0 }` and makes no API calls

### Requirement: Enhanced conversions with hashed user data
The upload function SHALL fetch customer `email` and `mobile_number` from the `customers` table via `estimates.customer_id` for each pending row, then hash them per Google's enhanced conversion requirements before including them in the payload.

#### Scenario: Gmail address normalization
- **WHEN** customer email is `User.Name+tag@gmail.com`
- **THEN** the function normalizes to `username@gmail.com` (lowercase, remove dots, strip plus alias) then SHA-256 hashes

#### Scenario: Phone normalization to E.164
- **WHEN** customer `mobile_number` is `(555) 123-4567`
- **THEN** the function normalizes to `+15551234567` then SHA-256 hashes

#### Scenario: Consent fields included with identifiers
- **WHEN** user identifiers are present in the payload
- **THEN** the payload includes `consent: { adUserData: "GRANTED", adPersonalization: "GRANTED" }`

### Requirement: Per-type conversion action resolution from config
The upload function SHALL look up each pending row's `conversion_type` in the `gads_conversion_config` table to resolve the `conversion_action_id`, then build the full resource name (`customers/{customerId}/conversionActions/{actionId}`). The resolved `conversion_action` is written back to the audit row after upload as a historical record. The `conversion_action` column in `gads_conversion_uploads` is nullable — NULL at discovery time, filled at upload time. The upload function also checks the `enabled` and `dry_run` flags per type.

#### Scenario: Different rows have different conversion actions
- **WHEN** the pending rows include a booking lead (config maps to action ID 123) and a qualified lead (config maps to action ID 456)
- **THEN** each row's payload uses the conversion action resolved from the config table for its `conversion_type`

#### Scenario: No configured conversion action for a type
- **WHEN** a pending row has `conversion_type = 'converted_lead'` but the matching config row has `conversion_action_id = NULL`
- **THEN** the row is left as `'pending'` (not skipped), `upload_attempts` is incremented, and `error_message` is set to indicate missing config. The next upload run will re-check.

#### Scenario: Conversion type is disabled in config
- **WHEN** a pending row has `conversion_type = 'booking_lead'` and the config row has `enabled = false`
- **THEN** the row is left as `'pending'` and excluded from this upload run (not attempted, not skipped)

#### Scenario: Conversion type is in dry_run mode
- **WHEN** a pending row has `conversion_type = 'qualified_lead'` and the config row has `dry_run = true`
- **THEN** the row is left as `'pending'` and excluded from this upload run. The row accumulates visibly in the dashboard.

#### Scenario: Config action ID changes between discovery and upload
- **WHEN** a pending row was discovered when config had action ID 123, but by upload time config has action ID 456
- **THEN** the upload uses the current config value (456) and writes it to the row — the row always reflects what was actually uploaded

### Requirement: Batch upload with partial failure handling
The upload function SHALL send all pending conversions in a single batch request with `partialFailure: true` and process per-row results.

#### Scenario: Mixed success and failure in batch
- **WHEN** a batch of 5 conversions is uploaded and 2 fail with expired GCLID errors
- **THEN** the 3 successful rows are marked `'uploaded'` (error_message cleared, upload_attempts incremented) and the 2 failed rows remain `'pending'` (error_message set, upload_attempts incremented). The next cron run re-attempts the 2 pending rows.

#### Scenario: Complete API failure
- **WHEN** the Google Ads API returns a non-200 response
- **THEN** all pending rows remain in `'pending'` status, `upload_attempts` is incremented for each, `error_message` is set to the API error, and the error is logged; the next cron run will reattempt
