# May 18–24, 2026 — Time vs. Developments

Correlates the week's logged hours ([Clockify detailed report](Clockify_Time_Report_Detailed_18_05_2026-24_05_2026.pdf)) with the OpenSpec changes from the [May 18–24 changes report](may-18-24-2026-changes-report.md). **Total: 30:25:21** (matches the PDF).

| Date | Logged task | Duration | Corresponding development |
|------|-------------|---------:|----------------------------|
| 18/05 | conversion upload error handling, frontend improvements, tests | 00:55:07 | **`gads-conversion-error-dispositions`** — foundational implementation (migrations `20260518*`), bundled with rollup FE + tests |
| 18/05 | conversion upload error handling, frontend improvements, tests | 02:56:15 | **`gads-conversion-error-dispositions`** (same) |
| 18/05 | conversion upload error handling, frontend improvements, tests | 03:14:51 | **`gads-conversion-error-dispositions`** (same) |
| 18/05 | frontend improvements, backend tests | 01:03:37 | **`conversions-rollup-redesign`** (FE) + **`gads-upload-step-tests`** (backend tests) |
| 19/05 | frontend improvements | 07:32:33 | **`conversions-rollup-redesign`** — the rollup-rail rebuild (Stage/Method/Push/Acceptance) |
| 20/05 | tests for updated upload function | 00:59:37 | **`gads-upload-step-tests`** |
| 20/05 | answering questions, researching bugs | 04:29:36 | General investigation / client Q&A — no specific change |
| 20/05 | investigate upload issues | 00:18:32 | May 21 upload-visibility cluster (`capture-raw-batch-payloads`, `view-batch-raw-payloads`, `gads-discovery-lifecycle-default`) |
| 21/05 | investigate upload issues | 02:38:03 | Same upload-visibility cluster |
| 21/05 | answering questions, researching bugs | 01:28:36 | General investigation / client Q&A — no specific change |
| 21/05 | implementing lead channel fix | 00:15:22 | **`prepass-callrail-direct-customer-id`** (CallRail GCLID join fix) |
| 22/05 | implementing lead channel fix | 04:33:12 | **`prepass-callrail-direct-customer-id`** (and early work toward `classify-callrail-call-forwarding-as-direct`) |
| | **Total** | **30:25:21** | |

## Grouped by development

| Development | Duration | Status |
|-------------|---------:|--------|
| `conversions-rollup-redesign` | 08:36:10 | complete |
| `gads-conversion-error-dispositions` | 07:06:13 | complete |
| `prepass-callrail-direct-customer-id` (lead channel fix) | 04:48:34 | complete |
| Upload-issue investigation → May 21 visibility cluster | 02:56:35 | complete |
| `gads-upload-step-tests` | 00:59:37 | complete |
| General investigation / client Q&A (no OpenSpec change) | 05:58:12 | — |
| **Total** | **30:25:21** | |

## Notes

- The biggest single block (7.5h on 19/05) was **`conversions-rollup-redesign`** — the Conversions-page rollup-rail rebuild — logged simply as "frontend improvements."
- **18/05 was the foundational `gads-conversion-error-dispositions` implementation day** (~7h across three entries, migrations `20260518*`), with frontend and tests bundled into the same log lines.
- ~6h of **"answering questions, researching bugs"** maps to no OpenSpec change — it's the largest non-feature bucket of the week (client support / investigation).
- **"investigate upload issues"** (~3h, 20–21/05) fed the May 21 visibility cluster — raw-payload capture, the Workbench payload viewer, and the `lifecycle = NULL` backfill — which surfaced and fixed silent upload gaps.
- The May 25–26 closeout changes (`classify-callrail-call-forwarding-as-direct`, `gads-upload-fix-and-refactor`, `callrail-pull-cron`) fall outside this Clockify window; any time spent on them is logged in a later week.
