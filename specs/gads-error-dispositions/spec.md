# gads-error-dispositions

## Purpose

Map every Google Ads error code to an operator-configurable disposition that drives retry, triage, and muting behavior, project that disposition onto upload rows via a view, and let operators edit dispositions through an admin page while preserving overrides across catalog re-seeds.

## Requirements

### Requirement: Disposition lookup table

The system SHALL provide a table `gads_error_dispositions` with PK `error_code text` matching the catalog keyspace `"<namespace>.<ENUM_NAME>"`. The table SHALL have these columns:

- `error_code text PRIMARY KEY`
- `disposition text NOT NULL` with CHECK constraint `disposition IN ('retry', 'fix-config', 'fix-data', 'fix-triage', 'drop', 'deliberate')`
- `max_attempts integer` (NULL = unlimited within the 90-day window)
- `retry_after_seconds integer NOT NULL DEFAULT 0`
- `no_alert boolean NOT NULL DEFAULT false`
- `human_action text` (operator-facing remediation copy)
- `notes text`
- `source text NOT NULL DEFAULT 'override'` with values either `'override'` or a string starting with `'proto-'` (e.g., `'proto-v23-seed'`)
- `updated_at timestamptz NOT NULL DEFAULT now()`
- `updated_by uuid` (nullable; references `auth.users.id`)

#### Scenario: Disposition row insertion

