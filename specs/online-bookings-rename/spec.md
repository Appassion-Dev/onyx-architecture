## Requirements

### Requirement: Rename BookingManagerPage file to OnlineBookingsPage
The file `BookingManagerPage.tsx` SHALL be renamed to `OnlineBookingsPage.tsx` and the exported component SHALL be renamed to `OnlineBookingsPage`.

#### Scenario: File exists at new path
- **WHEN** the codebase is inspected
- **THEN** `src/components/pages/OnlineBookingsPage.tsx` SHALL exist and `BookingManagerPage.tsx` SHALL NOT exist

### Requirement: Route path updated
The route for the online bookings page SHALL be `/online-bookings` instead of `/bookings`.

#### Scenario: Navigating to /online-bookings
- **WHEN** a user navigates to `/online-bookings`
- **THEN** the OnlineBookingsPage component SHALL render

#### Scenario: Old /bookings path no longer matches
- **WHEN** a user navigates to `/bookings`
- **THEN** the catch-all route SHALL redirect to `/`

### Requirement: Sidebar nav item updated
The sidebar navigation SHALL show "Online Bookings" as the label with path `/online-bookings` instead of "Bookings" with path `/bookings`.

#### Scenario: Sidebar shows Online Bookings
- **WHEN** the sidebar renders
- **THEN** the nav item SHALL display "Online Bookings" with the CalendarCheck icon and link to `/online-bookings`

### Requirement: Import updated in App.tsx
The App.tsx route file SHALL import `OnlineBookingsPage` from the new file path.

#### Scenario: App.tsx import correct
- **WHEN** App.tsx is inspected
- **THEN** it SHALL contain `import { OnlineBookingsPage } from './components/pages/OnlineBookingsPage'`