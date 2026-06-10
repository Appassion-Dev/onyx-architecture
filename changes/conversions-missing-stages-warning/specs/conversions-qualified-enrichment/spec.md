## MODIFIED Requirements

### Requirement: HCP deep-link per estimate option
Each row in the Estimate Options table SHALL include an external link icon (`ExternalLink`) that opens the option in HousecallPro at `https://pro.housecallpro.com/app/estimates/{option.id}` in a new tab. The icon SHALL be positioned inline within the Option cell, directly after the option name, rather than in a separate trailing column.

#### Scenario: Link opens correct HCP page
- **WHEN** user clicks the `ExternalLink` icon on an estimate option row
- **THEN** a new browser tab opens at `https://pro.housecallpro.com/app/estimates/{option.id}`

#### Scenario: Icon position
- **WHEN** the Estimate Options table renders a row
- **THEN** the `ExternalLink` icon SHALL appear immediately after the option name in the Option cell
- **AND** the table SHALL NOT render a standalone trailing link column
