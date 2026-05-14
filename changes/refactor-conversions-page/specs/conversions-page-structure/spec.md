## ADDED Requirements

### Requirement: Feature folder location for conversions UI

All Conversions page code (orchestrator, hooks, pure logic, primitives, hierarchy, row, row-details, dialog, and config page) SHALL live under `horizon-dashboard/src/components/conversions/`. The file `horizon-dashboard/src/components/pages/ConversionsPage.tsx` SHALL exist only as a thin re-export of the orchestrator from the feature folder, so the router import path is preserved.

#### Scenario: Router import path is unchanged
- **WHEN** the application router imports `ConversionsPage` from `pages/ConversionsPage`
- **THEN** the import SHALL succeed and SHALL resolve to the orchestrator implemented inside `components/conversions/ConversionsPage.tsx`

#### Scenario: No conversions code outside the feature folder
- **WHEN** searching `horizon-dashboard/src/` for definitions of `PipelineRow`, `ConversionMode`, `MODE_CONFIG`, `classifyChannel`, `computeStats`, `buildHierarchy`, `getPendingEstimateIds`, `getPhaseConfig`, `PipelineRowItem`, `PipelineStrip`, `PhaseCell`, `MonthCard`, or any other Conversions-page identifier
- **THEN** all definitions SHALL be located inside `components/conversions/` (the `pages/ConversionsPage.tsx` re-export is the only exception)

#### Scenario: Conversions config page is co-located
- **WHEN** the conversions configuration page (route `/conversions/config`) is implemented
- **THEN** its source SHALL live under `components/conversions/config/`

### Requirement: Three-layer separation of pure logic, hooks, and components

The feature folder SHALL be organized into three top-level layers — `lib/` for pure non-React functions, `hooks/` for stateful hooks (including all `useQuery` and `useState` clusters), and `components/` for React components. Imports SHALL flow only in the direction `components → hooks → lib`. Files in `lib/` SHALL NOT import React or any file from `hooks/` or `components/`.

#### Scenario: Pure functions have no React dependency
- **WHEN** any file under `components/conversions/lib/` is inspected
- **THEN** it SHALL NOT import from `react`, `@tanstack/react-query`, or any file under `hooks/` or `components/`

#### Scenario: Hooks do not depend on components
- **WHEN** any file under `components/conversions/hooks/` is inspected
- **THEN** it SHALL NOT import any file from `components/conversions/components/`

### Requirement: Shared types and constants live in dedicated files

All TypeScript type and interface declarations used across the feature SHALL live in `components/conversions/types.ts`. All shared constant data (mode configuration, step tabs, channel order, source-bucket configuration, dot colors, shared layout class strings) SHALL live in `components/conversions/constants.ts`. `constants.ts` MAY import from `types.ts`; `types.ts` SHALL NOT import from `constants.ts`.

#### Scenario: Single source of truth for types
- **WHEN** any file in the feature folder needs `PipelineRow`, `RollupStats`, `ConversionMode`, `MonthGroup`, `WeekGroup`, `SourceGroup`, `ConversionConfig`, `BulkUploadTarget`, or `PhaseCellConfig`
- **THEN** it SHALL import that type from `components/conversions/types.ts`

#### Scenario: Single source of truth for constants
- **WHEN** any file in the feature folder needs `MODE_CONFIG`, `STEP_TABS`, `CHANNEL_ORDER`, `sourceBucketConfig`, `BUCKET_DOT_COLORS`, or `ROLLUP_METRIC_RAIL_CLASS`
- **THEN** it SHALL import that constant from `components/conversions/constants.ts`

### Requirement: Filter cluster encapsulated in a single hook

A hook `useConversionFilters(rows: PipelineRow[])` SHALL own the entire filter cluster: `mode`, `channel`, `campaign`, and `assignee` state, all derived `filteredRows`, all derived option lists (`channelOptions`, `campaignOptions`), all derived counts (`activeFilterCount`, `pendingEstimateIds`, `retryCandidateCount`, `missingGclidCount`, `gclidCoveragePct`), the derived `filterSummaryLabel`, the derived `stats`, and a `resetFilters` callback. Adding a new filter dimension SHALL be possible by editing only `useConversionFilters.ts` and `ConversionsFilterBar.tsx`.

#### Scenario: Single hook returns the full filter cluster
- **WHEN** the orchestrator page renders
- **THEN** it SHALL obtain mode, channel, campaign, assignee, filteredRows, options, counts, summary label, stats, and reset callback from a single call to `useConversionFilters(rows)`

#### Scenario: Adding a new filter is a 2-file change
- **WHEN** a contributor adds a new filter dimension (e.g. date range)
- **THEN** the change SHALL touch only `hooks/useConversionFilters.ts` and `components/header/ConversionsFilterBar.tsx`, with no edits required in the orchestrator, hierarchy, or row components

### Requirement: Bulk upload flow encapsulated in a single hook

A hook `useBulkUpload(refetch: () => void)` SHALL own the bulk-upload dialog target state, the cancellable countdown timer, the toast lifecycle, and the upload `fetch` call to `google-ads-conversion-upload`. The hook SHALL expose at minimum `{ target, open(target), close(), confirm() }` (or equivalent) so the orchestrator and dialog component contain no direct timer or fetch logic.

