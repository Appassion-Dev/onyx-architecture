## Why

The Conversion Config page has three UX bugs that make it confusing and unreliable: navigating to it via the SPA shows empty fields until a page refresh, all three save buttons enter a loading state when only one is being saved, and there is no way to navigate back to the Conversions page. These issues erode trust in the config UI.

## What Changes

- Add a back button to `ConversionConfigPage` that navigates to `/conversions`
- Fix empty fields on SPA navigation by giving `ConversionConfigPage` its own React Query key (`['gads-conversion-config-full']`) so it doesn't read stale partial data cached by `ConversionsPage`
- Fix per-row save loading state by replacing the shared `mutation.isPending` flag with a `savingType` state variable that tracks which row is currently saving

## Capabilities

### New Capabilities

*(none — all changes are bug fixes to an existing page)*

### Modified Capabilities

- `conversion-config-page`: Fix back navigation, data fetch on SPA nav, and per-row save loading state

## Impact

- `horizon-dashboard/src/components/pages/ConversionConfigPage.tsx` — all three fixes live here
- `ConversionsPage` is read-only context; the query it runs against `gads_conversion_config` is unaffected
- No backend changes required
