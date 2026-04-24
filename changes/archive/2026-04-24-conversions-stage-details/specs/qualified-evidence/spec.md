## ADDED Requirements

### Requirement: Estimate options displayed in Qualified Lead detail
The system SHALL display a table of all estimate_options inside the Qualified Lead expanded section. Each row SHALL show the option name, amount (total_amount / 100 formatted as currency), and approval status with a colored badge. Options SHALL be ordered by total_amount descending.

#### Scenario: Estimate with multiple options
- **WHEN** a pipeline row is expanded and the Qualified Lead section renders
- **THEN** all estimate_options for that estimate are displayed in a table with name, amount, and status badge

### Requirement: Approval status badge coloring
The system SHALL color approval status badges as: `approved` and `pro approved` in green, `awaiting response` in yellow, `pro declined` and `declined` in red, `expired` in gray.

#### Scenario: Approved option badge
- **WHEN** an estimate option has `approval_status = 'approved'`
- **THEN** the badge displays "Approved" with green styling

#### Scenario: Awaiting option badge
- **WHEN** an estimate option has `approval_status = 'awaiting response'`
- **THEN** the badge displays "Awaiting" with yellow styling
