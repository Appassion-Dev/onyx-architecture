## ADDED Requirements

### Requirement: Qualified stage cell displays estimate work_status
The qualified stage cell in the pipeline strip SHALL display the estimate's raw `work_status` string as a sub-label beneath the status icon. The value is shown as-is (no condensing or mapping). This applies to both discovered and undiscovered qualified stages.

#### Scenario: Qualified stage cell with complete rated work_status
- **WHEN** a qualified_lead stage cell is rendered and the estimate has `work_status = 'complete rated'`
- **THEN** the cell SHALL show `"complete rated"` as a sub-label beneath the status icon

#### Scenario: Qualified stage cell with complete unrated work_status
- **WHEN** a qualified_lead stage cell is rendered and the estimate has `work_status = 'complete unrated'`
- **THEN** the cell SHALL show `"complete unrated"` as a sub-label beneath the status icon

#### Scenario: Qualified stage cell with non-complete work_status (not yet discovered)
- **WHEN** the qualified_lead stage has not been discovered and the estimate has `work_status = 'needs scheduling'` (or any other non-complete value)
- **THEN** the cell SHALL show the raw work_status string (e.g., `"needs scheduling"`) as a sub-label beneath the status icon

#### Scenario: Qualified stage cell with null work_status
- **WHEN** the estimate's `work_status` is NULL
- **THEN** no sub-label is rendered
