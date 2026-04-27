## Why

The current Conversions area mixes two different operator jobs: monitoring upload health and working individual upload rows. The system already collects far more feedback than the UI exposes, so operators need a dedicated analytics surface that renders all available conversion upload statistics and diagnostics, while preserving the upload table as a separate operational workbench.

## What Changes

- Add a new `Analytics` page under the Conversions section that renders all currently available conversion upload feedback in dedicated dashboard panels.
- Move the current conversions pipeline and upload workbench to a new `Uploads` page under the Conversions section, preserving scan, upload, filter, and row-detail workflows.
- Convert the `Conversions` sidebar item into a collapsible navigation group with `Analytics` and `Uploads` child destinations.
- Surface the full set of currently collected feedback where available, including upload health, attribution, action activity, configuration drift, analytics run freshness, slice status, row-level upload status and errors, and GCLID verification diagnostics.
- Align route structure, page titles, and navigation highlighting with the new Conversions information architecture.

## Capabilities

### New Capabilities
- `conversion-analytics-page`: renders the full conversion upload analytics and feedback surface in a dedicated dashboard page.
- `conversions-submenu-navigation`: provides a collapsible Conversions navigation group with child destinations for Analytics and Uploads.

### Modified Capabilities
- `conversion-dashboard`: changes the conversion upload dashboard from a single top-level Conversions destination to the Uploads destination under the Conversions submenu.
- `conversion-pipeline-ui`: moves the current conversions pipeline table and its operational controls to the Uploads page without removing the existing workflow.

## Impact

- `horizon-dashboard/src/App.tsx` route structure for Conversions destinations and page selection.
- `horizon-dashboard/src/components/common/Sidebar.tsx` navigation hierarchy, expansion behavior, and active-state logic.
- `horizon-dashboard/src/components/pages/ConversionsPage.tsx` page role, title, and route ownership for the uploads workbench.
- New dashboard UI under `horizon-dashboard/src/components/pages/` for conversion analytics and feedback panels.
- Existing Supabase-backed read paths for attribution, upload health, config drift, row-level upload evidence, and GCLID verification diagnostics.