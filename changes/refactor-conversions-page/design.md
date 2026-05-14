## Context

[horizon-dashboard/src/components/pages/ConversionsPage.tsx](horizon-dashboard/src/components/pages/ConversionsPage.tsx) is a 2,040-line / ~92 KB single-file React module containing the entire Conversions Uploads page. Internally it is already well-factored into ~25 named functions (components and pure helpers), but they all share one file. A grep across `horizon-dashboard/src/**` confirmed that **none** of the helpers, types, or sub-components are imported from anywhere else — the file is purely self-contained.

Existing structural conventions in this repo:

- [horizon-dashboard/src/components/booking/](horizon-dashboard/src/components/booking/) uses a deeper structure: `BookingWizard.tsx`, `BookingContext.tsx`, `types.ts`, a `steps/` subfolder, and several editor components.
- [horizon-dashboard/src/components/sales/](horizon-dashboard/src/components/sales/) and [horizon-dashboard/src/components/estimates/](horizon-dashboard/src/components/estimates/) use a flat layout — files only.
- `pages/` holds page-level routed components (typically thin wrappers over feature folders).

The next planned wave of work explicitly involves changing the table structure, swapping/extending hooks, and adding new pipeline stages or filters. The architecture decisions below are made to optimize for **easy future extensibility**, per the user's directive.

Current internal map (lines approximate):

```
ConversionsPage.tsx  (2040 lines)
  20–290   types + pure logic       (PipelineRow, RollupStats, MODE_CONFIG, classifyChannel, computeStats, buildHierarchy, …)
 288–390   small presentational atoms (SyncBadge, RollupMetricCell, OverviewStatCard, FilterField, PipelineStatusIcon)
 394–855   pipeline stage primitives  (StageDetail, getPhaseConfig, PhaseCell, PhaseConnector, PipelineStrip, BulkUploadToast, getPendingEstimateIds)
 856–1213  4 row-detail data widgets (CallHistoryTable, BookingTagsTable, EstimateOptionsTable, JobDetailSection — each owns its own useQuery)
1215–1405  PipelineRowItem (memo)
1405–1430  PipelineHeader
1431–2040  ConversionsPage component (state, queries, handlers, JSX)
```

## Goals / Non-Goals

**Goals:**

- Reduce `ConversionsPage.tsx` from 610 lines (the page-component portion) to ~60 lines of orchestration.
- Make the next wave of functional changes easy: adding a filter, adding a pipeline stage, swapping the data source, replacing the row layout, or adding a row-detail panel should each be a single-folder edit.
- Preserve current behavior bit-for-bit: same network calls, same query keys, same memoization, same DOM, same CSS classes, same `/conversions/config` route.
- Co-locate all conversions UI (including config) under one feature folder to avoid the "where does this live?" question.
- Codify the resulting structure as a spec capability so the seams survive future drift.

**Non-Goals:**

- No behavioral changes (filters, uploads, discovery, badges, bulk flow all behave identically).
- No new tests in this change (per user request — the structural seams enable future tests, but adding them is a follow-up).
- No CSS deduplication (the repeated `bg-[linear-gradient(...)]`, `rounded-[28px]`, etc. stay inline; a `Surface` primitive is deferred).
- No context-API introduction (props are drilled — see Decision 4).
- No change to the public route or to the `pages/ConversionsPage.tsx` import path used by the router.
- No change to query keys (`'gads-conversions-pipeline'`, `'gads-conversion-config'`) so cache behavior is preserved across the refactor deploy.
- No `index.ts` barrel files (see Decision 7).

## Decisions

### 1. Feature folder lives at `src/components/conversions/`, not under `pages/`

We follow the [booking/](horizon-dashboard/src/components/booking/) pattern (peer to `pages/`) rather than nesting under `pages/`. `pages/ConversionsPage.tsx` becomes a thin re-export:

```tsx
// pages/ConversionsPage.tsx
export { ConversionsPage } from '../conversions/ConversionsPage';
```

**Why:** keeps the router import path stable (no app-wide grep needed), matches the convention of feature folders being peers to `pages/`, and lets the conversions config page (`conversions/config/`) live under the same root.

