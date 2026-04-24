## ADDED Requirements

### Requirement: Form submission tags displayed in Booking Lead detail
The system SHALL display a table of booking_tags (key-value pairs) inside the Booking Lead expanded section when `has_form` is true. Tags SHALL be fetched lazily when the row is expanded. The keys `gclid`, `hsa_kw`, `hsa_mt`, `hsa_cam`, `hsa_src`, `hsa_grp`, `hsa_ad`, `hsa_tgt` SHALL be mapped to friendly labels. The keys `hsa_ver` and `ref` SHALL be excluded.

#### Scenario: Estimate with form submission tags
- **WHEN** a pipeline row with `has_form = true` is expanded
- **THEN** the Booking Lead section displays a "Form Submission" key-value table with the estimate's booking_tags

#### Scenario: Estimate without form submission
- **WHEN** a pipeline row with `has_form = false` is expanded
- **THEN** the Booking Lead section does NOT display the Form Submission table

### Requirement: Calls section nested inside Booking Lead
The system SHALL display the calls history table inside the Booking Lead section (not at the bottom of the expanded area). When `call_count = 0`, the system SHALL display "No calls recorded" instead of hiding the section.

#### Scenario: Booking lead with calls
- **WHEN** a pipeline row with `call_count > 0` is expanded
- **THEN** the Calls table appears inside the Booking Lead section

#### Scenario: Booking lead with no calls
- **WHEN** a pipeline row with `call_count = 0` is expanded
- **THEN** the text "No calls recorded" appears inside the Booking Lead section
