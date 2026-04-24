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

### Requirement: Filter by source
The Conversions page SHALL provide a "Source" dropdown that filters estimates to those with a matching value in their `callrail_sources` array. Options are computed dynamically from all distinct source values in the loaded dataset.

#### Scenario: Dynamic options reflect loaded data
- **WHEN** the Conversions page loads its 90-day dataset
- **THEN** the Source dropdown options contain all distinct non-null values from `callrail_sources` across all rows, plus an "All" option

#### Scenario: Source filter applied
- **WHEN** user selects a specific source (e.g., "Google Ads")
- **THEN** only estimates whose `callrail_sources` array contains that value are shown

### Requirement: Filter by first-touch medium
The Conversions page SHALL provide a "Medium" dropdown with options: All, Form, Call. The medium value comes from the `first_touch_medium` column on each estimate row.

#### Scenario: Filter to form medium
- **WHEN** the Medium dropdown is set to "Form"
- **THEN** only estimates where `first_touch_medium = 'form'` are shown

#### Scenario: Filter to call medium
- **WHEN** the Medium dropdown is set to "Call"
- **THEN** only estimates where `first_touch_medium = 'call'` are shown

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