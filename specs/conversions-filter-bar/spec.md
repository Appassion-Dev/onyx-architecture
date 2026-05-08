## Requirements

### Requirement: Filter by conversion step
The Conversions page SHALL provide a "Step" dropdown that filters the visible estimates by funnel stage. Options are: All, Pre-discovery, Has Booking, Has Qualified, Has Converted, Closed. Filters are inclusive ("has at least this stage"). All filters apply in AND combination with other active filters.

#### Scenario: No filter applied
- **WHEN** the Step dropdown is set to "All"
- **THEN** all estimates in the 90-day window are shown

#### Scenario: Filter to pre-discovery
- **WHEN** the Step dropdown is set to "Pre-discovery"
- **THEN** only estimates where all three stage columns are NULL are shown

#### Scenario: Filter to has-booking
- **WHEN** the Step dropdown is set to "Has Booking"
- **THEN** only estimates where `booking_status IS NOT NULL` are shown

#### Scenario: Filter to closed
- **WHEN** the Step dropdown is set to "Closed"
- **THEN** only estimates where `is_closed = true` are shown

### Requirement: Filter by channel
The Conversions page SHALL provide a "Channel" dropdown that filters estimates to those with a matching `channel` value. Options are the seven taxonomy channel names: All, Google Ads, GLS, GMB, Thumbtack, Organic, Direct, Other.

#### Scenario: Default state
- **WHEN** the Channel dropdown is set to "All"
- **THEN** all estimates in the 90-day window are shown regardless of channel

#### Scenario: Filter to Google Ads
- **WHEN** user selects "Google Ads" from the Channel dropdown
- **THEN** only estimates where `channel = 'Google Ads'` are shown

#### Scenario: Filter to GLS
- **WHEN** user selects "GLS" from the Channel dropdown
- **THEN** only estimates where `channel = 'GLS'` are shown

#### Scenario: Filter to Other
- **WHEN** user selects "Other" from the Channel dropdown
- **THEN** only estimates where `channel = 'Other'` are shown

### Requirement: Filter by campaign
The Conversions page SHALL provide a "Campaign" dropdown that filters estimates to those with a matching value in their `callrail_campaigns` array. Options are computed dynamically from all distinct campaign values in the loaded dataset.

#### Scenario: Campaign filter applied
- **WHEN** user selects a specific campaign name
- **THEN** only estimates whose `callrail_campaigns` array contains that value are shown

### Requirement: Filter by assigned employee
The Conversions page SHALL provide an "Assignee" dropdown that filters estimates by `assigned_employee_id`. Options are loaded from `useEmployees()` and rendered with `EmployeeBadge` (colored dot + name).

#### Scenario: Assignee filter applied
- **WHEN** user selects an employee from the Assignee dropdown
- **THEN** only estimates where `assigned_employee_id` matches the selected employee are shown

#### Scenario: Unassigned estimates
- **WHEN** user selects "Unassigned"
- **THEN** only estimates where `assigned_employee_id IS NULL` are shown