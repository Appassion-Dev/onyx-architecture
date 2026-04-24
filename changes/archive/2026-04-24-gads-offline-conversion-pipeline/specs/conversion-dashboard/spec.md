## ADDED Requirements

### Requirement: Conversions dashboard page
The dashboard SHALL provide a dedicated page for viewing all Google Ads conversion uploads from `gads_conversion_uploads`, accessible from the main navigation.

#### Scenario: User navigates to conversions page
- **WHEN** an authenticated user clicks the conversions link in the navigation
- **THEN** they see a page listing all conversion upload records

#### Scenario: Unauthenticated access is blocked
- **WHEN** an unauthenticated user attempts to access the conversions page
- **THEN** they are redirected to the login page

### Requirement: Group conversions by date
The conversions page SHALL group records by date (derived from `conversion_datetime`), showing each date as a collapsible section with its conversion rows.

#### Scenario: Multiple dates displayed
- **WHEN** the audit table contains conversions from April 14, April 15, and April 16
- **THEN** the page shows three date sections in reverse chronological order (newest first), each listing its conversions

#### Scenario: Date section shows summary counts
- **WHEN** a date section contains 3 uploaded, 1 pending (never tried), and 1 pending (retrying with error)
- **THEN** the section header displays the date, total count (5), and a breakdown by status (e.g., badges or colored indicators distinguishing fresh pending from errored pending)

### Requirement: Display conversion details per row
Each conversion row SHALL display: conversion type (booking lead / qualified lead / converted lead), status (pending / uploaded / skipped), GCLID (or "Enhanced only"), conversion value and currency (or "—" for booking leads), estimate number, customer name, upload timestamp, and upload attempts count. Rows with `upload_attempts > 0` and `status = 'pending'` (i.e., retrying after error) SHALL display the `error_message` to help diagnose failures.

#### Scenario: Uploaded conversion row
- **WHEN** a row has `status = 'uploaded'`, `conversion_type = 'qualified_lead'`, `gclid = 'abc123'`, `conversion_value = 150.00`
- **THEN** it displays with a green status indicator, "Qualified Lead" label, GCLID value, "$150.00 USD", and the uploaded_at timestamp

#### Scenario: Pending conversion row with error (retrying)
- **WHEN** a row has `status = 'pending'`, `upload_attempts = 3`, `error_message = 'GCLID expired'`
- **THEN** it displays with a red/warning status indicator showing it has been attempted and is retrying, with the error message visible (e.g., via tooltip or expandable detail)

#### Scenario: Pending conversion row (never tried)
- **WHEN** a row has `status = 'pending'` and `upload_attempts = 0`
- **THEN** it displays with a yellow/amber status indicator showing it awaits upload

#### Scenario: Booking lead with no value
- **WHEN** a row has `conversion_type = 'booking_lead'` and `conversion_value = NULL`
- **THEN** the value column displays "—" instead of a dollar amount

### Requirement: Cross-phase lead correlation in display
The conversions page SHALL visually correlate conversion rows that belong to the same lead (same `estimate_id`), allowing the user to see the full funnel progression for a single lead.

#### Scenario: Three phases for one estimate shown together
- **WHEN** the audit table has booking_lead, qualified_lead, and converted_lead rows all with `estimate_id = 'est_123'`
- **THEN** the dashboard groups or visually links these three rows, showing the funnel progression from booking → qualified → converted

#### Scenario: Converted lead shows job reference
- **WHEN** a converted_lead row has `job_id = 'job_456'`
- **THEN** the row displays the job reference (e.g., invoice number or job ID) alongside the estimate reference

### Requirement: GCLID source attribution
Each conversion row SHALL display the GCLID source indicator: `'booking'` (from booking form), `'call'` (from CallRail), or `'both'` (GCLID present in both sources). When both exist, the secondary (non-uploaded) GCLID is also visible.

#### Scenario: Estimate with booking form GCLID only
- **WHEN** an estimate has a GCLID in `booking_tags` but no correlated `callrail_leads` GCLID
- **THEN** the source indicator shows "Booking" and displays the GCLID

#### Scenario: Estimate with CallRail GCLID only
- **WHEN** an estimate has no `booking_tags` GCLID but a correlated `callrail_leads` GCLID
- **THEN** the source indicator shows "Call" and displays the GCLID

#### Scenario: Estimate with both GCLID sources
- **WHEN** an estimate has GCLIDs from both `booking_tags` and `callrail_leads`
- **THEN** the source indicator shows "Both", the uploaded GCLID (from booking_tags) is primary, and the secondary GCLID (from callrail_leads) is visible on expansion or tooltip

### Requirement: Filter by conversion type and status
The conversions page SHALL allow filtering by conversion type, by status, and by error state (pending rows with upload_attempts > 0).

#### Scenario: Filter to qualified leads only
- **WHEN** the user selects "Qualified Lead" from the conversion type filter
- **THEN** only rows with `conversion_type = 'qualified_lead'` are displayed

#### Scenario: Filter to errored uploads
- **WHEN** the user selects "Errored" from the status filter
- **THEN** only rows with `status = 'pending'` and `upload_attempts > 0` are displayed, showing rows that are retrying after failures

#### Scenario: Combined filters
- **WHEN** the user selects "Converted Lead" type and "Pending" status
- **THEN** only pending converted lead rows are shown

### Requirement: Conversions SQL view for dashboard
The system SHALL provide a SQL view `vw_gads_conversions` that joins `gads_conversion_uploads` with estimate, customer, and job data to supply the dashboard page with a single denormalized query source. The view includes a `gclid_source` indicator and both primary and secondary GCLIDs.

#### Scenario: View returns all fields needed by dashboard
- **WHEN** the dashboard queries `vw_gads_conversions`
- **THEN** each row includes: conversion_type, status, gclid (uploaded), conversion_value, conversion_currency, conversion_datetime, uploaded_at, error_message, upload_attempts, estimate_id, customer_name (first + last), job_id, job_invoice_number, gclid_source ('booking'/'call'/'both'), booking_gclid, call_gclid

#### Scenario: View handles converted lead with job data
- **WHEN** a converted_lead row has `job_id = 'job_456'`
- **THEN** the view joins to the `jobs` table and includes the job's `invoice_number` and `total_amount`

#### Scenario: View resolves GCLID source from both tables
- **WHEN** an estimate has GCLIDs in both `booking_tags` and `callrail_leads`
- **THEN** the view returns `gclid_source = 'both'`, `booking_gclid` from booking_tags, and `call_gclid` from callrail_leads
