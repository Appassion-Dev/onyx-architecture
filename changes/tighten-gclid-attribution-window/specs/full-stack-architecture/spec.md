## ADDED Requirements

### Requirement: Architecture spec documents both Google Ads upload time constraints
The architecture spec SHALL document both Google Ads time-window constraints that govern offline conversion upload eligibility, clearly distinguishing their reference points and noting which parts of the system enforce each:

```
                    click_through_lookback_window_days
                    (per-ConversionAction setting, default 30d, max 90d)
                    ◄──────────────────────────────────►
                                                        │
       Click ──────────────────────────────────► Conversion ────────────────────► Upload
       (GCLID born)                             (conversion_datetime)            (now)
       first_seen_at                                       ◄────────────────────►
                                                           Upload recency window
                                                           90 days (hard API limit)
```

- **Window 1 — Upload recency**: `conversion_datetime >= now() - 90 days`. Reference point: upload time. Enforced by the upload edge function (`status = 'expired'`).
- **Window 2 — Click lookback**: `first_seen_at >= conversion_datetime - click_through_lookback_window_days`. Reference point: conversion event. Enforced by the discovery SQL functions.

#### Scenario: Architecture spec accurately reflects both constraints
- **WHEN** a developer reads the architecture spec
- **THEN** they can identify which system component enforces each window, the reference point for each, and the consequence of a row that fails each window

### Requirement: Architecture spec is updated after each pipeline feature implementation
After any implementation that changes the behavior of a pipeline stage (discovery, upload, GCLID attribution, conversion action configuration), the architecture spec (`openspec/specs/full-stack-architecture/spec.md`) SHALL be updated to reflect the new behavior before the change is archived. This is a process requirement, not a code requirement.

#### Scenario: Implementation complete — arch spec is current
- **WHEN** implementation of a change is complete
- **THEN** `openspec/specs/full-stack-architecture/spec.md` accurately reflects the current system behavior before the change is moved to archive

#### Scenario: Arch spec lags implementation
- **WHEN** an architecture spec section describes behavior that was superseded by a change that was archived without updating the spec
- **THEN** the discrepancy is treated as a defect and addressed in the next change
