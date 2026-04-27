## 1. Routing And Navigation

- [x] 1.1 Update the dashboard route tree so `/conversions` lands on `/conversions/analytics` and add a dedicated `/conversions/uploads` destination.
- [x] 1.2 Refactor the Sidebar to render Conversions as a collapsible parent item with Analytics and Uploads child destinations.
- [x] 1.3 Update Conversions section active-state logic so the parent remains active across analytics, uploads, and secondary nested routes such as configuration.

## 2. Uploads Workbench Move

- [x] 2.1 Move the current ConversionsPage workbench to the Uploads destination and update page title, copy, and route ownership without removing existing actions.
- [x] 2.2 Preserve the current scan, upload, filter, table, and row-detail workflows on the Uploads page after the route split.
- [x] 2.3 Fix the GCLID verification response handling so the Uploads page can render verification feedback correctly after the move.

## 3. Analytics Data Integration

- [x] 3.1 Create the new Conversion Analytics page component and wire it to existing Supabase data sources for analytics runs, client health, action health, attribution summary, drift, and local upload outcomes.
- [x] 3.2 Add summary panels for system feedback, upload health, attribution, action activity, drift, and upload outcome counts.
- [x] 3.3 Add the first-sync and empty-data states so the Analytics page still renders as a valid destination before analytics snapshots exist.

## 4. Diagnostic Detail Surfaces

- [x] 4.1 Add drill-down views for analytics run failures, including slice status, row counts, timestamps, and stored error text.
- [x] 4.2 Add drill-down views for stored client and action feedback payloads, including alerts and daily summaries.
- [x] 4.3 Add navigation links between Analytics and Uploads so operators can move from summary feedback to row-level investigation.

## 5. Verification

- [x] 5.1 Verify the Conversions sidebar behaves correctly in both expanded and collapsed modes and exposes Analytics and Uploads as child destinations.
- [x] 5.2 Verify `/conversions` lands on Analytics and `/conversions/uploads` renders the preserved uploads workbench.
- [x] 5.3 Verify the Analytics page renders all currently available feedback families without duplicating the full uploads table.
- [x] 5.4 Verify the Uploads page still supports scan, upload, filters, row details, and GCLID verification after the move.