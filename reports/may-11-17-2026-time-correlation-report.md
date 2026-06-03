# May 11–17, 2026 — Time vs. Developments

Correlates the week's logged hours ([Clockify detailed report](../ref/Clockify_Time_Report_Detailed_11_05_2026-17_05_2026.pdf)) with the OpenSpec changes from the [May 11–17 changes report](may-11-17-2026-changes-report.md). **Total: 18:04:08** (matches the PDF).

| Date | Logged task | Duration | Corresponding development |
|------|-------------|---------:|----------------------------|
| 11/05 | deploy specification repo, dev reporting system, investigate click-lookback-window issue | 03:33:52 | Tooling/infra setup (OpenSpec repo + this reporting system) plus the investigation behind **`tighten-gclid-attribution-window`** (completed May 13) |
| 13/05 | generating architecture refactoring proposal | 06:30:57 | **`conversion-attribution-overhaul`** — the large 7-change proposal + `design.md` opened May 13 *(inferred from "proposal")* |
| 13/05 | csv export | 00:56:42 | Client request: download all conversion data from the frontend. Complete; no OpenSpec change folder |
| 14/05 | refactoring conversion page | 03:33:42 | **`refactor-conversions-page`** (completed May 14) — the 2,040-line page split into the `conversions/` feature folder |
| 15/05 | conversion upload error handling | 02:09:39 | **`gads-conversion-error-dispositions`** (opened May 15) |
| 15/05 | conversion upload error handling | 01:19:16 | **`gads-conversion-error-dispositions`** (opened May 15) |
| | **Total** | **18:04:08** | |

## Grouped by development

| Development | Duration | Status |
|-------------|---------:|--------|
| `conversion-attribution-overhaul` (proposal) | 06:30:57 | in progress |
| `refactor-conversions-page` | 03:33:42 | complete |
| `tighten-gclid-attribution-window` + infra/reporting setup | 03:33:52 | complete |
| `gads-conversion-error-dispositions` | 03:28:55 | complete |
| csv export (client data-download request) | 00:56:42 | complete |
| **Total** | **18:04:08** | |

## Notes

- The single biggest block (6.5h) went into **specifying**, not coding — generating the `conversion-attribution-overhaul` proposal that the following weeks build on. Implementation hours for that change fall outside this window.
- **`tighten-gclid-attribution-window`** was completed May 13, but the only logged time this week is the May 11 *investigation* of the click-lookback issue (bundled with infra setup); its migration work isn't broken out separately.
- **csv export** (0:56:42) corresponds to the **client's request to download all conversion data from the frontend**. It's complete, but has no OpenSpec change folder, so it doesn't appear in the changes report.
