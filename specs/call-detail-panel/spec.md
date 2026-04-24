## Requirements

### Requirement: Lazy-load call records on expand
When a pipeline row is expanded and `call_count > 0`, the system SHALL fetch callrail_leads records for that estimate via a separate Supabase query.

#### Scenario: Expand row with calls
- **WHEN** user expands a pipeline row where `call_count = 3`
- **THEN** the system fetches all 3 callrail_leads records for that estimate_id
- **AND** results are ordered by `call_started_at` descending (most recent first)

#### Scenario: Expand row with no calls
- **WHEN** user expands a pipeline row where `call_count = 0`
- **THEN** no callrail query is made and no call table is rendered

#### Scenario: Re-expand same row
- **WHEN** user collapses and re-expands the same row
- **THEN** the previously fetched call records are served from TanStack Query cache without a new network request

### Requirement: Call history table
The expanded detail panel SHALL display a compact table of all callrail records for the estimate, showing key call information.

#### Scenario: Call table columns
- **WHEN** the call history table is rendered
- **THEN** it displays columns: Date, Type (answered/missed/voicemail/form), Duration, Source, Lead Status, GCLID

#### Scenario: Call duration formatting
- **WHEN** a call has `duration = 272` (seconds)
- **THEN** it is displayed as `4:32`

#### Scenario: Form submission in call table
- **WHEN** a callrail record has `event_type = 'form_submission'`
- **THEN** the Type column shows "Form" and Duration shows "—"

#### Scenario: Call table position
- **WHEN** the detail panel is expanded and both stage details and call history exist
- **THEN** the call history table appears below the stage details section