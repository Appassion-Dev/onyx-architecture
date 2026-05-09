## 1. Row State Derivation

- [x] 1.1 Add daily-row helpers in the reporting page that derive labeled source tokens, prior-day comparison availability, and aggregate judgment state from the existing reconciliation dataset.
- [x] 1.2 Update the daily table cell layout to support wrapped chips and a richer comparison block without adding new backend queries or widening the table structure materially.

## 2. Daily Reconciliation UI

- [x] 2.1 Replace the `F/C/T/O` source-mix shorthand with labeled visual tokens and a clear no-local-source empty state for Google-only rows.
- [x] 2.2 Replace the current previous-day delta strip with an explicit comparison presentation that names the referenced prior day and falls back to a comparison-unavailable state when no prior row exists.
- [x] 2.3 Add aggregate judgment tags for balanced, imbalanced, local-only, and Google-only rows, keeping the aggregate-only caveat visible in the UI.

## 3. Validation

- [x] 3.1 Validate the updated row UI against balanced rows, imbalanced rows, local-only rows, Google-only rows, and rows with no previous-day comparison.
- [x] 3.2 Verify the daily table remains readable on desktop and narrower widths, including chip wrapping or overflow behavior inside the existing table layout.