- **WHEN** the seed migration runs against an empty `gads_error_dispositions` table
- **THEN** one row SHALL be inserted for every entry in the error catalog
- **THEN** each seeded row SHALL have `source = 'proto-v23-seed'` and a sensible default `disposition` per the rules in [Disposition seed defaults](#requirement-disposition-seed-defaults)

#### Scenario: Constraint enforcement

- **WHEN** an insert or update attempts to set `disposition` to a value outside the six allowed strings
- **THEN** the database SHALL reject the write with a CHECK constraint violation

### Requirement: Disposition seed defaults

The seed migration SHALL populate `gads_error_dispositions` from `supabase/generated/gads_error_catalog.json` with the following default `disposition` assignments per error semantics:

- Codes Google's proto documentation describes as transient (e.g., `INTERNAL_ERROR`, `TRANSIENT_ERROR`, `RESOURCE_TEMPORARILY_EXHAUSTED`): `retry`
- Codes that map to "the customer must change a setting in Google Ads" (e.g., `CUSTOMER_NOT_ACCEPTED_CUSTOMER_DATA_TERMS`, `CONVERSION_TRACKING_NOT_ENABLED`, `INVALID_CUSTOMER_ID`, `TOO_MANY_CONVERSIONS_IN_REQUEST`): `fix-config`
- Codes that indicate a malformed payload we can fix in our code (e.g., `INVALID_HASHED_PHONE_NUMBER_FORMAT`, `INVALID_CONVERSION_DATE_TIME`, `HASHED_FORMAT_REQUIRED`): `fix-data`
- Codes the proto explicitly documents as expected and ignorable (e.g., `CLICK_NOT_FOUND` for Enhanced Conversions for Leads, `EXPIRED_EVENT`, `DUPLICATE_CLICK_CONVERSION_IN_REQUEST`): `drop` with `no_alert = true`
- All other codes default to `fix-triage`

`human_action` SHALL be seeded from the proto `description` for the enum, with operator-readable phrasing where the proto comment is terse.

#### Scenario: Transient codes seeded as retry

- **WHEN** the seed migration encounters a catalog entry whose description matches transient semantics
- **THEN** the row SHALL be inserted with `disposition = 'retry'` and a non-zero `retry_after_seconds` where the proto specifies one (e.g., 21600 for `TOO_RECENT_EVENT`)

#### Scenario: Documented-ignorable codes seeded muted

- **WHEN** the seed migration encounters `conversionUploadError.CLICK_NOT_FOUND` or another code documented as expected
- **THEN** the row SHALL be inserted with `disposition = 'drop'` and `no_alert = true`

### Requirement: View projects disposition onto upload rows

The system SHALL provide a database view `vw_gads_conversion_uploads` that left-joins `gads_conversion_uploads` to `gads_error_dispositions` on `error_code` and projects every column of the underlying table plus computed columns `disposition`, `no_alert`, and `human_action` derived from the joined disposition row. Reads from this view SHALL reflect changes to `gads_error_dispositions` immediately with no backfill required.

#### Scenario: Computed disposition reflects current table state

- **WHEN** an operator updates `gads_error_dispositions` to change `EXPIRED_EVENT`'s disposition from `drop` to `retry`
- **THEN** every existing `gads_conversion_uploads` row with `error_code = 'conversionUploadError.EXPIRED_EVENT'` SHALL show `disposition = 'retry'` on the very next read from the view
- **THEN** no row in `gads_conversion_uploads` SHALL require an UPDATE for the change to take effect

#### Scenario: Rows without an error_code

- **WHEN** a row in `gads_conversion_uploads` has `error_code = NULL`
- **THEN** the view's `disposition`, `no_alert`, and `human_action` columns SHALL be NULL for that row
- **THEN** the row SHALL still appear in the view (left join, not inner join)

### Requirement: Dispositions admin page

The system SHALL provide a Workbench page at `/conversions/dispositions` where any logged-in dashboard user can view and edit the `gads_error_dispositions` table. The page SHALL list every disposition row with editable fields for `disposition` (dropdown of the six values), `max_attempts`, `retry_after_seconds`, `no_alert` (checkbox), and `human_action` (text). Saving an edit SHALL set `source = 'override'`, `updated_at = now()`, and `updated_by = auth.uid()`.

#### Scenario: Logged-in user can edit any row

- **WHEN** a logged-in dashboard user edits a disposition row
- **THEN** the save SHALL succeed regardless of any specific role or claim
- **THEN** the persisted row SHALL have `source = 'override'`, `updated_at = now()`, and `updated_by` set to the editing user's ID

#### Scenario: Override badge surfaces editor-modified rows

- **WHEN** a disposition row has `source = 'override'`
- **THEN** the admin page SHALL display an "✎ Overridden" badge next to the error code
- **THEN** a row-level menu SHALL offer "Reset to seed default" which restores the seed values and sets `source` back to the most recent `proto-vNN-seed` string

#### Scenario: Unknown observed codes surface as actionable

- **WHEN** any row in `gads_conversion_uploads` has an `error_code` for which no `gads_error_dispositions` row exists
- **THEN** the admin page SHALL show an "Unknown codes" callout listing those codes
- **THEN** clicking an unknown code SHALL open a "Create disposition" form pre-filled with that error code

### Requirement: Catalog sync preserves operator overrides

When the catalog sync script regenerates the catalog JSON and the migration runs to re-seed dispositions, rows where `source = 'override'` SHALL be left untouched. Rows where `source` starts with `proto-` MAY have `human_action`, `notes`, and the proto-derived metadata refreshed to the new seed values.

#### Scenario: Override survives proto bump

- **WHEN** a maintainer ran `npm run sync:gads-errors` (producing an updated catalog) and the re-seed migration runs
- **AND** an operator had previously changed `conversionUploadError.EXPIRED_EVENT` from `drop` to `retry` (row now has `source = 'override'`)
- **THEN** the row SHALL remain with `disposition = 'retry'` after the migration
- **THEN** the row SHALL retain its operator-edited values for every column the override touched

#### Scenario: Seed-only row gets fresh description

- **WHEN** the new catalog updates the proto `description` for a code whose disposition row has `source = 'proto-v23-seed'`
- **THEN** the re-seed migration SHALL update that row's `human_action` and `notes` to the new defaults
- **THEN** the row's `source` SHALL be updated to the new seed identifier (e.g., `'proto-v24-seed'`)