#### Scenario: Orchestrator does not own bulk-upload state
- **WHEN** the orchestrator page is inspected
- **THEN** it SHALL NOT contain any `useState` for the bulk-upload target, any `setTimeout` for the countdown, or any direct `fetch` call to the upload edge function

### Requirement: Data-fetch hooks wrap the existing `useQuery` calls

A hook `useConversionsPipeline()` SHALL wrap the `vw_conversion_candidates` query and a hook `useConversionConfigs()` SHALL wrap the `gads_conversion_config` query. Both hooks SHALL preserve the existing query keys (`'gads-conversions-pipeline'` and `'gads-conversion-config'`) so cache behavior is unchanged across the refactor.

#### Scenario: Pipeline query key is preserved
- **WHEN** `useConversionsPipeline()` is called
- **THEN** it SHALL register a TanStack Query with key `['gads-conversions-pipeline']`

#### Scenario: Configs query key is preserved
- **WHEN** `useConversionConfigs()` is called
- **THEN** it SHALL register a TanStack Query with key `['gads-conversion-config']`

### Requirement: Stage-rendering driven by `getPhaseConfig`

A pure function `getPhaseConfig(stage, row, configs)` in `components/conversions/lib/getPhaseConfig.ts` SHALL be the single source of truth for stage-cell rendering data (status, label, value, popover content, upload eligibility). `PhaseCell` SHALL consume this function exclusively. Adding a new pipeline stage SHALL be possible by extending `ConversionMode`, `MODE_CONFIG`, `STEP_TABS`, and adding a branch in `getPhaseConfig` — with no edits required in `PhaseCell`, `PipelineStrip`, `PipelineRowItem`, hierarchy components, or hooks.

#### Scenario: Adding a new stage does not touch row components
- **WHEN** a contributor adds a new pipeline stage to `ConversionMode`
- **THEN** the change SHALL be limited to `types.ts`, `constants.ts`, and `lib/getPhaseConfig.ts` (plus optional new fields on `PipelineRow` if the view exposes new columns), with no edits required in `components/pipeline-strip/`, `components/pipeline-row/`, `components/hierarchy/`, or `hooks/`

#### Scenario: PhaseCell delegates configuration to getPhaseConfig
- **WHEN** `PhaseCell` renders
- **THEN** it SHALL derive its status, label, value display, and popover content from a single call to `getPhaseConfig(stage, row, configs)`

### Requirement: Hierarchy chain takes drilled props (no context)

The rendering chain `MonthCard → WeekBlock → SourceGroupBlock → PipelineRowItem` SHALL pass `mode`, `configs`, and `refetch` as explicit props. The feature folder SHALL NOT introduce a React Context for these values. `PipelineRowItem` SHALL remain wrapped in `React.memo` and SHALL receive only stable prop references (the `configs` object from `useConversionConfigs`, the `refetch` callback from `useConversionsPipeline`, and the primitive `mode`).

#### Scenario: No conversions context module exists
- **WHEN** searching the feature folder for `createContext`
- **THEN** no occurrence SHALL be found

#### Scenario: Memoized row preserves identity
- **WHEN** a parent re-render occurs without a change to `row`, `configs`, `refetch`, or `mode` for a given row
- **THEN** that `PipelineRowItem` SHALL NOT re-render (verifiable in React DevTools profiler)

### Requirement: Row-detail panels are self-contained

Each row-detail panel (`CallHistoryTable`, `BookingTagsTable`, `EstimateOptionsTable`, `JobDetailSection`) SHALL live in its own file under `components/conversions/components/row-details/` and SHALL own its own `useQuery` keyed by the estimate id. Panels SHALL only fetch when the row is expanded (i.e. they are mounted only inside the expanded branch of `PipelineRowItem`).

#### Scenario: A row-detail query does not fire for collapsed rows
- **WHEN** a `PipelineRowItem` is in the collapsed state
- **THEN** none of `CallHistoryTable`, `BookingTagsTable`, `EstimateOptionsTable`, or `JobDetailSection` SHALL be mounted, and no row-detail query SHALL be issued for that estimate

### Requirement: No barrel `index.ts` re-exports inside the feature folder

The feature folder SHALL NOT contain `index.ts` files that re-export sibling modules. Each consumer SHALL import directly from the file that defines a symbol.

#### Scenario: No barrel files in the feature folder
- **WHEN** listing `components/conversions/` and its subfolders
- **THEN** no `index.ts` file SHALL exist anywhere in the tree

### Requirement: Behavior, query keys, and route are preserved

The refactor SHALL NOT change the page's observable behavior, the network calls it makes, the Supabase query keys it uses, the public route, or the visual output. The orchestrator after refactor SHALL render the same DOM, fire the same Supabase calls, use the same TanStack query keys, and respond to user interactions identically to the pre-refactor implementation.

#### Scenario: Smoke test parity
- **WHEN** the post-refactor page is loaded and a user switches modes, applies filters, expands a row, scrolls row-detail panels, opens the bulk-upload dialog, triggers Refresh, triggers Scan Now, and opens Settings
- **THEN** every interaction SHALL produce the same network calls, DOM structure, and visual output as the pre-refactor page

#### Scenario: Public route is preserved
- **WHEN** the application is built and the router is exercised
- **THEN** the route that previously rendered `ConversionsPage` SHALL continue to render the (re-exported) orchestrator with no path change
