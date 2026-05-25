## MODIFIED Requirements

### Requirement: vw_conversion_candidates exposes a resolved channel column
The view SHALL include a `channel` TEXT column that resolves each row to one of the seven taxonomy values (`'Google Ads'`, `'GLS'`, `'GMB'`, `'Thumbtack'`, `'Organic'`, `'Direct'`, `'Other'`) using the following priority order:
1. `estimates.lead_source` (non-null value written by the booking resolver)
2. `booking_tags` gclid present → `'Google Ads'`
3. `booking_tags` hsa_src = `'LocalServicesAds'` → `'GLS'`
4. `booking_tags` utm_source mapped to taxonomy channel
5. `booking_tags` ref URL matching google.com/localservices → `'GLS'`
6. `callrail_leads.source` mapped to taxonomy channel, including:
   - `source ILIKE '%thumbtack%'` → `'Thumbtack'`
   - `source ILIKE '%google ads%' OR ILIKE '%adwords%' OR ILIKE '%paid search%'` → `'Google Ads'`
   - `source ILIKE '%local services%' OR ILIKE '%lsa%'` → `'GLS'`
   - `source ILIKE '%google my business%' OR ILIKE '%maps%'` → `'GMB'`
   - `source ILIKE '%organic%' OR ILIKE '%seo%'` → `'Organic'`
   - `source ILIKE '%call forwarding%'` → `'Direct'`
   - `source ILIKE '%direct%'` → `'Direct'`
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

#### Scenario: CallRail call with Call forwarding source resolves to Direct
- **WHEN** `estimates.lead_source IS NULL` AND no `booking_tags` signals AND the customer has a `callrail_leads` row with `source = 'Call forwarding'`
- **THEN** `channel = 'Direct'`

#### Scenario: CallRail call with literal Direct source still resolves to Direct
- **WHEN** `estimates.lead_source IS NULL` AND no `booking_tags` signals AND the customer has a `callrail_leads` row with `source = 'Direct'`
- **THEN** `channel = 'Direct'`

#### Scenario: Higher-precedence CallRail source wins over Call forwarding
- **WHEN** `estimates.lead_source IS NULL` AND the customer has CallRail rows with both `source = 'Google Local Services'` and `source = 'Call forwarding'`
- **THEN** `channel = 'GLS'` (the GLS branch precedes the Call forwarding → Direct branch)

#### Scenario: No signals present
- **WHEN** `estimates.lead_source IS NULL` AND no relevant `booking_tags` keys AND no `callrail_leads` row
- **THEN** `channel = 'Other'`
