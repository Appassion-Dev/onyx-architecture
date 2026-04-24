## Why

The Conversions page groups estimates by raw calendar month, while every other sales report in the dashboard (sales goals, tech performance, sales overview) uses the fiscal calendar system — where a week belongs to the month containing its Thursday. This means "March" in the Conversions page and "March" in the sales goal chart can cover different date ranges, making cross-report comparison unreliable. Additionally, estimates from W14/2026 (Mar 30–Apr 5, fiscal April) currently appear split across two month headers — 32 estimates on Mar 30–31 land under "March" while Apr 1–5 land under "April," even though they're in the same ISO week.

## What Changes

- **Month grouping in `getRowDateKeys`** — replace raw `d.getMonth()` calendar month key with the fiscal month derived from `mapWeekToFiscalPeriod(weekYear, weekNumber)`. Month labels change from "March 2026" to "April 2026" for boundary-week estimates.
- **Month key format** — the sort key for month groups must encode fiscal year and fiscal month (not calendar year and month), so that W53 estimates sort into December and boundary weeks sort correctly.
- **Week labels remain unchanged** — ISO week bounds (Mon–Sun) are already correct; only the containing month group changes.
- **`getCalendarMonthName` call updated** — the month label must use the fiscal month's calendar name (e.g., fiscal month 4 → "April"), sourced from the `FiscalPeriod` result rather than the raw date.

## Capabilities

### New Capabilities
- `conversions-fiscal-grouping`: Month-level grouping in the Conversions page uses the fiscal calendar (Thursday-belongs rule), producing month headers that are consistent with all other dashboard reports.

### Modified Capabilities

(none — no existing spec files exist; this is new territory)

## Impact

- **`ConversionsPage.tsx`** — `getRowDateKeys` function updated; no other component files change
- **`fiscalCalendar.ts`** — `mapWeekToFiscalPeriod` already exists and is used; no changes needed
- **`weekUtils.ts`** — `getCalendarMonthName` already supports fiscal use; no changes needed
- **`vw_conversion_candidates`** — no database changes; the view already exposes `estimate_created_at`
- **No breaking changes** — this is a display-layer fix; no API contracts, query shapes, or pipeline behavior changes
