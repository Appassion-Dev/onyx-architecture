# Lead Management System — Architecture

## Overview

Leads enter the system through two paths: a booking form (online) and phone calls tracked via CallRail. Both paths converge in Supabase where attribution signals are resolved into a single taxonomy channel and made available to the dashboard.

---

## Mermaid Diagram

```mermaid
flowchart TD
    subgraph ENTRY["Lead Entry"]
        A([Booking Form\nonyx-widget.js]) -->|POST /hcp-booking| B[hcp-booking\nEdge Function]
        C([Phone Call]) -->|webhook| D[callrail-webhook\nEdge Function]
        E([CallRail daily sync]) -->|cron pull| F[callrail-pull\nEdge Function]
    end

    subgraph EDGE_BOOKING["hcp-booking · write path"]
        B --> B1[createCustomer\nhcp-client.ts]
        B1 -->|HCP API| B2[(HouseCall Pro\nCRM)]
        B2 --> B3[createEstimate + scheduleEstimate\nhcp-client.ts]
        B3 --> B4[persistBooking\nsupabase-writer.ts]
        B4 --> B5{{"resolveChannel()\nchannel-resolver.ts\n90-day attribution guard"}}
        B5 -->|new customer\nor outside window| B6[use submitted\nlead_source]
        B5 -->|repeat customer\nwithin 90 days\nnon-null original| B7[preserve original\nlead_source]
    end

    subgraph DB_WRITE["Postgres · Write Tables"]
        B6 & B7 --> T1[(customers\nlead_source\ncreated_at)]
        B4 --> T2[(estimates\nlead_source\nis_booking_form)]
        B4 --> T3[(booking_tags\ngclid · utm_source\nutm_medium · hsa_src\nref)]
        B4 --> T4[(addresses)]
        B4 --> T5[(estimates_settings\nsales_employee_id)]
        D & F --> T6[(callrail_leads\nsource · campaign\ngclid · call_started_at)]
    end

    subgraph VIEW["vw_conversion_candidates · Read View"]
        T2 --> V1
        T1 --> V1
        T3 --> V2{{"form_tags LATERAL\nform_gclid\nform_utm_source\nform_utm_medium\nform_hsa_src\nform_ref"}}
        T6 --> V3{{"call_agg LATERAL\ncallrail_sources\ncallrail_campaigns\ncall_count"}}
        T5 --> V4{{"assign_agg LATERAL\nassigned_employee"}}
        V2 --> V1{{"channel CASE resolver\n1 · estimates.lead_source in taxonomy\n2 · Reserve with Google → GMB\n3 · form_gclid present → Google Ads\n4 · form_hsa_src=LocalServicesAds → GLS\n5 · form_utm_source mapped to channel\n6 · form_ref ~* google.com/localservices → GLS\n7 · callrail_sources pattern-matched\n8 · Other"}}
        V3 --> V1
        V4 --> V1
        T7[(gads_conversion_uploads\nbooking · qualified\nconverted)] --> V1
    end

    subgraph RECONCILE["vw_gads_upload_reconciliation_daily"]
        V1 -->|channel| R1{{"7-channel → 4-bucket map\nGoogle Ads · GLS · GMB\nOrganic · Direct → form\nThumbtack → thumbtack\nOther w/ calls → calls\nOther → other"}}
        R1 --> R2[(daily upload counts\nform / calls\nthumbtack / other)]
    end

    subgraph GADS["Google Ads Upload"]
        T7 --> G1[google-ads-conversion-upload\nEdge Function]
        G1 -->|Google Ads API| G2([Google Ads\nConversion Actions])
        G1 --> T7
    end

    subgraph DASHBOARD["horizon-dashboard · React"]
        V1 -->|select * · React Query| P1[ConversionsPage.tsx]
        P1 --> P2{{"classifyChannel()\nreads row.channel"}}
        P2 --> P3{{"buildHierarchy()\ngroups by CHANNEL_ORDER\nGoogle Ads · GLS · GMB\nThumbtack · Organic\nDirect · Other"}}
        P3 --> P4[Pipeline view\nweekly rollup by channel]
        P4 --> P5[Channel filter dropdown\n7 taxonomy options]
        R2 -->|React Query| P6[ConversionReportingPage.tsx\nUpload reconciliation]
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
