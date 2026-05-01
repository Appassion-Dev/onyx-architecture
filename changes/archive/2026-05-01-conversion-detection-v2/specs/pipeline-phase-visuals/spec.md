## MODIFIED Requirements

### Requirement: Connected pipeline strip
The Booking, Qualified, and Converted stage cells SHALL be rendered as three independent cells with no connector lines between them. Since all three stages are fully independent events (not a linear progression), the connected-strip metaphor is removed.

#### Scenario: All three phases present
- **WHEN** an estimate has booking, qualified, and converted stages
- **THEN** three phase cells are rendered side by side with no connector lines between them

#### Scenario: Only booking phase present
- **WHEN** an estimate has only a booking_lead upload
- **THEN** the booking phase cell is rendered with its status; the remaining two cells show as empty/inactive with no connector treatment between them

#### Scenario: No phases present
- **WHEN** an estimate has no conversion upload records
- **THEN** all three cells render as empty outlines side by side with no connectors
