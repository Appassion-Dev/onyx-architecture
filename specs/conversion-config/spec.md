## Requirements

### Requirement: Conversion action config table
The system SHALL store Google Ads conversion action IDs in a `gads_conversion_config` table with one row per conversion type. Each row maps a `conversion_type` to a nullable `conversion_action_id` (the numeric ID from Google Ads — NULL until configured), a `conversion_action_name` (human-readable label for the dashboard), an `enabled` boolean (controls whether discovery creates pending rows for this type), and a `dry_run` boolean (controls whether upload actually sends to Google Ads).

#### Scenario: Config table has three conversion types
- **WHEN** the system is configured for all three funnels
- **THEN** the table contains rows for `'booking_lead'`, `'qualified_lead'`, and `'converted_lead'`, each with `conversion_action_id` set (or NULL if not yet configured), `enabled`, and `dry_run` flags

#### Scenario: Config entry is missing for a type
- **WHEN** the `'converted_lead'` row is absent from the config table
- **THEN** the discovery function skips converted lead discovery (no row = treated as disabled) and the upload function leaves any existing pending converted_lead rows untouched

#### Scenario: Config entry exists but conversion_action_id is NULL
- **WHEN** the `'qualified_lead'` row exists with `enabled = true` but `conversion_action_id = NULL`
- **THEN** discovery creates pending rows (enabled is true), but the upload function cannot resolve a conversion action — it leaves the row pending with `error_message` set and `upload_attempts` incremented

#### Scenario: Config entry is updated
- **WHEN** the conversion action ID for `'qualified_lead'` is changed in the dashboard
- **THEN** subsequent upload runs use the new action ID for pending rows (the resolved action is written to each row at upload time as a historical record)

#### Scenario: Conversion type is disabled
- **WHEN** the `'booking_lead'` row has `enabled = false`
- **THEN** the discovery function creates no booking_lead pending rows, and the upload function skips any existing pending booking_lead rows

#### Scenario: Conversion type is in dry_run mode
- **WHEN** the `'qualified_lead'` row has `enabled = true` and `dry_run = true`
- **THEN** the discovery function creates pending rows normally, but the upload function leaves them as pending without sending to Google Ads

### Requirement: Dashboard config page for conversion mappings
The dashboard SHALL provide a configuration page where an authenticated user can view and edit the conversion action ID for each conversion type.

#### Scenario: User views conversion config
- **WHEN** a user navigates to the conversion config page
- **THEN** they see a table with conversion type, action ID, action name, enabled toggle, and dry_run toggle for each configured type

#### Scenario: User updates an action ID
- **WHEN** a user changes the action ID for `'qualified_lead'` and saves
- **THEN** the `gads_conversion_config` row is updated and the change takes effect on the next upload run

#### Scenario: User toggles enabled/dry_run
- **WHEN** a user toggles `enabled` to false for `'booking_lead'` and saves
- **THEN** the next discovery run skips booking lead scanning; existing pending booking_lead rows remain but are not uploaded

#### Scenario: Config page requires authentication
- **WHEN** an unauthenticated user attempts to access the config page
- **THEN** they are redirected to the login page

### Requirement: Config edge function
The system SHALL provide an edge function to read and update the `gads_conversion_config` table, with JWT authentication for write operations.

#### Scenario: GET returns all config rows
- **WHEN** an authenticated user sends a GET request
- **THEN** the function returns all rows from `gads_conversion_config`

#### Scenario: PUT updates a single config row
- **WHEN** an authenticated user sends a PUT with `{ conversion_type: 'qualified_lead', conversion_action_id: '789012345' }`
- **THEN** the row is upserted and the response confirms the update

#### Scenario: Unauthenticated write is rejected
- **WHEN** a request without a valid JWT attempts a PUT
- **THEN** the function returns 401 Unauthorized