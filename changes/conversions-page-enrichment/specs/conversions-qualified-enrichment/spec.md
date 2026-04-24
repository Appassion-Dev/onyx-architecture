## ADDED Requirements

### Requirement: Assigned employee in Qualified Lead detail
The Qualified Lead expanded section SHALL display the assigned employee using `EmployeeBadge` (colored dot + name). The color is resolved from `useEmployees()` by matching `assigned_employee_id` to `color_hex`. When no employee is assigned, this row is omitted.

#### Scenario: Assigned employee present
- **WHEN** the estimate has an `assigned_employee_id`
- **THEN** the Qualified Lead detail shows "Assigned:" followed by an `EmployeeBadge` with the employee's name and their color

#### Scenario: No assigned employee
- **WHEN** `assigned_employee_id` is NULL
- **THEN** no "Assigned:" row is rendered in the Qualified Lead detail

### Requirement: CallRail attribution columns in call history table
The call history table in the Booking Lead expanded detail SHALL include `source`, `medium`, and `campaign` columns fetched from `callrail_leads`. These columns display the raw CallRail attribution values for each call record, or a dash when NULL. Medium is displayed capitalized.

#### Scenario: Call with attribution data
- **WHEN** a `callrail_leads` record has non-null `source`, `medium`, and `campaign`
- **THEN** those values appear in their respective columns in the call history table

#### Scenario: Call with missing attribution
- **WHEN** `medium` or `campaign` is NULL
- **THEN** the corresponding cell shows a dash

### Requirement: HCP deep-link per estimate option
Each row in the Estimate Options table SHALL include an external link icon (`ExternalLink`) that opens the option in HousecallPro at `https://pro.housecallpro.com/app/estimates/{option.id}` in a new tab.

#### Scenario: Link opens correct HCP page
- **WHEN** user clicks the `ExternalLink` icon on an estimate option row
- **THEN** a new browser tab opens at `https://pro.housecallpro.com/app/estimates/{option.id}`

### Requirement: Assigned employee column in view
The `vw_conversion_candidates` view SHALL expose `assigned_employee_id` and `assigned_employee_name` columns via a lateral join on `estimates_settings → employees`.

#### Scenario: Estimate with assigned employee
- **WHEN** the estimate has a row in `estimates_settings` with a valid `sales_employee_id`
- **THEN** `assigned_employee_id` and `assigned_employee_name` are populated in the view

#### Scenario: Estimate without assigned employee
- **WHEN** the estimate has no row in `estimates_settings`
- **THEN** `assigned_employee_id` and `assigned_employee_name` are NULL
