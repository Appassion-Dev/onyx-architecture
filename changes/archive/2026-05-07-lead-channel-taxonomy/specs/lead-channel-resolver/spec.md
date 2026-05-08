## ADDED Requirements

### Requirement: Booking-form submission writes resolved channel to estimates.lead_source
The `hcp-booking` edge function SHALL resolve the taxonomy channel string from the submitted URL tags (via `buildLeadSource()`) and persist it to `estimates.lead_source` after the HCP estimate is created.

#### Scenario: New form booking with gclid
- **WHEN** a booking form submission includes a `gclid` URL tag
- **THEN** `estimates.lead_source` is set to `'Google Ads'` for the newly created estimate row

#### Scenario: New form booking with utm_source=thumbtack
- **WHEN** a booking form submission includes `utm_source=thumbtack`
- **THEN** `estimates.lead_source` is set to `'Thumbtack'`

#### Scenario: New form booking with no tracking params
- **WHEN** a booking form submission has no gclid, fbclid, utm, or referrer signals
- **THEN** `estimates.lead_source` is set to `'Online Booking'` (the fallback value from `buildLeadSource()`)

### Requirement: Repeat-customer booking within 90 days preserves original channel
The `hcp-booking` edge function SHALL read the existing `customers.lead_source` and `customers.created_at` before writing. If the customer row exists AND `created_at` is within 90 days of the current booking timestamp AND the existing `lead_source` is non-null, the original `lead_source` value SHALL be used as the channel written to `estimates.lead_source`.

#### Scenario: Repeat customer within 90 days
- **WHEN** a booking form submission matches an existing customer created 45 days ago with `lead_source = 'Google Ads'`
- **THEN** the new estimate's `lead_source` is set to `'Google Ads'` (preserved from original)
- **AND** `customers.lead_source` is not changed

#### Scenario: Repeat customer outside 90 days
- **WHEN** a booking form submission matches an existing customer created 120 days ago
- **THEN** the new estimate's `lead_source` is set to the channel resolved from the current booking's URL tags
- **AND** `customers.lead_source` is updated to the new resolved channel

#### Scenario: Repeat customer with null original lead_source
- **WHEN** a booking form submission matches an existing customer whose `lead_source` is null (created before this fix)
- **THEN** the new estimate's `lead_source` is set to the channel resolved from the current booking's URL tags
- **AND** `customers.lead_source` is updated to the new resolved channel

#### Scenario: New customer
- **WHEN** the booking form submission does not match any existing customer
- **THEN** `customers.lead_source` is set to the resolved channel
- **AND** the new estimate's `lead_source` is set to the same resolved channel
