## ADDED Requirements

### Requirement: Per-row house-call lead source tag
Each estimate row in the conversions channel roll-up SHALL render, after the
estimate/customer name, a light-colored tag showing the estimate's
`lead_source` value. When `lead_source` is NULL or empty, the tag SHALL NOT be
rendered.

#### Scenario: Lead source present
- **WHEN** a row has `lead_source = 'Google Ads'`
- **THEN** a light-colored tag reading "Google Ads" SHALL render after the name

#### Scenario: Lead source absent
- **WHEN** a row has `lead_source` NULL or empty
- **THEN** no lead-source tag SHALL render

### Requirement: Per-row call-vs-booking tag
Each estimate row SHALL render a light-colored tag indicating whether the lead
arrived as a call or a booking, after the estimate/customer name. The value
SHALL be resolved as:
- `first_touch_medium = 'call'` → **Call**
- `first_touch_medium = 'form'` → **Booking**
- otherwise, fall back to `has_form = true` → **Booking**, then
  `call_count > 0` → **Call**
- if none resolve, the tag SHALL NOT be rendered.

#### Scenario: First-touch is a call
- **WHEN** a row has `first_touch_medium = 'call'`
- **THEN** a light-colored "Call" tag SHALL render

#### Scenario: First-touch is a form
- **WHEN** a row has `first_touch_medium = 'form'`
- **THEN** a light-colored "Booking" tag SHALL render

#### Scenario: Fallback to has_form
- **WHEN** `first_touch_medium` is NULL and `has_form = true`
- **THEN** a light-colored "Booking" tag SHALL render

#### Scenario: Fallback to call_count
- **WHEN** `first_touch_medium` is NULL, `has_form = false`, and `call_count > 0`
- **THEN** a light-colored "Call" tag SHALL render

#### Scenario: No signal resolves
- **WHEN** `first_touch_medium` is NULL, `has_form = false`, and `call_count = 0`
- **THEN** no call-vs-booking tag SHALL render

### Requirement: Tags are visually light and inline
Both tags SHALL use a light-colored pill style consistent with the row's other
inline tags (rounded, bordered, small uppercase-neutral text) and SHALL sit on
the same line as the estimate/customer name, wrapping when space is constrained.

#### Scenario: Both tags render together
- **WHEN** a row has both a `lead_source` and a resolvable call/booking signal
- **THEN** both light-colored tags SHALL render inline after the name in
  lead-source-then-call/booking order