**Alternative considered:** nest at `pages/conversions/`. Rejected because no other feature does this and it implies "page-only" code while the folder will hold hooks, lib, primitives.

### 2. Folder layout

```
src/components/conversions/
├── ConversionsPage.tsx              ← orchestrator, ~60 lines
├── types.ts                         ← all type/interface declarations
├── constants.ts                     ← MODE_CONFIG, STEP_TABS, CHANNEL_ORDER,
│                                       sourceBucketConfig, BUCKET_DOT_COLORS,
│                                       ROLLUP_METRIC_RAIL_CLASS
│
├── lib/                             ← pure functions, no React imports
│   ├── format.ts                    (formatDateTime, formatCurrency,
│   │                                  formatWholeNumber, formatDuration)
│   ├── classifyChannel.ts
│   ├── computeStats.ts
│   ├── buildHierarchy.ts            (+ getRowDateKeys, kept private)
│   ├── getPendingEstimateIds.ts
│   └── getPhaseConfig.ts
│
├── hooks/                           ← all useQuery + useState clusters
│   ├── useConversionsPipeline.ts
│   ├── useConversionConfigs.ts
│   ├── useConversionFilters.ts      ← OWNS mode + 3 filters + filteredRows +
│   │                                   options + activeFilterCount + reset
│   └── useBulkUpload.ts             ← target state + countdown + toast + fetch
│
├── components/
│   ├── primitives/                  ← stateless leaves
│   │   ├── SyncBadge.tsx
│   │   ├── RollupMetricCell.tsx
│   │   ├── OverviewStatCard.tsx
│   │   ├── FilterField.tsx
│   │   ├── PipelineStatusIcon.tsx
│   │   └── StageDetail.tsx
│   │
│   ├── header/
│   │   ├── ConversionsHeroHeader.tsx
│   │   └── ConversionsFilterBar.tsx
│   │
│   ├── pipeline-strip/
│   │   ├── PhaseCell.tsx            (getPhaseConfig stays private here OR in lib/)
│   │   ├── PhaseConnector.tsx
│   │   └── PipelineStrip.tsx
│   │
│   ├── row-details/                 ← each owns its own useQuery (already isolated)
│   │   ├── CallHistoryTable.tsx
│   │   ├── BookingTagsTable.tsx
│   │   ├── EstimateOptionsTable.tsx
│   │   └── JobDetailSection.tsx
│   │
│   ├── pipeline-row/
│   │   ├── PipelineHeader.tsx
│   │   └── PipelineRowItem.tsx      (keeps memo wrapper)
│   │
│   ├── hierarchy/
│   │   ├── MonthCard.tsx
│   │   ├── WeekBlock.tsx
│   │   └── SourceGroupBlock.tsx
│   │
│   └── bulk-upload/
│       ├── BulkUploadToast.tsx
│       └── BulkUploadConfirmDialog.tsx
│
└── config/                          ← the /conversions/config page
    └── ConversionsConfigPage.tsx    (or its existing equivalent, moved here)
```

**Why this layout:**

- **3-layer separation** (`lib/` / `hooks/` / `components/`) makes the dependency direction obvious: components depend on hooks depend on lib. No circular risk.
- **Sub-grouping inside `components/`** keeps related files visually together for the inevitable changes that touch a whole subsystem (e.g. "redesign the row" hits one folder).
- `constants.ts` is separate from `types.ts` because `MODE_CONFIG` references `PipelineRow`-typed accessor functions; `constants.ts` imports from `types.ts`, never the reverse.

### 3. Hook boundaries — fat hooks for state clusters, thin hooks for queries

| Hook | Returns | Owns |
|---|---|---|
| `useConversionsPipeline()` | the `useQuery` result `{ data, isLoading, isFetching, refetch }` | nothing else |
| `useConversionConfigs()` | the `useQuery` result + derived `anyDryRun` | nothing else |
| `useConversionFilters(rows)` | `{ mode, setMode, channel, setChannel, campaign, setCampaign, assignee, setAssignee, filteredRows, channelOptions, campaignOptions, stats, pendingEstimateIds, retryCandidateCount, activeFilterCount, gclidCoveragePct, missingGclidCount, filterSummaryLabel, resetFilters }` | all 4 useState calls, all derived useMemos |
| `useBulkUpload(refetch)` | `{ target, open, close, confirm }` | dialog state, countdown timer ref, toast lifecycle, fetch call |

