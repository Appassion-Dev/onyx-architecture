# OpenSpec — ONYX

Specifications and change proposals for the ONYX platform.

---

## Architecture Reference

Start here for a full top-to-bottom understanding of the system:

**[specs/full-stack-architecture/spec.md](specs/full-stack-architecture/spec.md)**

Covers: booking widget attribution → booking form → hcp-booking edge function → Supabase persistence → lead channel resolution → HCP sync → CallRail attribution → GCLID first-touch model → 3-stage conversion pipeline → Google Ads upload → analytics sync → React dashboard. Includes master flowchart and per-flow sequence diagrams.

---

## In-Progress Changes

| Change | Status |
|--------|--------|

---

## Capability Specs

All finalized specs live in `specs/`. Each directory contains a `spec.md` with requirements and scenarios.

### Architecture

| Spec | Description |
|------|-------------|
| [full-stack-architecture](specs/full-stack-architecture/spec.md) | End-to-end system architecture reference |

### Booking

| Spec | Description |
|------|-------------|
| [booking-evidence](specs/booking-evidence/spec.md) | Evidence display for booking-stage pipeline rows |

### Online Bookings Page

| Spec | Description |
|------|-------------|
| [online-bookings-rename](specs/online-bookings-rename/spec.md) | Rename "Online Bookings" page and nav entries |

### Conversions — Pipeline

| Spec | Description |
|------|-------------|
| [conversion-candidates-view](specs/conversion-candidates-view/spec.md) | `vw_conversion_candidates` view definition |
| [conversion-channel-grouping](specs/conversion-channel-grouping/spec.md) | Channel grouping logic in the conversions view |
| [conversion-config](specs/conversion-config/spec.md) | `gads_conversion_config` table and edge function |
| [conversion-dashboard](specs/conversion-dashboard/spec.md) | Conversions dashboard page layout |
| [conversion-pipeline-ui](specs/conversion-pipeline-ui/spec.md) | Pipeline UI components and stage visuals |
| [conversion-pipeline-view](specs/conversion-pipeline-view/spec.md) | Conversion pipeline view requirements |
| [conversion-populate](specs/conversion-populate/spec.md) | Populating conversion upload rows |
| [conversion-upload](specs/conversion-upload/spec.md) | Google Ads conversion upload logic |
| [conversion-view-mode](specs/conversion-view-mode/spec.md) | View mode toggling on the conversions page |
| [per-estimate-discovery](specs/per-estimate-discovery/spec.md) | Per-estimate manual re-discovery trigger |
| [pipeline-phase-visuals](specs/pipeline-phase-visuals/spec.md) | Visual treatment of pipeline phase cells |
| [pipeline-stage-booking](specs/pipeline-stage-booking/spec.md) | Booking Lead stage criteria and display |
| [pipeline-stage-converted](specs/pipeline-stage-converted/spec.md) | Converted Lead stage criteria and display |
| [pipeline-stage-qualified](specs/pipeline-stage-qualified/spec.md) | Qualified Lead stage criteria and display |
| [pipeline-view-fix](specs/pipeline-view-fix/spec.md) | Pipeline view bug fixes |
| [phase-cell-upload](specs/phase-cell-upload/spec.md) | Per-cell upload action in the pipeline table |
| [bulk-upload-scoped](specs/bulk-upload-scoped/spec.md) | Scoped bulk upload for filtered rows |

### Conversions — Evidence & Enrichment

| Spec | Description |
|------|-------------|
| [booking-evidence](specs/booking-evidence/spec.md) | Booking stage evidence panel |
| [converted-evidence](specs/converted-evidence/spec.md) | Converted stage evidence panel |
| [qualified-evidence](specs/qualified-evidence/spec.md) | Qualified stage evidence panel |
| [conversions-qualified-enrichment](specs/conversions-qualified-enrichment/spec.md) | Enrichment data shown on qualified rows |
| [pre-discovery-stage-sections](specs/pre-discovery-stage-sections/spec.md) | Pre-discovery section grouping |

### Conversions — Filtering & Display

| Spec | Description |
|------|-------------|
| [conversions-filter-bar](specs/conversions-filter-bar/spec.md) | Filter bar controls on the conversions page |
| [conversions-filtered-totals](specs/conversions-filtered-totals/spec.md) | Totals row respecting active filters |
| [conversions-fiscal-grouping](specs/conversions-fiscal-grouping/spec.md) | Fiscal week/month grouping for conversions |
| [conversions-gclid-tag](specs/conversions-gclid-tag/spec.md) | GCLID badge display in conversion rows |
| [conversions-page-v3](specs/conversions-page-v3/spec.md) | Conversions page v3 layout and features |
| [conversions-submenu-navigation](specs/conversions-submenu-navigation/spec.md) | Sub-menu navigation under Conversions |
| [source-badges](specs/source-badges/spec.md) | Source/channel badge components |

### Conversions — Config & Reporting

| Spec | Description |
|------|-------------|
| [conversion-analytics-page](specs/conversion-analytics-page/spec.md) | Conversion analytics page panels |
| [conversion-config-page](specs/conversion-config-page/spec.md) | Conversion config editor page |
| [gads-upload-analytics](specs/gads-upload-analytics/spec.md) | Google Ads upload analytics sync |
| [upload-reconciliation-reporting](specs/upload-reconciliation-reporting/spec.md) | Upload reconciliation reporting |
| [upload-reconciliation-visuals](specs/upload-reconciliation-visuals/spec.md) | Upload reconciliation visual components |
| [upload-report-page](specs/upload-report-page/spec.md) | Upload report page |

### Attribution

| Spec | Description |
|------|-------------|
| [customer-gclid-attribution](specs/customer-gclid-attribution/spec.md) | `customer_gclids` first-touch GCLID model |
| [gads-gclid-verification](specs/gads-gclid-verification/spec.md) | GCLID verification against Google Ads |
| [lead-channel-resolver](specs/lead-channel-resolver/spec.md) | Lead channel taxonomy and resolution logic |

### Calls

| Spec | Description |
|------|-------------|
| [call-detail-panel](specs/call-detail-panel/spec.md) | Call detail expansion panel |
