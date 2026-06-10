## ADDED Requirements

### Requirement: HCP deep-link for the job in Converted Lead detail
The Converted Lead detail SHALL include an external link icon (`ExternalLink`) positioned next to the job ID that opens the job in HousecallPro at `https://pro.housecallpro.com/app/jobs/{job.id}` in a new tab. The link SHALL include `target="_blank"` and `rel="noopener noreferrer"`.

#### Scenario: Link opens the job in HCP
- **WHEN** a pipeline row is expanded, a job exists, and the user clicks the `ExternalLink` icon next to the job ID
- **THEN** a new browser tab SHALL open at `https://pro.housecallpro.com/app/jobs/{job.id}`

#### Scenario: Icon position
- **WHEN** the Converted Lead detail renders a job
- **THEN** the `ExternalLink` icon SHALL appear directly next to the job ID heading
