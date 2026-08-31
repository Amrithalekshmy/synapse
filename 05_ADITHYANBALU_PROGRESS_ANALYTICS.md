# SIH26122 — ADITHYANBALU
## Actual Progress, Variance & Schedule Update Engine

**Owner:** Adithyanbalu  
**Module:** Progress calculation and schedule impact  
**Priority:** Critical  
**Depends on:** Yazeen + Amritha  
**Feeds:** Aliadnan + Adithyagopan

### What you build
Turn verified matches into operational meaning.

> Given what actually happened, how is the project performing against the baseline?

### Inputs
From Yazeen:
```text
activity_id
planned_start
planned_finish
planned_duration
planned_quantity (if available)
```

From Amritha:
```text
activity_id
actual_start
actual_finish
match_confidence
review_status
```

### Core calculations
```text
start_variance = actual_start - planned_start
finish_variance = actual_finish - planned_finish
duration_variance = actual_duration - planned_duration
```

Example:
```text
Planned finish: Aug 20
Actual finish:  Aug 24
Finish variance: +4 days
```

### Status model
```text
Not Started
Started
In Progress
Completed
Blocked
Unknown
```

### Partial progress
This is a major SIH edge case.

If the plan says:
```text
100 m cable tray
```

and the field reports:
```text
60 m installed
```

do not mark it complete.

Store:
```text
planned_quantity = 100
actual_quantity = 60
progress_percent = 60
```

### Event timeline
An activity may receive:
```text
START     Aug 10
PROGRESS  Aug 11
PROGRESS  Aug 12
COMPLETE  Aug 15
```

Derive the current state from the verified event history.

### Confidence gating
Do not use a low-confidence/unreviewed match as if it were fact.

```text
verified        → usable
pending_review  → provisional
rejected        → unusable
```

### Risk signals — Two Layers

#### Layer 1 — Rule-based (minimum version, achievable Week 1)
- started late
- finishing late
- progress below expected
- repeatedly delayed discipline
- blocked activity

#### Layer 2 — Historical risk scoring (strong version, using Adithyagopan's knowledge base)

This is SYNAPSE's forward-looking intelligence — no existing EPC tool offers this.

```text
Current activity: PIP-238 — Erect Line 24-XX
Planned duration: 5 days

Query to knowledge base:
"All piping erection activities at Oil India projects"

Historical result:
  Avg actual duration: 7.2 days
  Delay frequency: 68%
  Common delay causes:
    - Crane availability (42%)
    - Material delay (31%)
    - Permit issues (18%)

SYNAPSE risk alert:
{
  "activity_id": "PIP-238",
  "risk_level": "HIGH",
  "delay_probability": 0.68,
  "suggested_buffer_days": 2,
  "historical_basis": "23 similar activities in knowledge base"
}
```

The planner sees this risk alert **before** the activity is due to start, not after it is already late.

Do not claim ML prediction unless it is actually trained and evaluated. For the demo, rule-based + historical lookup is sufficient and honest.

### Multi-Source Conflict Detection

This is a feature no existing EPC tool handles.

When the same activity is reported with different statuses from multiple sources on the same day:

```text
Source A (DPR, 8 AM):         IN_PROGRESS
Source B (Excel, 5 PM):       COMPLETED
Source C (Supervisor, 6 PM):  BLOCKED
```

SYNAPSE flags this as a conflict rather than accepting the latest update:

```text
CONFLICT DETECTED
Activity: PIP-238
Date: 2026-08-30

Status reports received:
  DPR-30 (08:00) → IN_PROGRESS
  EXCEL-30 (17:00) → COMPLETED
  SUPERVISOR (18:00) → BLOCKED

Action required: Planner must resolve before schedule update.
```

The resolution is stored in the audit trail with the source that was trusted.

This prevents silent schedule corruption from inconsistent multi-source reporting.

### Minimum version
- [ ] actual start/finish
- [ ] planned vs actual variance
- [ ] status derivation
- [ ] partial quantity progress
- [ ] confidence/review gating
- [ ] API output

### Strong version
- [ ] event timeline
- [ ] discipline summaries
- [ ] early-warning indicators
- [ ] project KPI aggregation
- [ ] historical delay risk score per activity
- [ ] multi-source conflict detection and flagging
- [ ] productivity metrics (actual vs planned quantity per unit time)

### Development order
1. Date arithmetic.
2. Status state machine.
3. Partial quantity progress.
4. Confidence/review gating.
5. Project aggregation.
6. Connect to frontend.
