## ADDED Requirements

### Requirement: Conversion analytics landing page
The dashboard SHALL provide a dedicated Conversion Analytics page under the Conversions section and SHALL use it as the default landing destination for the Conversions route.

#### Scenario: User opens analytics from conversions navigation
- **WHEN** an authenticated user selects the Analytics destination inside the Conversions navigation group
- **THEN** the system routes to the analytics page and displays conversion upload analytics instead of the uploads workbench

#### Scenario: Root conversions route lands on analytics
- **WHEN** a user navigates to the root Conversions route without a child path
- **THEN** the system resolves that navigation to the Analytics child page

### Requirement: Analytics page renders all available feedback families
The Conversion Analytics page SHALL render dedicated panels for each currently collected conversion upload feedback family, including analytics run status, client upload health, action upload health, attribution summary, action alive state, configuration drift, and local upload outcome summaries.

#### Scenario: Feedback families render when analytics data exists
- **WHEN** cached analytics and upload data exist in Supabase
- **THEN** the page shows separate feedback panels for system runs, client health, action health, attribution, drift, and upload outcomes

#### Scenario: Pending-first-sync analytics page
- **WHEN** no analytics snapshots have been collected yet
- **THEN** the page shows a first-sync waiting state without redirecting the user away from the analytics destination

### Requirement: Analytics page exposes stored diagnostic detail
The Conversion Analytics page SHALL provide drill-down views for stored diagnostic detail, including slice-level run errors, raw alerts, raw daily summaries, and latest sync timestamps where those values exist.

#### Scenario: Operator inspects upload health detail
- **WHEN** an operator opens the detail view for a client or conversion action health panel
- **THEN** the system shows the latest synced timestamp together with the stored alerts and daily summary content for that panel

#### Scenario: Operator inspects failed analytics run
- **WHEN** the latest analytics run contains one or more failed slices
- **THEN** the system shows the failing slice names and the recorded error text without requiring external logs

### Requirement: Analytics page summarizes row-level upload outcomes
The Conversion Analytics page SHALL summarize local row-level upload outcomes without duplicating the full uploads table.

#### Scenario: Upload outcome summary is shown
- **WHEN** local upload rows exist
- **THEN** the page shows aggregate counts for uploaded, pending, skipped, and errored or retrying rows and provides a direct path to the Uploads page for row-level inspection
