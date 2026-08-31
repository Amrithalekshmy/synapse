# SIH26122 — ALIADNAN
## Frontend, Reviewer Queue, Audit Trail & User Experience

**Owner:** Aliadnan  
**Module:** User-facing application  
**Priority:** Critical  
**Depends on:** Can start with mocked APIs; final integration uses all backend modules

### What you build
Make the pipeline understandable and usable.

> Can a planner/supervisor see what the system understood, trust it, correct it, and see the schedule impact?

### Main screens

#### 0. Agentic Supervisor Input (NEW — SYNAPSE differentiator)

This screen is for supervisors in the field, not planners.

```text
┌─────────────────────────────────────────────┐
│ SYNAPSE — Report What Happened               │
│                                              │
│ > "Erection completed today."               │
│                                              │
│ SYNAPSE: Which activity?                     │
│   (a) Line 24-XX — Pipe Rack A              │
│   (b) Line 25-XX — Pipe Rack A              │
│                                              │
│ > "a"                                        │
│                                              │
│ ✓ Linked to PIP-238. Schedule updated.      │
└─────────────────────────────────────────────┘
```

This is the agentic clarification interface. It resolves ambiguity at input time.

#### 1. Upload / Input (Planner / Admin)
Support:
- daily report upload (PDF, text)
- spreadsheet upload (Excel/CSV)
- text paste
- optional voice input (strong version)

Show processing progress:
```text
Processing...
7 events detected
2 conflicts detected
```

#### 2. Extracted Events
Display:
- original text
- extracted description
- discipline
- date
- status
- extraction confidence

#### 3. Matching Review Queue
This is a core screen.

```text
FIELD EVENT
"Spool erection completed for Line 24"

TOP MATCH
PIP-L6-024 — Erect Line 24
Confidence: 94%

[Approve] [Reject] [Choose another]
```

For ambiguous matches:
```text
Candidate 1 — 58%
Candidate 2 — 55%
Candidate 3 — 43%

Needs planner review
```

#### 4. Schedule / Gantt
Show:
```text
Activity | Planned | Actual | Variance
```

A clean prototype Gantt is enough.

#### 5. Audit Trail
```text
Source
  ↓
Extracted event
  ↓
Match
  ↓
Reviewer decision
  ↓
Schedule update
```

#### 6. Conflict Resolution (NEW — SYNAPSE differentiator)

```text
┌─────────────────────────────────────────────┐
│ ⚠ CONFLICT DETECTED                          │
│                                              │
│ Activity: PIP-238 — Erect Line 24-XX         │
│ Date: 30 Aug 2026                            │
│                                              │
│ DPR (08:00)       → IN PROGRESS             │
│ Excel (17:00)     → COMPLETED               │
│ Supervisor (18:00)→ BLOCKED                 │
│                                              │
│ Which source do you trust?                   │
│ [DPR] [Excel] [Supervisor] [Investigate]     │
└─────────────────────────────────────────────┘
```

The planner's decision is recorded in the audit trail.

#### 7. Risk Dashboard (NEW — SYNAPSE differentiator)

```text
┌─────────────────────────────────────────────┐
│ RISK INTELLIGENCE                            │
│                                              │
│ HIGH RISK                                    │
│ PIP-238 — Erect Line 24-XX                  │
│ Historical delay rate: 68%                   │
│ Suggested buffer: 2 days                     │
│ Common cause: crane availability             │
│                                              │
│ MEDIUM RISK                                  │
│ ELE-102 — Cable Tray Area B                 │
│ Historical delay rate: 41%                   │
│                                              │
│ [View historical evidence]                   │
└─────────────────────────────────────────────┘
```

#### 8. Historical Knowledge
Show natural-language search and supporting records.

### UX principle
Never hide uncertainty.

Bad:
```text
Matched successfully.
```

Better:
```text
Matched to PIP-L6-024
Confidence: 94%
Verified by planner
```

### API separation
Do not put AI/extraction logic in React.

Consume backend endpoints such as:
```text
POST /events/extract
POST /matches
POST /matches/{id}/review
GET  /schedule
GET  /progress
GET  /history/search
```

Names may change; ownership boundaries should not.

### Demo flow (SYNAPSE full story)
```text
1. Supervisor types ambiguous update → agentic agent asks one question → confirmed event extracted
2. Upload DPR (planner) → 7 events detected, 2 conflicts detected
3. Conflict alert shown → planner resolves
4. Match candidates appear for each event
5. High-confidence → AUTO-LINKED (schedule updates immediately)
6. Low-confidence → enters review queue with evidence ticks
7. User approves/corrects → active learning stores feedback
8. Actual date updates → variance appears → Gantt changes
9. Risk Dashboard shows PIP-238 at HIGH risk based on historical patterns
10. Historical record becomes searchable for future projects
```

This is the complete DATA → INTELLIGENCE → DECISION → ACTION → LEARNING story.

### Minimum version
- [ ] upload
- [ ] event table
- [ ] review queue
- [ ] schedule variance
- [ ] audit trail

### Strong version
- [ ] Gantt
- [ ] confidence badges
- [ ] source preview
- [ ] voice input
- [ ] history search
- [ ] polished demo flow

### Design goal
Do not build a generic dashboard. Make this story visually obvious:

```text
SUPERVISOR SPEAKS/TYPES
       ↓
SYNAPSE CLARIFIES (if needed)
       ↓
EVENT EXTRACTED
       ↓
CONFLICT CHECKED (multi-source)
       ↓
HYBRID MATCH
       ↓
AUTO-LINK or HUMAN REVIEW
       ↓
SYSTEM LEARNS (active feedback)
       ↓
SCHEDULE UPDATED + AUDIT TRAIL
       ↓
RISK INTELLIGENCE (historical)
       ↓
INSTITUTIONAL MEMORY
```

The system name **SYNAPSE** should appear in the top-left of every screen. The name should feel like a product, not a student project.
