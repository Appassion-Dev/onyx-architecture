## ADDED Requirements

### Requirement: Daily upload analytics sync
The system SHALL run a daily analytics sync that queries Google Ads for every enabled conversion type in `gads_conversion_config` that has a non-null `conversion_action_id`.

#### Scenario: Daily sync gathers required analytics slices
- **WHEN** the scheduled upload analytics job runs
- **THEN** it SHALL execute the daily attribution query, the client upload health query, the action upload health query, and the conversion action configuration query for the configured action IDs
- **THEN** it SHALL persist the results as timestamped snapshots in Supabase

#### Scenario: Disabled or unmapped conversion types are excluded
- **WHEN** a conversion type is disabled or has no `conversion_action_id` in `gads_conversion_config`
- **THEN** the analytics sync SHALL exclude that conversion type from Google Ads query scope

### Requirement: Cached dashboard analytics
The system SHALL serve Google Ads upload analytics from cached Supabase data and SHALL derive `action alive` and attribution-rate metrics without issuing additional live Google Ads queries from the dashboard.

#### Scenario: Dashboard reads cached attribution metrics
- **WHEN** an operator opens the upload analytics surface
- **THEN** the system SHALL read the latest stored attribution and health snapshots from Supabase
- **THEN** it SHALL compute `action alive` from recent attribution rows and attribution rate from stored attribution rows plus local upload counts

### Requirement: Upload health snapshots
The system SHALL snapshot both client-level and conversion-action-level upload health so the dashboard can expose platform health and per-action health independently.

#### Scenario: Client and action health are both available
- **WHEN** a daily analytics sync completes successfully
- **THEN** the system SHALL store the latest client upload summary and the latest per-action upload summaries
- **THEN** it SHALL preserve raw `alerts` and `daily_summaries` payloads for later inspection

### Requirement: Configuration drift detection
The system SHALL compare the latest successful conversion action configuration snapshot to the previous successful snapshot and flag drift when tracked action settings change.

#### Scenario: Config drift is detected
- **WHEN** `status`, `primary_for_goal`, `include_in_conversions_metric`, `counting_type`, or `click_through_lookback_window_days` differs between consecutive successful snapshots for the same action
- **THEN** the system SHALL mark that action as having configuration drift

### Requirement: Partial analytics failures remain visible
The system SHALL preserve successful analytics slices from a run even when one or more Google Ads query slices fail.

#### Scenario: One query slice fails during sync
- **WHEN** the analytics sync receives valid data for one analytics slice and an error for another slice in the same run
- **THEN** the system SHALL persist the successful slice
- **THEN** it SHALL record the failed slice as an error instead of discarding the entire run