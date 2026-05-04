# Conversion Tracking Update — May 2026

## What We Improved

We made three meaningful fixes to how your Google Ads conversions are tracked and reported.

---

### 1. We were missing leads that came in by phone or direct entry

**Before:** Our system only counted a customer as a "qualified lead" or "converted lead" if they had previously gone through the online booking form. Customers who called in or were entered manually in HousecallPro were invisible to Google Ads — even when they were genuinely ad-attributed.

**After:** All three stages (Booking, Qualified, Converted) now detect independently. A customer who calls in can now be credited as a qualified or converted lead without needing a prior booking form submission. This means Google Ads now sees the full picture of your ad-driven business.

---

### 2. Returning customers were losing their ad attribution

**Before:** When a customer who originally came from a Google Ad came back for a second estimate, the link back to that original click was lost. The follow-up job wasn't credited to your ad spend.

**After:** We now store a permanent record linking each customer to their original Google click ID. Any estimate for that customer — first visit or return — can now be attributed back to the original ad. Historical data has been backfilled, so this applies to past customers as well.

---

### 3. The estimated job value reported to Google was inconsistent

**Before:** For "qualified lead" conversions, we were only summing *approved* estimate options. This meant we were sending $0 to Google Ads for any estimate where the customer hadn't formally approved an option yet — even if a real estimate amount had been presented.

**After:** We now use the average of all presented options as the job value. This gives Google a realistic signal of job size at the moment the lead qualifies, regardless of approval status. (For converted leads, which represent completed jobs, we still use approved amounts — that hasn't changed.)

---

## What You'll See in the Dashboard

- The **estimated job value** shown on the Conversions page now reflects the average of all options presented to the customer, not just approved ones.
- The **Qualified** stage now shows the estimate's work status (e.g., "Complete") directly on the card, so you can see at a glance what triggered the conversion.
- The visual connector lines between Booking → Qualified → Converted have been removed, since these stages are now independent events rather than a required sequence.

---

## What Didn't Change

- **Google Ads upload behavior** is unchanged — conversions without a direct click ID are still sent via enhanced conversions (email/phone matching), exactly as before.
- **Historical uploaded conversions** are untouched — we never retroactively modify data that has already been sent to Google.
- **Converted lead value** still uses approved option totals, as that represents actual committed revenue.
