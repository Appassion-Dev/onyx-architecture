## Why

The conversions pipeline table shows three stages (Booking, Qualified, Converted) but the expanded detail view only displays flat metadata (status, GCLID, date). There is no way to see the *evidence* behind each stage — form submission tags proving the ad click, estimate options proving the qualified value, or the job record proving the conversion. Users must cross-reference multiple systems to validate a single conversion.

## What Changes

- **Booking Lead detail** gains two sub-sections:
  - Form Submission table — shows all `booking_tags` (gclid, keyword, match type, campaign, network) proving the booking signal's validity
  - Calls table — moved from bottom of expanded area into Booking Lead section; shows "No calls recorded" when `call_count = 0`
- **Qualified Lead detail** gains an Estimate Options table showing all options with amount and approval status badges
- **Converted Lead detail** gains a Job section showing job status, total, and outstanding balance — displayed even when `converted_status` is null; shows "No job created yet" when no job exists
- GCLID is removed from the flat metadata line (it now lives inside the Form Submission table where it belongs)

## Capabilities

### New Capabilities
- `booking-evidence`: Form submission tags and calls display inside the Booking Lead stage detail
- `qualified-evidence`: Estimate options table with approval status inside the Qualified Lead stage detail
- `converted-evidence`: Job record display with status and balance inside the Converted Lead stage detail

### Modified Capabilities

## Impact

- `horizon-dashboard/src/components/pages/ConversionsPage.tsx` — three new sub-components + updated expanded row layout
- Data fetched from `booking_tags`, `estimate_options`, and `jobs` tables via Supabase client (lazy on expand)
- No SQL migration needed — all tables already exist
