## REMOVED Requirements

### Requirement: Filter by conversion step (All and Closed options)
**Reason**: The step selector is now a required conversion mode, not an optional filter. "All" has no coherent date or value context. "Closed" is a derived state (all stages uploaded/skipped) not a conversion type.
**Migration**: Users who previously used "All" should use the "Qualified" mode as the default working view. Users who previously used "Closed" can identify closed estimates by their uploaded status badges within any mode tab.

## MODIFIED Requirements

### Requirement: Filter by conversion step
The Conversions page SHALL provide a step selector that sets the active conversion mode. The selector SHALL present four options: Pre-discovery, Booking, Qualified, Converted. There is no "All" or "Closed" option. The selector is always active (there is no unset/default-all state); the default is Qualified on page load.

#### Scenario: Step selector options
- **WHEN** the Conversions page renders the step selector
- **THEN** it SHALL show exactly four tabs: Pre-discovery, Booking, Qualified, Converted
- **AND** there SHALL be no "All" or "Closed" tab

#### Scenario: Default mode on page load
- **WHEN** the Conversions page first loads
- **THEN** the Qualified tab SHALL be active

#### Scenario: Filter to pre-discovery
- **WHEN** the user selects Pre-discovery
- **THEN** only estimates where all three stage columns are NULL are shown
- **AND** the hierarchy groups by `estimate_created_at`

#### Scenario: Filter to has-booking
- **WHEN** the user selects Booking
- **THEN** only estimates where `booking_status IS NOT NULL` are shown
- **AND** the hierarchy groups by `booking_datetime`

#### Scenario: Filter to has-qualified
- **WHEN** the user selects Qualified
- **THEN** only estimates where `qualified_status IS NOT NULL` are shown
- **AND** the hierarchy groups by `qualified_datetime`

#### Scenario: Filter to has-converted
- **WHEN** the user selects Converted
- **THEN** only estimates where `converted_status IS NOT NULL` are shown
- **AND** the hierarchy groups by `converted_datetime`

#### Scenario: Reset filters restores default mode
- **WHEN** the user activates Reset Filters
- **THEN** the step selector SHALL return to Qualified (not "All")
