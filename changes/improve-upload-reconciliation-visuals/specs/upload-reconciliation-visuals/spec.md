## ADDED Requirements

### Requirement: Daily rows use labeled source mix tokens
The system SHALL render daily reconciliation source mix using labeled visual tokens with stable per-bucket styling and explicit counts, instead of single-letter abbreviations. Only local source buckets with non-zero counts SHALL be shown for a row, and rows without local uploaded counts MUST show a clear no-local-source state rather than four zero-value tokens.

#### Scenario: Mixed local source day
- **WHEN** a daily reconciliation row has local uploaded counts across `form`, `calls`, and `thumbtack`
- **THEN** the row shows labeled source tokens such as `Form`, `Calls`, and `Thumbtack` with their counts rather than `F`, `C`, and `T` abbreviations

#### Scenario: Google-only day has no misleading source tokens
- **WHEN** a daily reconciliation row has Google summary data and zero local uploaded rows
- **THEN** the source-mix cell shows that no local source mix is available and does not render zero-value bucket tokens

### Requirement: Daily rows show explicit prior-day comparison context
The system SHALL render prior-day comparison with the referenced comparison day and labeled metric deltas for uploaded, successful, and failed counts. If no prior-day row exists for the event, the system MUST render comparison unavailable rather than implying a zero baseline.

#### Scenario: Prior-day comparison exists
- **WHEN** a daily reconciliation row for April 20 has a corresponding April 19 row in the same event section
- **THEN** the row shows that it is comparing against April 19 and labels the uploaded, successful, and failed deltas explicitly

#### Scenario: Prior-day comparison is missing
- **WHEN** a daily reconciliation row has no corresponding row for the immediately previous day
- **THEN** the comparison area indicates that prior-day comparison is unavailable instead of rendering deltas against zero

### Requirement: Daily rows expose aggregate judgment state
The system SHALL surface an at-a-glance judgment tag for each daily reconciliation row using the displayed aggregate counts and data-presence flags so operators can distinguish balanced rows, imbalanced rows, and one-sided rows quickly. This judgment tag MUST remain framed as aggregate reconciliation state, not row-level proof of acceptance.

#### Scenario: Balanced aggregate row
- **WHEN** a daily reconciliation row has local uploads and Google counts for the same day, and `local uploaded = successful + failed`
- **THEN** the row shows a balanced judgment state

#### Scenario: Imbalanced aggregate row
- **WHEN** a daily reconciliation row has both local and Google-side data, and `local uploaded` differs from `successful + failed`
- **THEN** the row shows an imbalanced judgment state that is visually distinct from a balanced row

#### Scenario: Local-only row
- **WHEN** a daily reconciliation row has local uploaded data and no Google-side summary for that day
- **THEN** the row shows a local-only judgment state

#### Scenario: Google-only row
- **WHEN** a daily reconciliation row has Google-side summary data and no local uploaded rows for that day
- **THEN** the row shows a Google-only judgment state