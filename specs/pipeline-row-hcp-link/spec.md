## Requirements

### Requirement: Estimate label deep-links to HousecallPro
The estimate label in `PipelineRowItem` (rendered as `#{estimate_number}`) SHALL be wrapped in an anchor element that opens `https://pro.housecallpro.com/app/estimates/{estimate_id}` in a new browser tab. The link SHALL include `target="_blank"` and `rel="noopener noreferrer"`. Clicking the link SHALL NOT also toggle the row's expanded/collapsed state.

#### Scenario: Click opens HCP in new tab
- **WHEN** a user clicks the `#{estimate_number}` label in a PipelineRowItem with `estimate_id = "abc123"`
- **THEN** a new browser tab SHALL open at `https://pro.housecallpro.com/app/estimates/abc123`
- **AND** the source row's expanded/collapsed state SHALL remain unchanged

#### Scenario: Click on the rest of the row still toggles
- **WHEN** a user clicks anywhere on the PipelineRowItem button area OTHER than the estimate label link
- **THEN** the row SHALL toggle its expanded/collapsed state as it does today

#### Scenario: Estimate fallback when number is missing
- **WHEN** an estimate has `estimate_number = NULL`
- **THEN** the row SHALL render the existing fallback label (first 8 characters of `estimate_id`) wrapped in the same HCP link to `https://pro.housecallpro.com/app/estimates/{estimate_id}`

### Requirement: Expanded detail panel includes a customer-info block
When a PipelineRowItem is expanded, the detail panel SHALL include a new `CustomerInfoBlock` rendered at the top of the panel (above the Booking Lead section). The block SHALL display the customer name, email (rendered as a `mailto:` link), mobile phone (rendered as a `tel:` link), and service address (single line: street, city, state, zip) from the customer record exposed by `vw_conversion_candidates`. Fields with NULL or empty values SHALL be omitted (NOT rendered as `—`).

#### Scenario: All customer fields present
- **WHEN** a row is expanded and the customer has name, email, mobile, and a complete address
- **THEN** the detail panel SHALL display the CustomerInfoBlock with name, an email mailto link, a phone tel link, and a single-line address

#### Scenario: Partial customer data
- **WHEN** a row is expanded and the customer has name and mobile but no email and no address
- **THEN** the CustomerInfoBlock SHALL display name and the phone tel link only

#### Scenario: CustomerInfoBlock position
- **WHEN** a row is expanded
- **THEN** the CustomerInfoBlock SHALL be rendered above the Booking Lead StageDetail section in the expanded panel

#### Scenario: Email link mechanics
- **WHEN** the user clicks the email value
- **THEN** the browser SHALL open the default mail client with the customer's email pre-filled (standard `mailto:` behavior)

#### Scenario: Phone link mechanics
- **WHEN** the user clicks the phone value
- **THEN** the browser SHALL initiate a tel: action (standard `tel:` behavior)
