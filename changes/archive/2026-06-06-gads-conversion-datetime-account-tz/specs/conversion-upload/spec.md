## ADDED Requirements

### Requirement: Conversion dateTime is formatted in the configured account timezone

The edge function SHALL format each conversion's `conversionDateTime` field by re-projecting the stored UTC instant into the configured account timezone, emitting the Google Ads format `YYYY-MM-DD HH:MM:SS±HH:MM`. The timezone SHALL be sourced from the `GOOGLE_ADS_ACCOUNT_TIMEZONE` environment variable, defaulting to `America/New_York` when unset. The rendering SHALL be instant-preserving and DST-aware: the wall-clock components and the offset together SHALL denote the same absolute instant as the stored value, with the offset resolved for that specific instant (e.g. `-04:00` during US Eastern daylight time, `-05:00` during standard time). The function SHALL NOT relabel the offset while leaving the UTC wall-clock components unchanged.

#### Scenario: Default timezone renders a summer instant in Eastern daylight time
- **WHEN** the account timezone is unset (defaulting to `America/New_York`) and a row's `conversion_datetime` is `2026-05-15T12:00:00Z`
- **THEN** the `conversionDateTime` sent to Google SHALL be `2026-05-15 08:00:00-04:00`

#### Scenario: Default timezone renders a winter instant in Eastern standard time
- **WHEN** the account timezone defaults to `America/New_York` and a row's `conversion_datetime` is `2026-01-02T03:04:05Z`
- **THEN** the `conversionDateTime` sent to Google SHALL be `2026-01-01 22:04:05-05:00`

#### Scenario: Rendered value denotes the same instant as the stored UTC value
- **WHEN** a row's `conversion_datetime` is rendered in the account timezone
- **THEN** parsing the emitted string SHALL yield the same absolute instant as the stored UTC value, with only the wall-clock representation and offset differing

#### Scenario: Timezone is configurable via environment variable
- **WHEN** `GOOGLE_ADS_ACCOUNT_TIMEZONE` is set to `UTC` and a row's `conversion_datetime` is `2026-05-15T12:00:00Z`
- **THEN** the `conversionDateTime` sent to Google SHALL be `2026-05-15 12:00:00+00:00`

#### Scenario: Midnight in the account timezone renders as 00, not 24
- **WHEN** a row's instant falls exactly at midnight in the account timezone
- **THEN** the emitted hour component SHALL be `00:00:00` (not `24:00:00`)
