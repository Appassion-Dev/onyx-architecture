## 1. Update ConversionsPage Month Grouping

- [x] 1.1 Add `mapWeekToFiscalPeriod` to the import from `@/lib/utils/fiscalCalendar` in `ConversionsPage.tsx`
- [x] 1.2 Rewrite `getRowDateKeys` to derive `monthKey` and `monthLabel` from `mapWeekToFiscalPeriod(info.weekYear, info.weekNumber)` instead of from `d.getMonth()`
- [x] 1.3 Use `fiscalPeriod.fiscalYear` (not `d.getFullYear()`) for the year portion of both `monthKey` and `monthLabel`
- [x] 1.4 Update `monthKey` format to `"<fiscalYear>-FM<fiscalMonth padded 2>"` (e.g., `"2026-FM04"`)
- [x] 1.5 Update the null/invalid date fallback to return `monthKey: '0000-FM00'` for consistency with the new format
- [x] 1.6 Add a null guard for the `mapWeekToFiscalPeriod` return value, falling back to `getCalendarMonthName(d.getMonth() + 1)` and `d.getFullYear()` if null (defensive only — should not occur in practice)

## 2. Verify Correctness

- [x] 2.1 Manually confirm that estimates from Mar 30–31, 2026 now appear under "April 2026" (not "March 2026") in the local dev dashboard
- [x] 2.2 Confirm that estimates from Apr 1–5, 2026 also appear under "April 2026" — same month group as Mar 30–31 (no week split)
- [x] 2.3 Confirm that mid-month estimates (e.g., Apr 15) still show under "April 2026" unchanged
- [x] 2.4 Confirm that month sections still sort newest-first (April 2026 before March 2026)
