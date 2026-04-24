## Why

The Conversions page shows pipeline status per estimate but lacks the filtering, attribution context, and estimate detail that operators need to diagnose funnel gaps and attribution coverage. There is no way to slice by step, source, or assignee, and key signals — GCLID count, campaign name, assigned salesperson, and estimate links — are either absent or buried.

## What Changes

- Add a filter bar at the top of the Conversions page with five independent dropdowns: conversion step (pre-discovery / has-booking / has-qualified / has-converted / closed), source (dynamic, from callrail_sources), first-touch medium (form / call), campaign (dynamic, from callrail_campaigns), and assigned employee (from `vw_employees_with_roles`)
- Add a `GCLID ×N` tag in each estimate row showing the count of unique GCLIDs across both booking_tags and callrail_leads; hovering shows the full list in a tooltip (mirrors the "Ad" tag on the Calls page)
- Add assigned employee (name + colored dot via `EmployeeBadge`) to the Qualified Lead expanded detail section
- Add an HCP deep-link (`↗`) to each row in the Estimate Options table in the Qualified Lead detail
- Enrich `vw_conversion_candidates` with: `callrail_campaigns`, `all_gclids` (combined deduplicated array from both sources), `assigned_employee_id`, `assigned_employee_name`, and `first_touch_medium`

## Capabilities

### New Capabilities
- `conversions-filter-bar`: Multi-dropdown filter bar that narrows the visible estimates client-side by step, source, medium, campaign, and assigned employee
- `conversions-gclid-tag`: Per-estimate GCLID count badge with tooltip listing all unique GCLIDs combined from booking_tags and callrail_leads
- `conversions-qualified-enrichment`: Assigned employee display and HCP estimate option links in the Qualified Lead expanded section

### Modified Capabilities
<!-- No existing specs to modify — all new. -->

## Impact

- **Database**: `vw_conversion_candidates` view rebuilt via new migration to expose `callrail_campaigns`, `all_gclids`, `assigned_employee_id`, `assigned_employee_name`, `first_touch_medium`
- **Frontend**: `ConversionsPage.tsx` — `PipelineRow` interface extended, filter state added, filter bar rendered above the month hierarchy, GCLID tag added to row badges, `EstimateOptionsTable` gains HCP links, `StageDetail` for Qualified Lead gains assignee row
- **Dependencies**: `useEmployees()` hook (already app-wide cached via `vw_employees_with_roles`) used for the assignee filter dropdown and color lookup; `EmployeeBadge` component reused
- **No breaking changes**: view columns are purely additive; existing row queries still work
