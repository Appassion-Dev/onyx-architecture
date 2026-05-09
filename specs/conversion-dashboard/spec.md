## MODIFIED Requirements

### Requirement: Conversions dashboard page
The dashboard SHALL provide the conversion upload dashboard as the Uploads destination within the Conversions navigation group rather than as a single flat main-navigation page.

#### Scenario: User navigates to uploads page
- **WHEN** an authenticated user selects Uploads under the Conversions navigation group
- **THEN** they see the conversion upload dashboard for Google Ads upload records

#### Scenario: Unauthenticated access is blocked
- **WHEN** an unauthenticated user attempts to access the Uploads destination
- **THEN** they are redirected to the login page
