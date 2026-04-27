## Why

The new reconciliation reporting page answers the right operational question, but its daily table still makes operators decode shorthand instead of judging the uploads quickly. Letter-coded source mix, compact comparison strips, and missing row-state cues make it harder than it should be to spot whether a day is balanced, one-sided, or worth investigating.

## What Changes

- Add a visual-judgment layer to the reconciliation reporting table so each day row communicates source mix, comparison context, and row state without relying on ambiguous letter codes.
- Replace compressed source-mix shorthand with labeled visual tokens that can use color, ordering, and optional overflow treatment while still preserving the existing exclusive `form`, `calls`, `thumbtack`, and `other` buckets.
- Replace the prior-day shorthand strip with a clearer comparison presentation that names the compared period and the metrics being compared.
- Add explicit row-state indicators for matched rows, local-only rows, and Google-only rows so operators can distinguish missing-side data from true mismatches.
- Keep the reporting page honest about aggregate reconciliation while making mismatch detection and row triage materially faster.

## Capabilities

### New Capabilities
- `upload-reconciliation-visuals`: Visual affordances on the reconciliation reporting page that make daily rows easier to interpret, compare, and triage.

### Modified Capabilities
<!-- Existing capabilities whose REQUIREMENTS are changing (not just implementation).
     Only list here if spec-level behavior changes. Each needs a delta spec file.
     Use existing spec names from openspec/specs/. Leave empty if no requirement changes. -->

## Impact

- `horizon-dashboard/src/components/pages/ConversionReportingPage.tsx`: the daily reconciliation table will need a clearer row presentation for source mix, comparison context, and one-sided data states.
- Shared dashboard UI primitives such as badges, tooltips, and table cells may need light reuse or extension to support wrapped chips and richer row detail.
- No new Google Ads requests should be introduced; the change should continue using the existing reporting dataset and state flags already exposed by the reconciliation view.
- This proposal is a follow-on to `add-upload-reconciliation-reporting` and should be implemented alongside or after that reporting surface lands.