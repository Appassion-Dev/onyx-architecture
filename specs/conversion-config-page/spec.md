## Requirements

### Requirement: Back navigation from config page
The Conversion Config page SHALL provide a back button that navigates the user to the Conversions page (`/conversions`).

#### Scenario: User clicks back button
- **WHEN** the user is on the Conversion Config page and clicks the back button
- **THEN** the browser navigates to `/conversions` without a full page reload

#### Scenario: Back button is always visible
- **WHEN** the Conversion Config page is mounted in any state (loading, loaded, error)
- **THEN** the back button is visible in the page header

### Requirement: Config fields populated on SPA navigation
The Conversion Config page SHALL display the full config values (`conversion_action_id`, `conversion_action_name`, `enabled`, `dry_run`) immediately or show a loading state when navigated to via the SPA router — it SHALL NOT display empty fields while silently using stale partial cache data from another page.

#### Scenario: Navigate from Conversions page to Config page
- **WHEN** the user navigates from `/conversions` to `/conversions/config` via the SPA router
- **THEN** either a loading spinner is shown while data is fetched, OR the fields display correct non-empty values from a prior full fetch
- **THEN** no fetch completes with `action_id`/`action_name` still null when the database has non-null values

#### Scenario: Direct page load
- **WHEN** the user loads `/conversions/config` directly (full page reload or fresh visit)
- **THEN** the page fetches config data and populates all fields correctly

#### Scenario: Query key isolation
- **WHEN** `ConversionsPage` has previously fetched and cached config data (partial shape)
- **THEN** `ConversionConfigPage` MUST NOT use that partial-shape cache for rendering the action ID and action name fields

### Requirement: Per-row save loading state
When saving a single conversion config row, only that row's Save button SHALL show a loading state. Other rows' Save buttons SHALL NOT enter a loading state.

#### Scenario: Save one row
- **WHEN** the user clicks Save on the "Booking Lead" card
- **THEN** only the "Booking Lead" card's Save button shows a loading spinner and is disabled
- **THEN** the "Qualified Lead" and "Converted Lead" Save buttons remain in their normal state

#### Scenario: Save completes
- **WHEN** a save mutation completes (success or error)
- **THEN** the previously loading Save button returns to its normal state
- **THEN** no other Save button is in a loading or disabled state as a result of that mutation