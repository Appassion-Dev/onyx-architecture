## Context

`add-upload-reconciliation-reporting` introduces a daily reconciliation table with the right aggregate counts, but the current row presentation still makes operators interpret shorthand before they can judge the day. The present design compresses source mix into single-letter codes, collapses prior-day comparison into unlabeled deltas, and leaves one-sided local-only or Google-only rows implicit even though the reporting dataset already exposes the needed state.

This follow-on change is intentionally narrow: improve how the daily reconciliation row communicates meaning without widening the underlying reporting contract. The existing reporting view already exposes exclusive source-bucket totals and `has_local_data` / `has_google_data` flags, so the main work is to turn those fields into a clearer, more trustworthy presentation.

Constraints:
- keep the page cache-backed and frontend-driven; no live Google Ads requests
- preserve the current exclusive local buckets: `form`, `calls`, `thumbtack`, `other`
- preserve the aggregate-reconciliation framing so no visual state implies row-level proof of acceptance
- fit inside the existing fixed-layout table system and remain readable on narrower widths

## Goals / Non-Goals

**Goals:**
- Make each daily row interpretable at scan speed without a legend.
- Make prior-day comparison explicit enough that missing comparison rows are not mistaken for zero baselines.
- Surface one-sided and imbalanced day states so operators can triage rows faster.
- Reuse the existing reporting dataset and dashboard UI primitives instead of expanding the backend surface area.

**Non-Goals:**
- Redesign the weekly rollup table in the same pass.
- Add new reporting queries, views, or source-taxonomy buckets.
- Prove row-level Google acceptance or attribution.
- Replace the broader aggregate-reconciliation copy already defined for the reporting page.

## Decisions

### D1: Render source mix as labeled chips with stable bucket styling

The daily row will replace one-letter source shorthand with labeled tokens such as `Form 8`, `Calls 3`, `Thumbtack 2`, and `Other 1`. Each bucket will use stable visual styling so operators can learn the palette over time, with color as reinforcement rather than the only cue.

Only non-zero local buckets will render for a row. If a row has no local uploads, the cell will render a clear empty-state label rather than four zero tokens. This reduces noise and makes Google-only days immediately obvious.

**Alternative considered:** keep the current compact `F/C/T/O` string and add a legend. Rejected because it still forces users to decode the row and does not solve the ambiguity between `F = Form` in source mix and `F = Failed` in prior-day comparison.

### D2: Replace shorthand prior-day deltas with an explicit comparison block

The current comparison strip will be replaced with a small comparison block that names the referenced prior day and labels the metric deltas for uploaded, successful, and failed counts. The presentation can remain compact, but the labels must be explicit.

When the prior day does not exist in the selected range or the dataset, the row will show a comparison-unavailable state instead of implicitly comparing against zero. This avoids false confidence on sparse days.

**Alternative considered:** continue treating missing prior rows as zero totals. Rejected because it produces deltas that look mathematically precise while hiding the fact that no prior comparison row exists.

### D3: Add an at-a-glance row judgment tag derived from existing counts

Each daily row will surface a judgment tag derived from the existing aggregate counts and presence flags. The initial states are:
- `Balanced` when both sides exist and `local_uploaded_count = google_successful_count + google_failed_count`
- `Partial` when both sides exist but the aggregate totals do not balance
- `Local only` when local data exists without Google-side data
- `Google only` when Google-side data exists without local uploaded rows

This uses already available fields and gives operators a fast first-pass triage cue. The tag remains an aggregate status only; it does not imply that individual upload rows were accepted.

**Alternative considered:** show only presence-state tags (`Both sides`, `Local only`, `Google only`). Rejected because it leaves operators to do mental arithmetic on the rows that actually matter most: days where both sides exist but the totals do not reconcile.

### D4: Keep the change frontend-only and reuse existing UI primitives

The page will continue reading the existing reconciliation dataset and derive all new visual states in the app layer. Source chips and judgment tags can reuse existing badge primitives, while comparison detail can use wrapped table cells and optional tooltip/popover affordances if needed for narrow widths.

Avoiding new backend work keeps the change safe to ship alongside the existing reporting feature and minimizes coordination risk with the still-open reporting dataset validation task.

**Alternative considered:** widen the SQL view with precomputed visual-state fields. Rejected because the needed inputs already exist, and visual judgment rules are presentation logic that is easier to evolve in the UI.

### D5: Prefer wrapped row content over additional columns

The improvement will increase meaning inside the existing daily table rather than adding more columns. Source tokens should wrap within the Source Mix cell, while comparison content should stack or condense within the existing Previous Day cell.

This preserves the overall table structure and avoids making the page substantially wider, while still allowing richer content than the current one-line abbreviations.

**Alternative considered:** add dedicated `Status` or `Processed` columns. Rejected for the first pass because the table already has horizontal pressure, and the judgment information can be integrated into existing cells.

## Risks / Trade-offs

- [Color becomes the only meaning carrier] -> Pair every colored treatment with explicit text labels and counts.
- [Balanced/Partial tags are misread as row-level acceptance proof] -> Keep the existing aggregate-reconciliation copy and, where helpful, attach tooltip language that explains the tag is derived from aggregate counts only.
- [Wrapped chips make dense rows taller] -> Render only non-zero buckets, keep token text short, and allow tooltip/popover overflow only if the live layout still feels crowded.
- [Missing prior-day states feel visually inconsistent] -> Use a deliberate muted empty-state treatment so operators can distinguish unavailable comparison from true zero change.

## Migration Plan

1. Update the reporting page row helpers to derive labeled source tokens, explicit comparison state, and judgment tags from the existing row data.
2. Replace the current source-mix shorthand and comparison strip in the daily reconciliation table.
3. Validate the new states against matched rows, imbalanced rows, local-only rows, Google-only rows, and rows with no prior-day comparison.
4. Roll back by restoring the existing daily row presentation if the denser layout proves too noisy in production feedback.

## Open Questions

- Should the imbalance tag use `Partial`, `Needs review`, or another label that is less likely to be read as a pipeline failure?
- Should the weekly rollup table adopt the same judgment language in the same change, or stay unchanged until the daily version is proven useful?