## Requirements

### Requirement: vw_conversion_candidates exposes a resolved channel column
The view SHALL include a `channel` TEXT column that resolves each row to one of the seven taxonomy values (`'Google Ads'`, `'GLS'`, `'GMB'`, `'Thumbtack'`, `'Organic'`, `'Direct'`, `'Other'`) using the following priority order:
1. `estimates.lead_source` (non-null value written by the booking resolver)
2. `booking_tags` gclid present → `'Google Ads'`
3. `booking_tags` hsa_src = `'LocalServicesAds'` → `'GLS'`
4. `booking_tags` utm_source mapped to taxonomy channel
5. `booking_tags` ref URL matching google.com/localservices → `'GLS'`
6. `callrail_leads.source` mapped to taxonomy channel
7. `'Other'` (fallback)

#### Scenario: Form booking with resolved lead_source
- **WHEN** `estimates.lead_source = 'Google Ads'`
- **THEN** `channel = 'Google Ads'`

#### Scenario: Form booking with gclid tag but null lead_source (pre-fix row)
- **WHEN** `estimates.lead_source IS NULL` AND `booking_tags` contains key `gclid`
- **THEN** `channel = 'Google Ads'`

#### Scenario: CallRail call with Google Ads source
- **WHEN** `estimates.lead_source IS NULL` AND `callrail_leads.source = 'Google Ads'`
- **THEN** `channel = 'Google Ads'`

#### Scenario: No signals present
- **WHEN** `estimates.lead_source IS NULL` AND no relevant `booking_tags` keys AND no `callrail_leads` row
- **THEN** `channel = 'Other'`

### Requirement: vw_conversion_candidates surfaces booking_tags UTM fields
The view SHALL expose the following columns extracted from the `booking_tags` table for each estimate:
- `form_utm_source` (TEXT) — value of the `utm_source` tag
- `form_utm_medium` (TEXT) — value of the `utm_medium` tag
- `form_hsa_src` (TEXT) — value of the `hsa_src` tag
- `form_ref` (TEXT) — value of the `ref` tag (parent page URL at submission)

All four columns SHALL be NULL when no corresponding tag exists for the estimate.

#### Scenario: Booking with UTM parameters
- **WHEN** `booking_tags` contains `utm_source = 'google'` and `utm_medium = 'cpc'` for an estimate
- **THEN** the view row has `form_utm_source = 'google'` and `form_utm_medium = 'cpc'`

#### Scenario: Booking with no UTM parameters
- **WHEN** `booking_tags` has no `utm_source` or `utm_medium` keys for an estimate
- **THEN** `form_utm_source` and `form_utm_medium` are NULL

### Requirement: ConversionsPage weekly rollup groups by taxonomy channel
The weekly rollup section of the Conversions page SHALL group estimates by the `channel` column from `vw_conversion_candidates`, using the seven taxonomy channel names as the group keys. The rollup SHALL replace the previous 4-bucket medium grouping (calls / form / thumbtack / other).

#### Scenario: Google Ads estimates grouped together
- **WHEN** the weekly rollup renders
- **THEN** all estimates with `channel = 'Google Ads'` appear in a single "Google Ads" group regardless of whether they arrived via form or call

#### Scenario: Taxonomy channel order
- **WHEN** the weekly rollup renders
- **THEN** channel groups are ordered: Google Ads, GLS, GMB, Thumbtack, Organic, Direct, Other
