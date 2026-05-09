# Lead Management System — Architecture

## Overview

Leads enter the system through two paths: a booking form (online) and phone calls tracked via CallRail. Both paths converge in Supabase where attribution signals are resolved into a single taxonomy channel and made available to the dashboard.

---

## Mermaid Diagram

```mermaid
flowchart TD
    subgraph ENTRY["Lead Entry"]
        A(["Booking Form
onyx-widget.js"]) -->|POST /hcp-booking| B["hcp-booking
Edge Function"]
        C(["Phone Call"]) -->|webhook| D["callrail-webhook
Edge Function"]
        E(["CallRail daily sync"]) -->|cron pull| F["callrail-pull
Edge Function"]
    end

    subgraph EDGE_BOOKING["hcp-booking · write path"]
        B --> B1["createCustomer
hcp-client.ts"]
        B1 -->|HCP API| B2[("HouseCall Pro
CRM")]
        B2 --> B3["createEstimate + scheduleEstimate
hcp-client.ts"]
        B3 --> B4["persistBooking
supabase-writer.ts"]
        B4 --> B5{{"resolveChannel()
channel-resolver.ts
90-day attribution guard"}}
        B5 -->|"new customer
or outside window"| B6["use submitted
lead_source"]
        B5 -->|"repeat customer
within 90 days
non-null original"| B7["preserve original
lead_source"]
    end

    subgraph DB_WRITE["Postgres · Write Tables"]
        B6 & B7 --> T1[("customers
lead_source
created_at")]
        B4 --> T2[("estimates
lead_source
is_booking_form")]
        B4 --> T3[("booking_tags
gclid · utm_source
utm_medium · hsa_src
ref")]
        B4 --> T4[("addresses")]
        B4 --> T5[("estimates_settings
sales_employee_id")]
        D & F --> T6[("callrail_leads
source · campaign
gclid · call_started_at")]
    end

    subgraph VIEW["vw_conversion_candidates · Read View"]
        T2 --> V1
        T1 --> V1
        T3 --> V2{{"form_tags LATERAL
form_gclid
form_utm_source
form_utm_medium
form_hsa_src
form_ref"}}
        T6 --> V3{{"call_agg LATERAL
callrail_sources
callrail_campaigns
call_count"}}
        T5 --> V4{{"assign_agg LATERAL
assigned_employee"}}
        V2 --> V1{{"channel CASE resolver
── 8-step priority chain ──"}}
        V3 --> V1
        V4 --> V1
        T7[("gads_conversion_uploads
booking · qualified
converted")] --> V1
    end

    subgraph RECONCILE["vw_gads_upload_reconciliation_daily"]
        V1 -->|channel| R1{{"7-channel → 4-bucket map
Thumbtack → thumbtack
Google Ads · GLS · GMB
Organic · Direct → form
Other/NULL w/ calls → calls
else → other"}}
        R1 --> R2[("daily upload counts
form / calls
thumbtack / other")]
    end

    subgraph GADS["Google Ads Upload"]
        T7 --> G1["google-ads-conversion-upload
Edge Function"]
        G1 -->|Google Ads API| G2(["Google Ads
Conversion Actions"])
        G1 --> T7
    end

    subgraph DASHBOARD["horizon-dashboard · React"]
        V1 -->|"select * · React Query"| P1["ConversionsPage.tsx"]
        P1 --> P2{{"classifyChannel()
reads row.channel"}}
        P2 --> P3{{"buildHierarchy()
groups by CHANNEL_ORDER
Google Ads · GLS · GMB
Thumbtack · Organic
Direct · Other"}}
        P3 --> P4["Pipeline view
weekly rollup by channel"]
        P4 --> P5["Channel filter dropdown
7 taxonomy options"]
        R2 -->|React Query| P6["ConversionReportingPage.tsx
Upload reconciliation"]
    end
```

---

## Key Data Flows

| Signal | Written by | Read by |
|---|---|---|
| `estimates.lead_source` | `hcp-booking` via `resolveChannel()` | `vw_conversion_candidates` step 1 |
| `booking_tags.{gclid,utm_source,…}` | `hcp-booking` · `persistBooking()` | `form_tags` LATERAL in view |
| `callrail_leads.source` | `callrail-webhook` / `callrail-pull` | `call_agg` LATERAL in view |
| `vw_conversion_candidates.channel` | Computed in view | `ConversionsPage`, `vw_gads_upload_reconciliation_daily` |
| `gads_conversion_uploads.status` | `google-ads-conversion-upload` | `vw_conversion_candidates` upload stage columns |

## Attribution Guard (90-day window)

```
resolveChannel(submittedChannel, existingLeadSource, existingCreatedAt)
  │
  ├─ existingCreatedAt within 90 days AND existingLeadSource non-null?
  │     → withinWindow=true, preserveOriginal=true
  │     → write existingLeadSource to both estimates.lead_source and customers.lead_source
  │
  └─ otherwise (new customer, outside window, or null original)
        → write submittedChannel to both
```