**Why fat for filters:** the 4 filter pieces of state and their 8 derived memos are tightly coupled. Splitting them creates artificial seams. Future filter additions (date range, lead source, etc.) become a single-file change.

**Why fat for bulk upload:** same reasoning — state, side effect, and toast all live together.

**Why thin for queries:** they're one-liners. Wrapping them gains the testable seam needed for future "swap to a different view" work without bloat.

**Alternative considered:** a single `useConversionsPage(rows)` mega-hook returning everything. Rejected — too coarse-grained, no benefit over orchestrating two narrower hooks in the page.

### 4. Prop drilling, not context

The rendering tree has 4 levels under the page: `MonthCard → WeekBlock → SourceGroupBlock → PipelineRowItem`. Three values (`mode`, `configs`, `refetch`) need to reach the leaves.

**Decision:** drill them as props. No `<ConversionsContext>`.

**Why:**

- Three values, four levels — not painful. Explicit > magical.
- Context wrapping would introduce a new value-identity surface that interacts badly with `PipelineRowItem`'s `memo` (a context-derived object would need `useMemo` to stay stable).
- Easier to test pieces in isolation.
- Makes "what does this component need?" trivially answerable from the prop list.

**Alternative considered:** small `<ConversionsContext>` for read-mostly values. Rejected for the reasons above; can be added in a follow-up if drill depth grows.

### 5. Stage extension contract

Adding a new pipeline stage (e.g. a `revenue` stage after `converted`) MUST be possible without touching row-rendering, hierarchy, filter, or hook code. The required edits:

1. Extend `ConversionMode` union in `types.ts`.
2. Add the new mode's entry to `MODE_CONFIG` in `constants.ts`.
3. Add the mode to `STEP_TABS` in `constants.ts`.
4. Add a branch in `getPhaseConfig` (`lib/getPhaseConfig.ts`) returning the cell's status/label/value/popover content.
5. Optionally add fields to `PipelineRow` in `types.ts` if the row needs new columns from the view.

Nothing else changes. `PhaseCell`, `PipelineStrip`, `PipelineRowItem`, `MonthCard`, the filter hook, and the orchestrator page remain untouched.

This is enforced via the spec requirements in `conversions-page-structure`.

### 6. Filter extension contract

Adding a new filter dimension (e.g. a date-range filter) is a single-file change to `useConversionFilters.ts`:

1. Add a `useState` slot.
2. Add the predicate inside the `filteredRows` `useMemo`.
3. Add an option-derivation `useMemo` if the filter takes its values from data.
4. Add the new field to the returned object.
5. (UI) Add a `<FilterField>` in `ConversionsFilterBar.tsx`.

Total: 2 files. Hooks contract grows additively; no consumer breaks.

### 7. No barrel `index.ts` files

Each consumer imports from the specific file (e.g. `import { computeStats } from '../lib/computeStats'`). No re-export hubs.

**Why:** barrels create implicit ordering issues, hide the dependency graph, and complicate tree-shaking. Slightly longer imports are worth the explicitness, especially during a refactor when grep-ability matters.

### 8. `getPhaseConfig` lives in `lib/` not co-located with `PhaseCell`

It's a 45-line pure function consumed only by `PhaseCell` today, but moving it to `lib/` makes it (a) trivially unit-testable in the future and (b) a clearly identified extension point per Decision 5. Keeping it co-located would hide the extension surface.

### 9. The 4 row-detail tables stay one-file-each in `components/row-details/`

Each already owns its own `useQuery` and is self-contained. They are the simplest part of the lift — pure move. They keep their lazy-on-expand behavior because they're rendered conditionally inside `PipelineRowItem`.

### 10. PR sequencing for safe incremental delivery

Six PRs, each independently reviewable and revertable:

