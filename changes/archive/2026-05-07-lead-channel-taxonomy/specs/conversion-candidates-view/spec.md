## MODIFIED Requirements

### Requirement: View exposes source signals for every estimate
The system SHALL include `has_form` (boolean), `lead_source` (text), `channel` (text), `call_count` (integer), `callrail_sources` (text array), `form_utm_source` (text), `form_utm_medium` (text), `form_hsa_src` (text), and `form_ref` (text) on every row, regardless of whether the estimate has been discovered.

`channel` SHALL be the resolved taxonomy channel (one of: `'Google Ads'`, `'GLS'`, `'GMB'`, `'Thumbtack'`, `'Organic'`, `'Direct'`, `'Other'`) computed by the priority chain defined in `conversion-channel-grouping/spec.md`.

`form_utm_source`, `form_utm_medium`, `form_hsa_src`, and `form_ref` are extracted from `booking_tags` and SHALL be NULL when no corresponding tag exists.

#### Scenario: Booking form estimate
- **WHEN** `estimates.is_booking_form = true`
- **THEN** `has_form` is `true`

#### Scenario: Estimate with CallRail calls
- **WHEN** one or more `callrail_leads` rows are correlated to the estimate
- **THEN** `call_count` reflects the count and `callrail_sources` contains the distinct source values

#### Scenario: Booking form estimate with resolved channel
- **WHEN** `estimates.lead_source = 'Google Ads'` (set by the write-time resolver)
- **THEN** `channel = 'Google Ads'`

#### Scenario: Form estimate with UTM tags
- **WHEN** `booking_tags` contains `utm_source = 'google'` for an estimate
- **THEN** `form_utm_source = 'google'`
