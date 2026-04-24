## ADDED Requirements

### Requirement: Job record displayed in Converted Lead detail
The system SHALL display job details inside the Converted Lead section. The job is found via `jobs.original_estimate_id` matching an `estimate_options.id` for the estimate. The system SHALL show: invoice_number, work_status (with colored badge), total_amount, and outstanding_balance.

#### Scenario: Converted lead with a job
- **WHEN** a pipeline row is expanded and a job exists for the estimate's approved option(s)
- **THEN** the Converted Lead section displays the job's invoice number, status badge, total, and outstanding balance

#### Scenario: No job exists
- **WHEN** a pipeline row is expanded and no job exists for the estimate's options
- **THEN** the Converted Lead section displays "No job created yet"

### Requirement: Converted section always renders
The system SHALL render the Converted Lead section even when `converted_status` is null, to show job data when available.

#### Scenario: Converted status is null but job exists
- **WHEN** `converted_status` is null and a job record exists
- **THEN** the Converted Lead section renders with the job details

### Requirement: Job work_status badge coloring
The system SHALL color job status badges as: `complete rated` and `complete unrated` in green, `scheduled` in blue, `in progress` in yellow, `needs scheduling` in gray, `user canceled` and `pro canceled` in red.

#### Scenario: Completed job badge
- **WHEN** a job has `work_status = 'complete rated'`
- **THEN** the badge displays "Complete" with green styling
