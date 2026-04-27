## MODIFIED Requirements

### Requirement: Pipeline table with estimate-per-row layout
The Uploads page under the Conversions navigation group SHALL display a table where each row represents one estimate, with columns: Est#, Customer, Source, Job#, Value, Booking (sync icon), Qualified (sync icon), Converted (sync icon), Closed (icon).

#### Scenario: User opens uploads workbench
- **WHEN** an authenticated user navigates to the Uploads child page
- **THEN** the page renders the estimate-per-row pipeline workbench instead of the analytics dashboard

#### Scenario: Estimate row with full pipeline
- **WHEN** an estimate has all three stages (booking uploaded, qualified uploaded, converted pending)
- **THEN** the row SHALL show the estimate number, customer name, booking source, job number, display value, a green CheckCircle2 for Booking, a green CheckCircle2 for Qualified, an amber Clock for Converted, and an unchecked Square for Closed

#### Scenario: Estimate row with partial pipeline
- **WHEN** an estimate has only a booking_lead stage (pending, no attempts)
- **THEN** the row SHALL show an amber Clock for Booking, a text dash for Qualified, a text dash for Converted, and an unchecked Square for Closed

### Requirement: Action buttons preserved
The Uploads page header SHALL retain the Scan Now, Upload Pending, Settings, and Refresh buttons with existing behavior.

#### Scenario: Scan Now triggers discovery
- **WHEN** the user clicks Scan Now from the Uploads page
- **THEN** the system SHALL call `discover_pending_conversions()` RPC, show a toast with results, and refresh the table

#### Scenario: Upload Pending triggers upload
- **WHEN** the user clicks Upload Pending from the Uploads page
- **THEN** the system SHALL invoke the `google-ads-conversion-upload` edge function, show a toast with results, and refresh the table