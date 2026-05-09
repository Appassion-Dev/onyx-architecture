## Context

`ConversionsPage.tsx` is a ~1600-line single-file React component. Its current mental model is: one dataset, multiple optional row filters, with the `stepFilter` as just another filter. The hierarchy date, value field, upload cells, and detail panel are all fixed regardless of what stage the user is triaging.

Current state:
- `stepFilter` is a `useState<string>('all')` that filters rows but drives nothing else.
- `getRowDateKeys()` always reads `estimate_created_at`.
- `computeStats()` always sums `display_value`.
- `PipelineStrip` always renders all three `PhaseCell` components.
- The expanded detail panel always renders all three `StageDetail` sections fully expanded.
- Zero-value filter always checks `display_value`.

The existing `STEP_TABS` array has 6 options: All, Pre-discovery, Booking, Qualified, Converted, Closed. "All" and "Closed" are being removed.

## Goals / Non-Goals

**Goals:**
- Make `conversionMode` (replacing `stepFilter`) the single source of truth for: date field, value field, upload cell, detail layout, zero-value filter field, and rollup value.
- Remove "All" and "Closed" tabs so every view has a clear temporal and monetary context.
- Default to Qualified mode on page load.
- Keep the component in a single file (no new files needed).

**Non-Goals:**
- Changing the data source — `vw_conversion_candidates` already has all three value columns.
- Changing any Supabase edge function or backend logic.
- Adding persistence of the selected mode (URL params, localStorage) — that's a future change.
- Changing the source/medium/campaign/assignee filters — they remain unchanged.

## Decisions

### Decision 1: `conversionMode` as a typed union, not a string

Replace `stepFilter: string` with `conversionMode: ConversionMode` where:

```ts
type ConversionMode = 'pre-discovery' | 'booking' | 'qualified' | 'converted';
```

**Rationale**: A typed union enables exhaustive switch patterns, eliminates string comparison bugs, and makes the mode-to-configuration lookup explicit. Alternative (keeping `string`) was rejected because mode now drives 5+ behaviors and needs to be safe to extend.

### Decision 2: Mode config object drives all context-dependent values

Define a lookup at the module level:

```ts
const MODE_CONFIG: Record<ConversionMode, {
  dateField:  (row: PipelineRow) => string | null;
  valueField: (row: PipelineRow) => number | null;
  stageType:  ConversionType | null;
  label:      string;
  showValue:  boolean;
  showZeroToggle: boolean;
}> = { ... }
```

Components and derived values (`computeStats`, `getRowDateKeys`, zero-value filter) read from `MODE_CONFIG[mode]` rather than having parallel switch/if blocks scattered through the file.

**Rationale**: Single place to change mode behavior. Alternative (inline switch at each callsite) was rejected because the mode logic would be duplicated ~6 times and drift over time.

### Decision 3: `getRowDateKeys` accepts the date ISO string directly

Currently `getRowDateKeys(row)` hardcodes `row.estimate_created_at`. Change signature to accept a pre-resolved ISO string:

```ts
function getRowDateKeys(iso: string | null): { monthKey, weekKey, monthLabel, weekLabel }
```

Callers: `buildHierarchy(rows, mode)` resolves `MODE_CONFIG[mode].dateField(row)` and passes the result. This keeps date logic pure and testable without mode knowledge.

### Decision 4: Collapsed StageDetail sections via `isCollapsed` prop

Add an `isCollapsed?: boolean` prop to `StageDetail`. When true, the section renders only a one-line summary row (label + status badge + value if present) with no sub-content. The expanded detail panel passes `isCollapsed={true}` to all sections *except* the primary one for the current mode.

**Rationale**: Keeps sections cross-referenceable (user can see booking GCLID while in qualified mode) without cluttering the workflow. Alternative (hide non-primary sections entirely) was rejected because it removes useful context.

### Decision 5: Single `PhaseCell` per mode, no strip

Remove `PipelineStrip`. The pipeline column in each row renders:
- Pre-discovery: nothing (column hidden / shows `—`)
- Other modes: one `PhaseCell` for the active stage

The column header label changes to match the mode ("Upload" or nothing).

**Rationale**: Removes visual noise and focuses the user on the one action available for their current context.

### Decision 6: Default mode is `'qualified'`

**Rationale**: The qualified stage is where daily upload work happens. Booking is high-volume but lower-priority for uploads. Converted is the output stage. Pre-discovery is triage. Qualified is the most-used context.

### Decision 7: `resetFilters` sets mode back to `'qualified'`

When the user resets all filters, mode returns to the default rather than resetting to "all" (which no longer exists).

## Risks / Trade-offs

- **Hierarchy re-sort on tab switch**: Changing from `estimate_created_at` to `booking_datetime` may reorder or re-bucket estimates the user was looking at. No mitigation needed — this is intentional and correct behavior.
- **Pre-discovery rows with no datetime**: `estimate_created_at` should always be present for pre-discovery rows, but `booking_datetime`/`qualified_datetime`/`converted_datetime` will be NULL for rows that haven't reached that stage. `getRowDateKeys` already handles null ISO gracefully (falls back to 'Unknown' bucket). The mode filter ensures only rows with the relevant stage are shown (except pre-discovery which shows no-stage rows). → Low risk.
- **`computeStats` value sum changes per tab**: The month/week rollup value will change when switching tabs, which may surprise users who expected continuity. No mitigation — this is correct and intentional.
- **`retryCandidateCount` currently counts all stages**: After the change, it should only count the active mode's stage. This is a small but important correctness fix to include.

## Open Questions

- Should the "Show zero values" toggle label change text on the Qualified tab to "Show $0 estimates" or keep the generic label? (No strong opinion — keep generic for now.)
- Should Pre-discovery rows hide both Pipeline and Value columns, collapsing the right-side card to just the row label + source badges? Or keep the card structure with `—` placeholders? (Proposal says simplified row — confirm during implementation.)
