## Requirements

### Requirement: Connected pipeline strip
The Booking, Qualified, and Converted stage cells SHALL be rendered as three independent cells with no connector lines between them. Since all three stages are fully independent events (not a linear progression), the connected-strip metaphor is removed.

#### Scenario: All three phases present
- **WHEN** an estimate has booking, qualified, and converted stages
- **THEN** three phase cells are rendered side by side with no connector lines between them

#### Scenario: Only one phase present
- **WHEN** an estimate has only a booking_lead upload
- **THEN** the booking phase is rendered with status, and the remaining phases show as empty/inactive (no connectors)

### Requirement: Phase status visualization
Each pipeline phase cell SHALL display a colored background and icon that communicates the upload status at a glance.

#### Scenario: Uploaded status
- **WHEN** a phase has `status = 'uploaded'`
- **THEN** the phase cell uses a green background tint with a check icon

#### Scenario: Pending status (no errors)
- **WHEN** a phase has `status = 'pending'` and `upload_attempts = 0`
- **THEN** the phase cell uses an amber/warning background tint with a clock icon

#### Scenario: Error status (pending with attempts)
- **WHEN** a phase has `status = 'pending'` and `upload_attempts > 0`
- **THEN** the phase cell uses a red background tint with an error icon

#### Scenario: Skipped status
- **WHEN** a phase has `status = 'skipped'`
- **THEN** the phase cell uses a gray background tint with a skip icon

#### Scenario: Null phase (not yet created)
- **WHEN** a phase has no conversion upload record (status is null)
- **THEN** the phase cell is rendered as an empty outline with a dash

### Requirement: Inline phase data
Each pipeline phase cell SHALL display a relevant data point beneath the status icon when space permits.

#### Scenario: Uploaded phase shows date
- **WHEN** a phase has `status = 'uploaded'` and `uploaded_at` is set
- **THEN** the phase cell shows the upload date in compact format (e.g., "Apr 15")

#### Scenario: Error phase shows message
- **WHEN** a phase has an `error_message`
- **THEN** the phase cell shows a truncated error hint

#### Scenario: Pending phase shows waiting indicator
- **WHEN** a phase has `status = 'pending'` and `upload_attempts = 0`
- **THEN** the phase cell shows "Pending" text

### Requirement: Call count badge
When an estimate has associated calls, the Source column SHALL display a count badge alongside the source type.

#### Scenario: Call source with multiple calls
- **WHEN** `booking_source = 'call'` and `call_count = 3`
- **THEN** the source column displays "Call" with a "(3)" count indicator

#### Scenario: Form source with calls
- **WHEN** `booking_source = 'form'` and `call_count = 2`
- **THEN** the source column displays "Form" with a call count indicator showing 2 associated calls

#### Scenario: No calls
- **WHEN** `call_count = 0`
- **THEN** no call count badge is shown