## Context

The Conversions page (`ConversionsPage.tsx`) groups estimates into a month → week → estimate hierarchy. The current `getRowDateKeys` function derives both the week key (via `getWeekInfo`) and the month key independently from the same `estimate_created_at` date. The week key is already an ISO week key (e.g., `"2026-W14"`), which is correct. But the month key is derived from `d.getMonth()` — the raw calendar month of the date — which is not the same as the fiscal month.

The fiscal calendar system (in `fiscalCalendar.ts`) defines that a week belongs to the calendar month containing its Thursday. The rest of the dashboard (sales goals, tech performance, sales overview) consistently uses this system. The Conversions page does not.

This creates cross-report inconsistency: "April 2026" in the Conversions page covers Apr 1 onward by calendar, but "April" everywhere else in the dashboard includes W14 (Mar 30–Apr 5). Concretely, 32 estimates from Mar 30–31, 2026 appear under "March" in Conversions but belong to fiscal April.

The fix is a single-function change to `getRowDateKeys` in `ConversionsPage.tsx`. No view, schema, or pipeline changes are needed.

## Goals / Non-Goals

**Goals:**
- Month groups in the Conversions page align with the fiscal calendar used by all other dashboard reports
- Estimates in the same ISO week always appear in the same month group (no week split across two months)
- Month labels and sort keys encode fiscal identity (fiscal year + fiscal month), not raw calendar date
- No visual or functional changes beyond the month grouping labels and membership

**Non-Goals:**
- Changes to the underlying view (`vw_conversion_candidates`) or database
- Changes to week labels, week keys, or weekly rollup logic — those are already correct
- Changes to any other page or component
- Changing how fiscal months are named (they keep using calendar month names like "April 2026", not "M4 2026" — the fiscal system uses human-readable names already via `getCalendarMonthName`)
- Pagination, filtering, or any pipeline behavior changes

## Decisions

### Decision 1: Derive month identity from the ISO week, not from the date

**Chosen**: In `getRowDateKeys`, use `mapWeekToFiscalPeriod(info.weekYear, info.weekNumber)` to get the fiscal period, then read `fiscalPeriod.fiscalMonth` and `fiscalPeriod.fiscalYear` for the month key and label.

**Rationale**: This is exactly the same rule used by all other fiscal-system components. The ISO week is already computed (`getWeekInfo` is already called). Using `mapWeekToFiscalPeriod` adds one pure-function call with no I/O — it's cheap, already imported-adjacent, and unambiguous.

**Alternative considered**: Recompute Thursday of the week inline (`addDays(weekStart, 3)`) and take its month. This produces the same result but duplicates logic that `mapWeekToFiscalPeriod` already encapsulates cleanly.

**Alternative considered**: Move grouping to the backend by adding a fiscal month column to `vw_conversion_candidates`. Rejected — the view is pure data; the fiscal calendar is a UI concern. Other fiscal-system charts also do this computation in the frontend.

### Decision 2: Month sort key encodes fiscal year + fiscal month (zero-padded)

**Chosen**: `monthKey = "<fiscalYear>-FM<fiscalMonth padded to 2>"`, e.g., `"2026-FM04"`.

**Rationale**: The current key is `"2026-04"` (YYYY-MM). Using a distinct prefix `FM` avoids any chance of collision with other key formats and makes the fiscal interpretation explicit in debug views. Sorting is still lexicographic and correct.

**Alternative considered**: Keep the same `"YYYY-MM"` format but use fiscal year and fiscal month as the numbers. This works, but is visually indistinguishable from the calendar format and could mislead future readers into thinking it's calendar-based.

### Decision 3: Month label uses `getCalendarMonthName(fiscalMonth)` + fiscal year from the period

**Chosen**: `monthLabel = getCalendarMonthName(fiscalPeriod.fiscalMonth) + " " + fiscalPeriod.fiscalYear`

**Rationale**: The fiscal month number maps 1:1 to calendar month names (fiscal month 4 is always named "April"). This keeps labels human-readable ("April 2026") without exposing the "M4" fiscal identifier. `getCalendarMonthName` is already imported.

**Note on fiscal year vs. calendar year**: For a boundary estimate like Jan 4 (W1 of fiscal year 2026), the fiscal year is 2026 even if the calendar year is 2025. Using `fiscalPeriod.fiscalYear` (not `d.getFullYear()`) is therefore critical at year boundaries.

### Decision 4: Fallback for null/invalid dates is unchanged

**Chosen**: If `estimate_created_at` is null or unparseable, return `{ monthKey: '0000-FM00', weekKey: '0000-W00', monthLabel: 'Unknown', weekLabel: 'Unknown' }`.

**Rationale**: No behavior change for the edge case. The `"FM"` prefix keeps the fallback key consistent with the new format.

## Risks / Trade-offs

**[Risk] mapWeekToFiscalPeriod returns null for out-of-range week numbers** → The function returns null only for week numbers <1 or >53. ISO weeks from `getWeekInfo` are always valid, so this path is unreachable in practice. A null guard should still be added, falling back to calendar month label in the degenerate case.

**[Risk] Users with bookmarks or habits expecting "March = Mar 1–31" will see 32 estimates move from March to April** → This is the intended behavior. It aligns with the rest of the dashboard. No user-facing migration is needed beyond the label change.

**[Risk] W53 estimates in a 53-week year** → `mapWeekToFiscalPeriod` handles 53-week years correctly (W53's Thursday falls in December). No special case needed.

## Migration Plan

1. Update `getRowDateKeys` in `ConversionsPage.tsx` — single function, ~10 lines
2. Add `mapWeekToFiscalPeriod` to the import from `fiscalCalendar.ts` (it's not currently imported in `ConversionsPage.tsx`)
3. Update the fallback `monthKey` string to use the `FM` prefix for consistency
4. No database migration, no view change, no edge function change
5. Rollback: revert the single function — the view and pipeline are completely unaffected

## Open Questions

- None — the fiscal system is well-established, `mapWeekToFiscalPeriod` is tested, and the scope is a single function.
