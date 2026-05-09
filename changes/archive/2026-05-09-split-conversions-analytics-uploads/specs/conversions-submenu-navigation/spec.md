## ADDED Requirements

### Requirement: Conversions sidebar group
The dashboard SHALL render Conversions as a collapsible sidebar group instead of a single flat navigation item.

#### Scenario: Expanded sidebar shows child destinations
- **WHEN** the sidebar is expanded and the user opens the Conversions group
- **THEN** the sidebar shows child destinations for Analytics and Uploads

#### Scenario: Collapsed sidebar preserves conversions navigation
- **WHEN** the sidebar is collapsed and the user activates the Conversions control
- **THEN** the system still provides access to both Analytics and Uploads destinations without requiring the sidebar to stay fully expanded

### Requirement: Conversions child destinations own active state
The Conversions sidebar group SHALL own the active state for the Analytics and Uploads child destinations and for other routes nested under the Conversions section.

#### Scenario: Analytics child is active
- **WHEN** the current route is the Conversions Analytics destination
- **THEN** the Conversions group is marked active and the Analytics child is highlighted

#### Scenario: Uploads child is active
- **WHEN** the current route is the Conversions Uploads destination
- **THEN** the Conversions group is marked active and the Uploads child is highlighted

#### Scenario: Secondary conversions route keeps parent active
- **WHEN** the current route is another nested Conversions destination such as configuration
- **THEN** the Conversions group remains active even if that route is not a primary child item in the sidebar

### Requirement: Analytics is the default conversions destination
The system SHALL use the Analytics child page as the default destination for top-level Conversions navigation.

#### Scenario: User selects parent conversions destination
- **WHEN** the user navigates to Conversions without selecting a specific child destination
- **THEN** the system lands on the Analytics child page