```
PR 1  Pure code     → types.ts, constants.ts, lib/* (move only, no tests)
PR 2  Primitives    → SyncBadge, RollupMetricCell, OverviewStatCard,
                       FilterField, PipelineStatusIcon, StageDetail,
                       PhaseConnector, PipelineHeader
PR 3  Row details   → CallHistoryTable, BookingTagsTable,
                       EstimateOptionsTable, JobDetailSection
PR 4  Strip + row   → PhaseCell, PipelineStrip, PipelineRowItem
                       (verify memo still works)
PR 5  Hierarchy +   → MonthCard, WeekBlock, SourceGroupBlock,
       bulk-upload     BulkUploadToast, BulkUploadConfirmDialog
PR 6  Hooks         → useConversionsPipeline, useConversionConfigs,
                       useConversionFilters, useBulkUpload
                       (page now ~60 lines, refactor done)
```

After each PR the page must compile cleanly and behave identically; any PR can be reverted in isolation. The `pages/ConversionsPage.tsx` re-export is added in PR 6 (the page move). Until then `pages/ConversionsPage.tsx` keeps shrinking as imports replace inline definitions.

## Risks / Trade-offs

- **[Risk] `PipelineRowItem` memo breaks because props get re-allocated each render.** → Mitigation: `configs` and `refetch` come straight from `useQuery` return values (stable references). `mode` is a primitive. Confirm via React DevTools profiler after PR 4 that `PipelineRowItem` does not re-render when its row is unchanged.
- **[Risk] Circular import between `types.ts` and `constants.ts`.** → Mitigation: enforced direction `constants.ts → types.ts`, never reverse. `MODE_CONFIG`'s accessor functions reference `PipelineRow` as a type-only import.
- **[Risk] Hidden coupling between row-detail tables and the parent's query cache.** → No coupling exists today; each detail table uses its own query key (estimate-scoped). Verified during exploration.
- **[Risk] CSS class drift across PRs.** → Mitigation: each move is mechanical (cut + paste with import path adjustments only). No reformatting allowed in the same PR.
- **[Risk] Re-export shim in `pages/ConversionsPage.tsx` confuses future contributors.** → Mitigation: a one-line comment in the shim points to the new location. Acceptable trade-off vs. updating the router and any deep-link tests.
- **[Trade-off] No tests added now.** → User-requested. The pure functions in `lib/` become trivially testable after PR 1, so adding tests is a clean follow-up that does not block this refactor.
- **[Trade-off] Drilled props instead of context.** → Slight verbosity at `MonthCard`/`WeekBlock`/`SourceGroupBlock` (3 extra props each). Accepted in exchange for memo stability and explicitness (Decision 4).
- **[Trade-off] No barrel files.** → Imports get a bit longer. Accepted for grep-ability and tree-shaking (Decision 7).

## Migration Plan

1. Land the 6 PRs in sequence (Decision 10). Each PR is independently mergeable.
2. After each PR, smoke-test the Conversions page in dev: load, switch modes, apply filters, expand a row, scroll the row-detail panels, run a bulk upload (in dry-run), trigger Refresh, trigger Scan Now, open Settings.
3. No database, edge function, or env-var changes are required.
4. **Rollback**: any single PR can be reverted independently. There is no schema migration, no edge function deployment, no cache invalidation. `git revert` is sufficient.
5. After PR 6, optionally open a follow-up issue to (a) add unit tests for `lib/`, (b) audit repeated CSS class strings for consolidation, (c) add the `<ConversionsContext>` if drill depth becomes painful.

## Open Questions

- Does the existing `/conversions/config` route point to a separate page file today, or is it part of the same `ConversionsPage.tsx`? If a separate file exists outside `pages/`, its move into `conversions/config/` is mechanical; if not, this change leaves `config/` as a placeholder folder for future use. (To resolve at start of PR 1.)
- Should `formatDateTime` / `formatCurrency` / `formatWholeNumber` move to a shared `src/lib/format.ts` instead of a feature-local file? Deferred — a quick grep across other pages can decide this in PR 1, but the safe default is feature-local.
