# May 25–31, 2026 — Time vs. Developments

Correlates the week's logged hours  with the conversion-pipeline investigation captured in the [`conversion-known-issues`](../changes/conversion-known-issues/proposal.md) research register. **Total: 12:44:53** (matches the PDF).

This week was almost entirely **investigation and documentation** — no feature change folder was opened. The hours fed the four issues now documented in the known-issues register.

| Date | Logged task | Duration | Corresponding investigation |
|------|-------------|---------:|------------------------------|
| 25/05 | updating documentation | 01:59:31 | Known-issues register write-up (architecture spec + register scaffolding) |
| 25/05 | updating documentation | 00:45:12 | Known-issues register write-up |
| 25/05 | error tracking improvements | 01:15:41 | **Issue #2 (Luckhardt #7534)** — `expired` disposition / `error_message` surfacing for out-of-window GCLIDs |
| 26/05 | analyzing issues with classifications | 02:35:40 | **Issue #4 (Lowe #7428)** — CallRail calls bound to a non-adjacent sibling → `channel = 'Other'` |
| 26/05 | analyzing issues with classifications | 02:17:10 | **Issue #1 (Wydro #7679)** — `correlate_callrail_estimate()` tiebreak, booking on a canceled duplicate *(Wydro estimates were created 25/05 evening)* |
| 27/05 | updating documentation | 00:57:20 | Known-issues register write-up |
| 27/05 | analyzing issues with classifications | 00:00:16 | **Issue #4 (Lowe #7428)** |
| 27/05 | analyzing issues with classifications | 00:43:44 | **Issue #4 (Lowe #7428)** |
| 27/05 | analyzing implementation | 00:30:54 | **Issue #3 (Cross #7454)** — reviewing migration `20260526000002` + repeat-customer discovery branch |
| 28/05 | analyzing implementation | 00:27:01 | **Issue #3 (Cross #7454)** — migration / discovery analysis |
| 29/05 | analyzing errors | 01:07:31 | **Issue #2 (Luckhardt #7534)** — expired-window analysis (70-estimate simulation, 6 out-of-window) |
| 30/05 | analyzing errors | 00:04:53 | **Issue #2 (Luckhardt #7534)** — expired-window analysis |
| | **Total** | **12:44:53** | |

## Grouped by issue investigation

| Issue investigation | Duration | Status |
|---------------------|---------:|--------|
| **Issue #4** — Lowe #7428 (CallRail tiebreak → `channel = 'Other'`) | 03:19:40 | documented |
| **Issue #1** — Wydro #7679 (CallRail tiebreak → booking on canceled duplicate) | 02:17:10 | documented |
| **Issue #2** — Luckhardt #7534 (repeat-customer GCLID, expired 90-day window) | 02:28:05 | documented |
| **Issue #3** — Cross #7454 (repeat-customer follow-up, all stages out-of-window) | 00:57:55 | documented |
| Known-issues register documentation (covers all four issues) | 03:42:03 | complete |
| **Total** | **12:44:53** | |

Two root-cause threads account for the bulk of the week:
- **CallRail correlation tiebreak** (Issues #1 + #4): **05:36:50** combined — the `ORDER BY created_at DESC LIMIT 1` per-customer binding, manifesting as a funnel split (Wydro) and a channel mis-classification (Lowe).
- **Repeat-customer GCLID / 90-day window** (Issues #2 + #3): **03:26:00** combined — out-of-window GCLIDs surfacing as `expired`, plus review of the unapplied migration `20260526000002`.

## Cases reviewed — no issue found

The following customers were also examined during this investigation window and **cleared as no-issue** (attribution, channel classification, and conversion stages all resolved as expected — no funnel split, mis-classification, or out-of-window surprise):

**Batch 1**

- Chris Baumann
- Amy Struikman
- Edward Trexler
- Carlease Clark
- Alisha Hessler
- Michael Scott Johnson
- Grayson DeBlasi
- Luis Herrera
- Rodney Boblitt
- Jennifer Widmar
- Michael Henderson
- Modular Building Systems International
- Heather Perry

**Batch 2**

- Darren Anthony
- Wesley Luckhardt
- Sarah Kelly
- Ethan Stone
- Maria Lopez
- Robert O'connell
- Jennifer Wu
- Jessica Wu
- David Evans
- Ava Chen
- Amee Yammine
- Gaby Bejarano
- William Foley
- David Wentworth
- Aaron Bolster

> Note: **Wesley Luckhardt** appears here and is also the named customer in **Issue #2 (#7534)**. The no-issue clearance applies to his other reviewed estimates; the specific repeat-customer/expired-window edge case on #7534 is the one documented as Issue #2.

## Notes

- **The Clockify descriptions never name a customer**, so the per-issue split within the two shared-root-cause threads (CallRail correlation → Issues #1/#4; repeat-customer GCLID → Issues #2/#3) is **inferred** from each issue's theme and the estimate-creation timeline. The thread-level totals (05:36:50 and 03:26:00) are firm; the within-thread allocation between the two paired issues is an estimate.
- **The Wydro case (#7679) anchors the register** — its two duplicate estimates were created 25/05 evening (19:26 / 19:34), at the very start of this Clockify week, which is why the deep correlation analysis lands on 26/05.
- **"analyzing issues with classifications"** (≈5h37m, 26–27/05) is the largest bucket and maps to the CallRail-correlation root cause behind Issues #1 and #4 — the channel/estimate binding that decides how a call "classifies" onto an estimate.
- **"analyzing implementation"** (27–28/05) is the review of the unapplied migration `20260526000002_booking_lead_repeat_customer_gclid.sql` — the open question carried across Issues #1–#3 (pending deploy vs. abandoned).
- **No code or schema changes shipped this week.** Per the register's own framing, `conversion-known-issues` is a *research-phase* document; implementation is deferred until an issue graduates into its own change. The ~3h42m of "updating documentation" is that register write-up plus the companion `full-stack-architecture/spec.md` updates.
