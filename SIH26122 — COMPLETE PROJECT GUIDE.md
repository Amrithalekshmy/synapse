# SIH26122 — COMPLETE PROJECT GUIDE

## SYNAPSE — Synchronized NLP Activity-to-Plan Scheduling Engine

### Intelligent Planning-to-Execution Bridge for Infrastructure Project Management

**System Name:** SYNAPSE  
**Organization:** Oil India Limited  
**Theme:** Smart Automation  
**Type:** Software  
**Team Size:** 6  
**Project Difficulty Target:** Medium–Hard

---

> SYNAPSE is not a dashboard. It is a trustworthy data-linking layer that converts messy field execution language into verified, auditable schedule updates — with active learning, agentic clarification, and historical risk intelligence built in.

---

# TABLE OF CONTENTS

1. Problem Statement
2. Problem in Simple Words
3. Why This Problem Exists
4. What Exactly We Are Building
5. Complete System Architecture
6. End-to-End Data Flow
7. The Most Important Technical Problem
8. Semantic Matching
9. Why Normal Search Is Not Enough
10. Hybrid Matching
11. Confidence Scoring
12. Human-in-the-Loop Review
13. Granularity Mismatch
14. Event Extraction
15. Heterogeneous Data Ingestion
16. Schedule / WBS Representation
17. Actual Progress Updating
18. Variance Calculation
19. Audit Trail
20. Institutional Memory
21. AI / LLM Role
22. Voice / Time Agent
23. Recommended Technology Stack
24. Database Design
25. API Architecture
26. Synthetic Dataset
27. Evaluation Strategy
28. Team Architecture
29. Development Dependencies
30. Final MVP and SIH Demo

---

# 0. WHAT EXISTS TODAY AND WHY IT FAILS — THE COMPETITIVE GAP

## Current State at Oil India Limited and Similar EPC Projects

Infrastructure projects use **Primavera P6** or **MS Project** for scheduling.

These tools are powerful for planning.

They are useless for capturing what actually happened on site.

### What planners do today

```text
Site supervisor writes:
"Line 24 spool erection done."

        ↓

Planner opens Primavera.

        ↓

Planner reads report.

        ↓

Planner searches for "Line 24" manually in 500+ activities.

        ↓

Planner finds PIP-238.

        ↓

Planner manually types the actual finish date.

        ↓

This happens for every activity, every day, across every discipline.
```

### The quantified pain

```text
A typical EPC project at scale contains:
500–5000 planned activities at L5/L6 level.

A planner manually reconciles:
50–200 field reports per day across all disciplines.

Time spent:
3–5 hours per day per planner on reconciliation alone.

Schedule update lag:
24–72 hours between activity completion and schedule update.

Error rate:
Manual matching introduces ~10–15% mis-linking in large projects
(wrong activity updated, delayed activities not flagged).
```

### Why existing tools fail

| Tool | What it claims | Why it fails |
|---|---|---|
| Primavera P6 | Schedule management | Requires exact activity IDs; cannot read free-text reports |
| MS Project | Schedule management | No NLP capability; purely manual data entry |
| Generic BI tools (Power BI, Tableau) | Dashboards | Can display data; cannot extract or link field information |
| Generic OCR tools | Document reading | Extract text but cannot understand domain meaning or link to schedule |
| Basic chatbots | Q&A | Generic; no schedule context; no confidence-aware routing |

**The gap:**

> No existing tool can automatically read a supervisor's message like *"Line 24 spool erection done"* and reliably link it to PIP-238 in the project schedule — with a confidence score, evidence, human review for ambiguous cases, and an audit trail. SYNAPSE is built to close exactly this gap.

### What SYNAPSE does differently

```text
EXISTING TOOLS:
Report arrives → Planner reads → Manual search → Manual entry → Schedule updates (if remembered)

SYNAPSE:
Report arrives → AI extracts event → Hybrid matcher links to activity
→ Confidence-gated: auto-link OR human review
→ Schedule updates automatically
→ Reviewer decisions improve future matching (active learning)
→ Historical patterns warn about delay risk
```

---

# 1. PROBLEM STATEMENT

Infrastructure projects such as oil & gas, construction, EPC and engineering projects are planned using detailed project schedules.

These schedules may contain thousands of activities organized into multiple WBS levels:

```text
L1
 ↓
L2
 ↓
L3
 ↓
L4
 ↓
L5
 ↓
L6
```

At the L5/L6 level, the activities are detailed enough to represent executable work.

For example:

```text
Activity ID: PIP-238

Activity:
Erect Line 24-XX

Discipline:
Piping

Location:
Unit 4

Planned Start:
16 Aug

Planned Finish:
20 Aug
```

However, actual execution at the construction site does not necessarily arrive in this structured form.

It may arrive as:

```text
"Spool erection for line 24 completed yesterday."
```

or:

```text
"Line 24 spool erection done by piping crew."
```

or:

```text
"24-XX spool erect. completed."
```

or as a spreadsheet row:

```text
Date | Discipline | Description | Status
28/08 | Piping | Spool erection Line 24 | Complete
```

These different representations may all describe the same physical activity.

The central problem is therefore:

> **How can we automatically convert heterogeneous field execution information into structured actual-progress events and reliably link those events to the correct L5/L6 planned activity?**

---

# 2. THE PROBLEM IN SIMPLE WORDS

Imagine a construction manager has a project plan containing:

```text
PIP-238
Erect Line 24-XX
```

The supervisor sends:

> "Line 24 spool erection completed."

The system needs to understand:

```text
Supervisor statement
        ↓
What happened?
        ↓
Spool erection completed
        ↓
Which planned activity?
        ↓
PIP-238
        ↓
How confident are we?
        ↓
93%
        ↓
Is automatic update safe?
        ↓
YES
        ↓
Update actual completion
```

That is the project.

Everything else supports this pipeline.

---

# 3. WHY THIS PROBLEM EXISTS

The schedule and actual execution live in different worlds.

## Planned World

```text
Primavera / MS Project

Activity IDs
WBS
Planned dates
Dependencies
Disciplines
Locations
```

## Execution World

```text
Daily reports
Site diaries
Spreadsheets
Supervisor messages
Verbal updates
Scanned documents
```

These systems are disconnected.

Therefore:

```text
PLAN
  ↓
Detailed activity

             X

SITE
  ↓
Messy description
```

Someone has to manually reconcile them.

---

# 4. CONSEQUENCES

Because this reconciliation is manual:

### 4.1 Progress becomes delayed

The actual project may already be ahead or behind while the schedule still shows old information.

### 4.2 Manual work increases

Planners have to read multiple reports and identify corresponding schedule activities.

### 4.3 Errors occur

A report can be linked to the wrong activity.

### 4.4 Analytics become unreliable

If actual dates are wrong:

```text
Wrong actual dates
       ↓
Wrong variance
       ↓
Wrong delay analysis
       ↓
Wrong forecasting
```

### 4.5 Historical knowledge is lost

After the project closes, information about:

- actual duration;
- delays;
- bottlenecks;
- productivity;
- recurring issues

often remains scattered across documents and individual experience.

---

# 5. WHAT EXACTLY ARE WE BUILDING?

We are building an:

> **AI-powered planning-to-execution bridge.**

The system has seven major stages:

```text
1. INGEST
      ↓
2. EXTRACT
      ↓
3. NORMALIZE
      ↓
4. MATCH
      ↓
5. REVIEW
      ↓
6. UPDATE
      ↓
7. REMEMBER
```

In detail:

```text
Site Reports
Spreadsheets
PDFs
Supervisor Input
       │
       ▼
┌───────────────────────┐
│ INPUT INGESTION       │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ EVENT EXTRACTION      │
└───────────┬───────────┘
            │
            ▼
      ExecutionEvent
            │
            ▼
┌───────────────────────┐
│ SEMANTIC MATCHING     │
└───────────┬───────────┘
            │
            ▼
      MatchResult
            │
            ▼
┌───────────────────────┐
│ CONFIDENCE + REVIEW   │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ PROGRESS ENGINE       │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ ANALYTICS + MEMORY    │
└───────────────────────┘
```

---

# 5.5 THREE DIFFERENTIATORS THAT MAKE SYNAPSE DIFFERENT FROM ANY EXISTING TOOL

## Differentiator 1 — Active Learning Feedback Loop

Most AI matching systems are static.

They match, and they never improve.

SYNAPSE improves with every human decision.

```text
Event: "Line 24 spool erection done."

Matcher: PIP-238 @ 76% → REVIEW QUEUE

Reviewer: Approves PIP-238

        ↓

Feedback engine stores:
{
  event_embedding: [...],
  approved_activity: "PIP-238",
  reviewer: "planner_01",
  timestamp: "2026-08-30"
}

        ↓

Future matching:
Similar event arrives → matcher now assigns PIP-238 higher confidence
based on previous confirmed links.
```

This is not a chatbot getting smarter over time in a vague way.

This is a concrete engineering decision:

> Planner corrections become training signal for the matching model.

The more the system is used, the fewer events go to review.

The false-match rate decreases over time.

**This is SYNAPSE's strongest technical differentiator.**

---

## Differentiator 2 — Agentic Clarification Loop (First-Class Feature, Not Optional)

When a report is ambiguous, existing tools silently fail or mislink.

SYNAPSE uses an agentic approach:

```text
Supervisor: "Erection completed today."

        ↓

SYNAPSE Agent:
"I found 3 erection activities in your area. Which line?
  (a) Line 24-XX
  (b) Line 25-XX
  (c) Line 26-XX"

        ↓

Supervisor: "a"

        ↓

ExecutionEvent with confirmed asset: "Line 24-XX"
Confidence: HIGH
Auto-linked → PIP-238
```

This is Agentic AI as defined by SIH 2026:

> The system uses context, asks clarifying questions, and performs the task — rather than returning a low-confidence result and forcing the planner to intervene later.

The clarification happens **at the point of data entry** (supervisor message), not at the planner's review queue hours later.

This reduces review queue load and improves real-time schedule accuracy.

---

## Differentiator 3 — Historical Delay Risk Intelligence

After projects close, SYNAPSE retains execution history.

This history powers **forward-looking risk alerts** on current projects:

```text
Current project:
PIP-238 — Erect Line 24-XX
Planned duration: 5 days

Historical knowledge base:
Similar piping erection activities at Oil India projects:
  Avg actual duration: 7.2 days
  Delay frequency: 68%
  Common causes: material availability, crane availability

        ↓

SYNAPSE flags:
"Risk: This activity historically takes 44% longer than planned.
Similar activities were delayed in 68% of past cases.
Suggested buffer: 2–3 days."
```

This is not generic project management advice.

It is **domain-specific risk intelligence derived from verified execution history** from the same organization (Oil India Limited).

No existing EPC tool offers this combination of semantic linking + organizational memory + forward risk scoring.

---

# 6. COMPLETE SYSTEM ARCHITECTURE

```text
                  PROJECT SCHEDULE
                         │
             ┌───────────┴───────────┐
             │                       │
        Primavera                MS Project
             │                       │
             └───────────┬───────────┘
                         │
                         ▼
                 Schedule Parser
                         │
                         ▼
                ScheduleActivity[]
                         │
                         │
                         ▼
                ┌─────────────────┐
                │                 │
                │ MATCHING ENGINE │
                │                 │
                └─────────────────┘
                         ▲
                         │
                  ExecutionEvent
                         ▲
                         │
        ┌────────────────┴─────────────────┐
        │                                  │
        ▼                                  ▼
 Daily Reports                       Supervisor
 Spreadsheets                        Time Agent
 Site Diaries                        Voice
 PDFs                                Text
        │                                  │
        └────────────────┬─────────────────┘
                         │
                         ▼
                  Input Ingestion
                         │
                         ▼
                   Event Extraction
                         │
                         ▼
                  ExecutionEvent
                         │
                         ▼
                  Matching Engine
                         │
                         ▼
                    Confidence
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
          Auto-link              Review
              │                     │
              └──────────┬──────────┘
                         │
                         ▼
                   Approved Event
                         │
                         ▼
                  Progress Engine
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
        Live Analytics         Project Memory
             │                       │
             └───────────┬───────────┘
                         ▼
                    Frontend
```

---

# 7. THE MOST IMPORTANT TECHNICAL PROBLEM

The central intelligence is:

# Execution → Planned Activity Matching

Example:

### Planned Activity

```text
PIP-238
Erect Line 24-XX
Piping
Unit 4
```

### Execution Report

```text
Piping crew completed spool erection
for Line 24 yesterday.
```

The words are not identical.

Yet the meanings are related.

The system needs to understand:

```text
spool erection
        ≈
erect

Line 24
        ≈
24-XX

Piping
        =
Piping

Unit 4
        =
Unit 4
```

Therefore:

```text
PIP-238
Confidence = 93%
```

This is the core technical contribution.

---

# 8. WHY EXACT STRING MATCHING FAILS

Suppose the planned activity is:

```text
Erect Line 24-XX
```

The report says:

```text
Spool erection for line twenty-four completed.
```

String matching sees:

```text
Erect Line 24-XX

vs

Spool erection for line twenty-four completed
```

Very few exact characters match.

But a human understands the relationship immediately.

This is why semantic representation is useful.

---

# 9. BASELINE APPROACHES

We should not jump directly to an advanced AI model.

We need baselines.

## Baseline 1 — Exact Matching

Normalize:

```text
lowercase
remove punctuation
standardize whitespace
```

Then compare.

---

## Baseline 2 — Fuzzy Matching

Useful for:

- spelling differences;
- word ordering;
- small textual variations.

Example:

```text
Erect Line 24-XX

Erect Line 24 XX
```

These should be recognized as similar.

---

## Baseline 3 — Embedding Matching

Convert text into vectors.

For example:

```text
"Erect Line 24-XX"
        ↓
[0.13, -0.27, 0.51, ...]
```

and:

```text
"Spool erection completed for Line 24"
        ↓
[0.12, -0.25, 0.49, ...]
```

Then calculate similarity.

---

# 10. SEMANTIC MATCHING

Recommended approach:

```text
Schedule activities
       ↓
Embedding model
       ↓
Vector database
```

When an event arrives:

```text
Execution event
       ↓
Embedding
       ↓
Vector search
       ↓
Top-K candidates
```

For example:

```text
Input:
"Spool erection completed for Line 24"

Top candidates:

PIP-238 → 0.94
PIP-241 → 0.62
PIP-245 → 0.48
```

---

# 11. HYBRID MATCHING

Embedding similarity alone is not enough.

We should combine:

```text
Semantic similarity
+
Identifier matching
+
Discipline matching
+
Location matching
+
WBS context
+
Temporal context
+
Dependency context
```

Conceptually:

```text
Final Score =
    semantic evidence
  + identifier evidence
  + discipline evidence
  + location evidence
  + WBS evidence
  + temporal evidence
  + dependency evidence
```

The actual weights must be validated experimentally.

---

# 12. IDENTIFIERS ARE VERY IMPORTANT

Suppose two activities are:

```text
PIP-238
Erect Line 24-XX

PIP-239
Erect Line 25-XX
```

Report:

> "Line 24 erection completed."

Semantic similarity may find both activities similar.

But the identifier:

```text
24
```

strongly supports:

```text
PIP-238
```

Therefore the matching system should extract and use identifiers whenever available.

---

# 13. CONTEXTUAL MATCHING

Consider:

```text
Report:
Piping work completed in Unit 4.
```

Possible activities:

```text
PIP-101
Piping Unit 4

PIP-102
Piping Unit 5

PIP-103
Piping Unit 4
```

Location can eliminate irrelevant candidates.

Similarly:

```text
discipline = piping
```

can eliminate:

```text
electrical
civil
instrumentation
```

---

# 14. CONFIDENCE SCORING

Every match should produce:

```text
Activity:
PIP-238

Confidence:
93%
```

But confidence must have an operational meaning.

Recommended structure:

```text
HIGH
   ↓
Automatic update

MEDIUM
   ↓
Human review

LOW
   ↓
Unmatched
```

Example:

```text
≥ 90%
Auto-link

70–90%
Review

< 70%
Unmatched
```

These are only starting points.

The final thresholds should come from validation.

---

# 15. WHY HUMAN REVIEW IS CORE

Suppose:

```text
"Pipe work completed in Unit 4."
```

The model produces:

```text
PIP-101 → 76%
PIP-102 → 74%
PIP-103 → 72%
```

Automatically choosing PIP-101 could corrupt the schedule.

Therefore:

```text
Ambiguous AI
     ↓
Human reviewer
     ↓
Approve / Reject / Create new
```

This is not a weakness.

It is a safety mechanism.

---

# 16. REVIEW QUEUE

Example UI:

```text
┌─────────────────────────────────────────────┐
│ FIELD EVENT                                 │
│                                             │
│ "Pipe work completed in Unit 4."            │
│                                             │
├─────────────────────────────────────────────┤
│ CANDIDATES                                  │
│                                             │
│ PIP-101  Pipe Erection Unit 4      78%      │
│ PIP-102  Pipe Welding Unit 4       75%      │
│ PIP-103  Valve Installation Unit 4 69%     │
│                                             │
│ [APPROVE] [REJECT] [UNMATCHED]              │
└─────────────────────────────────────────────┘
```

Also show evidence:

```text
✓ Discipline match
✓ Location match
△ Semantic match
✗ Asset identifier missing
```

---

# 17. GRANULARITY MISMATCH

This is one of the hardest parts of the problem.

Suppose the planned schedule has:

```text
PIP-200

Erect Line 24-XX
```

But the field reports:

```text
Spool 001 erected
Spool 002 erected
Spool 003 erected
Spool 004 pending
```

We cannot blindly say:

```text
PIP-200 = 100%
```

Instead:

```text
PIP-200
│
├── Spool 001 → Complete
├── Spool 002 → Complete
├── Spool 003 → Complete
└── Spool 004 → Pending
```

If we know the denominator:

```text
3 / 4 = 75%
```

Otherwise we should preserve the evidence without inventing a percentage.

---

# 18. EVENT EXTRACTION

Before matching, we need to determine what actually happened.

Input:

> "Piping team completed spool erection for Line 24-XX yesterday."

Output:

```json
{
  "event_id": "EVT-001",
  "description": "spool erection for Line 24-XX",
  "discipline": "piping",
  "asset": "24-XX",
  "location": null,
  "start_time": null,
  "end_time": "2026-08-30",
  "status": "completed",
  "quantity": null,
  "source": "DPR-30-AUG"
}
```

The extraction model should not invent missing information.

---

# 19. MULTIPLE EVENTS

Input:

> "Line 24 erection completed and Line 25 welding started."

Output:

```text
EVENT 1
Line 24 erection
Completed

EVENT 2
Line 25 welding
Started
```

This is important because real daily reports may contain many activities in one paragraph.

---

# 20. RELATIVE DATES

Reports may say:

```text
today
yesterday
last shift
Monday
this morning
```

The report timestamp must be supplied as context.

Example:

```text
Report date:
31 Aug 2026

"yesterday"
       ↓
30 Aug 2026
```

---

# 21. HETEROGENEOUS INPUT

The system should accept at least 2–3 different formats.

Recommended MVP:

### Input 1

Free-text report.

### Input 2

Excel/CSV discipline report.

### Input 3

PDF/text document.

OCR for scanned documents is optional.

The SIH statement explicitly says production-grade OCR/ASR is not required for the prototype.

---

# 22. SCHEDULE REPRESENTATION

Every planned activity should become a standardized object.

Example:

```json
{
  "activity_id": "PIP-238",
  "activity_name": "Erect Line 24-XX",
  "wbs_id": "PIP-AREA-A",
  "level": "L6",
  "discipline": "piping",
  "location": "Unit-4",
  "planned_start": "2026-08-16",
  "planned_finish": "2026-08-20",
  "predecessors": [],
  "successors": ["PIP-239"]
}
```

---

# 23. WBS HIERARCHY

Preserve the hierarchy.

Example:

```text
Project
│
└── Construction
    │
    └── Piping
        │
        └── Unit 4
            │
            └── Pipe Rack
                │
                └── Erect Line 24-XX
```

WBS context can help semantic matching.

---

# 24. ACTUAL PROGRESS UPDATE

After a match is approved:

```text
ExecutionEvent
       ↓
Matched Activity
       ↓
Progress Engine
       ↓
Actual dates
       ↓
Variance
```

Example:

```text
Planned:
16 Aug → 20 Aug

Actual:
18 Aug → 23 Aug
```

Therefore:

```text
Start variance  = +2 days
Finish variance = +3 days
```

---

# 25. PROGRESS STATES

Recommended:

```text
NOT_STARTED
IN_PROGRESS
COMPLETED
DELAYED
AT_RISK
REVIEW
UNMATCHED
```

---

# 26. PARTIAL PROGRESS

If the report says:

> "3 of 4 spools completed."

Then:

```text
Progress = 75%
```

If the report only says:

> "Several spools completed."

Do not invent:

```text
75%
```

Instead store:

```text
Partial progress evidence
```

and let the planner review.

---

# 27. AUDIT TRAIL

Every automated decision should be traceable.

Store:

```text
Original report
       ↓
Extracted event
       ↓
Candidate activities
       ↓
Scores
       ↓
AI decision
       ↓
Human decision
       ↓
Final schedule update
```

Useful fields:

```text
source_id
event_id
model_version
matching_version
timestamp
confidence
candidate_list
reviewer
review_action
```

---

# 28. INSTITUTIONAL MEMORY

This is the long-term value of the system.

After project completion, we retain:

```text
Activity type
Discipline
Location
Planned duration
Actual duration
Variance
Delay cause
Productivity
Evidence
```

Future projects can use this historical information.

Example:

> Similar piping erection activities historically took 6–8 days.

The system can eventually use this information for:

- planning;
- benchmarking;
- risk detection;
- forecasting;
- productivity analysis.

---

# 28.5 MULTI-SOURCE CONFLICT DETECTION

This is a feature no existing EPC tool addresses.

Real projects receive the same activity update from multiple sources on the same day:

```text
Daily report (8 AM):
"Line 24 erection in progress."

Excel sheet (5 PM):
"Line 24 erection — DONE"

Supervisor message (6 PM):
"Line 24 still not finished, pending inspection."
```

Three sources, three different statuses, for the same activity.

A naive system accepts the latest update.

SYNAPSE detects the conflict:

```text
CONFLICT DETECTED
Activity: PIP-238

Source 1 (DPR-30):       IN_PROGRESS
Source 2 (EXCEL-30):     COMPLETED
Source 3 (SUPERVISOR):   BLOCKED

Flagged for planner review.
```

The planner resolves the conflict.

The resolution is stored in the audit trail.

This prevents schedule corruption from inconsistent multi-source reporting — a problem Oil India Limited would immediately recognize.

---

# 29. AI / LLM ROLE

We should not say:

> "Everything is done by an LLM."

That is technically weak.

Instead, SYNAPSE uses five distinct intelligence layers:

### Layer 1 — LLM (Extraction)

Used for:

```text
Messy text
    ↓
Structured event (discipline, asset, action, date, status)
```

### Layer 2 — Embedding Model (Retrieval)

Used for:

```text
Semantic activity matching
→ Top-K candidate retrieval from vector database
```

### Layer 3 — Hybrid Scorer (Ranking)

Used for:

```text
Semantic score
+ Identifier match
+ Discipline match
+ Location match
+ WBS context
+ Temporal fit
→ Final confidence score
```

### Layer 4 — Agentic Clarification (Dialogue)

Used for:

```text
Low-information events
→ Agent asks clarifying questions
→ Supervisor confirms
→ High-confidence event submitted
```

This is SYNAPSE's Agentic AI layer.

### Layer 5 — Active Learning (Improvement)

Used for:

```text
Reviewer decisions (approve/reject/reroute)
→ Feedback store
→ Future match weighting improved
→ Confidence thresholds recalibrated
```

### Layer 6 — Rules / Deterministic Logic (Safety)

Used for:

```text
Identifiers
Date arithmetic
Variance calculation
Conflict detection
Threshold enforcement
Audit trail
```

### Layer 7 — Human

Used for:

```text
Medium-confidence matches
Multi-source conflicts
New/unplanned activities
Critical corrections
```

This seven-layer architecture is the correct answer to "Is this just another AI chatbot?"

It is not. Each layer has a specific, defensible responsibility.

SYNAPSE's technical differentiation is:

> Layers 4 and 5 (Agentic Clarification + Active Learning) are what no existing EPC tool offers.

---

# 30. TIME AGENT

A supervisor should not need to fill a complicated form.

Example:

Supervisor:

> "Line twenty-four erection started this morning."

Agent:

> "I found a piping erection activity for Line 24-XX. Should I record the start time as today?"

Supervisor:

> "Yes."

System:

```text
ExecutionEvent
↓
Match
↓
Confidence
↓
Update
```

Voice can be added later.

The conversational workflow itself is more important than voice.

---

# 31. VOICE

Possible architecture:

```text
Supervisor Speech
       ↓
Speech-to-Text
       ↓
Time Agent
       ↓
Structured Event
       ↓
Matcher
```

However:

> **Do not make voice the foundation of the project.**

If voice fails during the demo, the core system should still work through text.

---

# 32. RECOMMENDED TECHNOLOGY STACK

## Backend

```text
Python
FastAPI
Pydantic
```

## AI

```text
LLM
Sentence Transformers
```

## Vector Search

```text
PostgreSQL
pgvector
```

## Data Processing

```text
pandas
openpyxl
PDF parser
```

## Frontend

```text
React
```

## Charts

Use a suitable chart/Gantt library.

## Voice

Optional:

```text
Whisper / equivalent STT
```

---

# 33. DATABASE DESIGN

Core tables:

```text
projects
schedule_activities
wbs_nodes
execution_events
match_results
progress_updates
review_actions
source_documents
historical_records
```

Relationships:

```text
Project
  │
  ├── ScheduleActivity
  │
  └── SourceDocument
          │
          └── ExecutionEvent
                  │
                  └── MatchResult
                          │
                          └── ProgressUpdate
```

---

# 34. API ARCHITECTURE

Potential endpoints:

```text
POST /schedule/import

POST /reports/upload

POST /events/extract

POST /matches/run

GET /matches/review

POST /matches/{id}/approve

POST /matches/{id}/reject

GET /activities/{id}

GET /analytics/progress

GET /analytics/variance

GET /history/search
```

Do not overbuild the API.

---

# 35. SYNTHETIC DATA

Because real Oil India project data will not be provided for normal development:

> We create a synthetic dataset with realistic structure.

Example:

```text
500 Schedule Activities
1000 Execution Events
```

Across:

```text
Civil
Piping
Electrical
Instrumentation
```

---

# 36. DATA DIFFICULTY LEVELS

Our dataset should contain:

## Easy

```text
Erect Line 24-XX
```

## Paraphrase

```text
Spool erection completed for Line 24.
```

## Abbreviation

```text
24XX spool erect done.
```

## Missing identifier

```text
Piping erection completed in Unit 4.
```

## Hard negative

Two activities with nearly identical descriptions.

## Granularity mismatch

Multiple spool reports → one planned activity.

---

# 37. EVALUATION

We should compare:

```text
Exact Matching
       ↓
Fuzzy Matching
       ↓
Embedding Matching
       ↓
Hybrid Matching
       ↓
Hybrid + Confidence Review
```

This gives us an experimental story.

---

# 38. METRICS

## Top-1 Accuracy

Was the correct activity ranked first?

## Top-3 Recall

Was the correct activity among the top three?

## Precision

How many predicted matches were correct?

## False Auto-Link Rate

How frequently did the system automatically make a wrong match?

This is one of the most important metrics.

## Review Rate

What percentage requires human review?

A useful system should reduce manual effort without creating dangerous false matches.

---

# 39. RESEARCH / PAPER ANGLE

Possible research question:

> Can hybrid semantic and schedule-context matching reliably map heterogeneous field execution descriptions to planned L5/L6 activities?

Experiment:

```text
Exact
  ↓
Fuzzy
  ↓
Embedding
  ↓
Hybrid
  ↓
Hybrid + Review
```

Another research question:

> How should confidence thresholds balance false automatic links against human review workload?

Another:

> How can fine-grained field execution events be safely related to planned activity progress?

This makes the project more than a dashboard.

---

# 40. WHAT WE SHOULD NOT BUILD FIRST

Do NOT start with:

```text
Complex voice system
Huge LLM
Mobile application
Microservices
Kubernetes
Advanced OCR
Fancy dashboards
Multi-agent architecture
```

These are distractions until the core pipeline works.

The first goal is:

```text
REPORT
 ↓
EVENT
 ↓
MATCH
 ↓
CONFIDENCE
 ↓
APPROVE
 ↓
ACTUAL DATE
```

---

# 41. TEAM STRUCTURE

We have six people.

| Person | Ownership |
|---|---|
| **Amritha** | Semantic Matching + Granularity |
| **Adithyan** | Event Extraction + Time Agent |
| **Yazeen** | Schedule + WBS |
| **Adithyagopan** | Input Ingestion |
| **Adithyanbalu** | Progress + Analytics + Memory |
| **Aliadnan** | Frontend + Integration |

---

# 42. WHY AMRITHA + ADITHYAN ARE CRITICAL

The two most important transformations are:

```text
"What happened?"
```

and:

```text
"Which activity was it?"
```

Adithyan owns:

```text
Raw report
      ↓
ExecutionEvent
```

Amritha owns:

```text
ExecutionEvent
      ↓
ScheduleActivity
```

Therefore:

```text
REPORT
  ↓
ADITHYAN
  ↓
EVENT
  ↓
AMRITHA
  ↓
MATCH
```

These two modules form the core AI pipeline.

---

# 43. TEAM DEPENDENCY GRAPH

```text
                     YAZEEN
                Schedule / WBS
                      │
                      ▼
              ScheduleActivity
                      │
                      │
                      ▼
                  AMRITHA
             Semantic Matching
                      ▲
                      │
                      │
                  ADITHYAN
              Event Extraction
                      ▲
                      │
                ADITHYAGOPAN
                   Ingestion
```

Then:

```text
AMRITHA
   ↓
MatchResult
   ↓
ADITHYANBALU
   ↓
Progress / Analytics
   ↓
ALIADNAN
   ↓
Frontend
```

---

# 44. DEVELOPMENT SHOULD BE PARALLEL

Do not make the team wait for one person.

Everyone should use mock data based on frozen schemas.

For example, Amritha can immediately use:

```json
{
  "event_id": "EVT-001",
  "description": "Spool erection for Line 24-XX",
  "discipline": "piping"
}
```

even before Adithyan finishes the final extraction model.

Aliadnan can build the frontend using:

```json
{
  "activity_id": "PIP-238",
  "confidence": 0.93,
  "status": "review"
}
```

---

# 45. DEVELOPMENT PHASE 1

## Days 1–3

Everyone:

- understand the problem;
- understand the architecture;
- freeze schemas;
- create repository;
- create synthetic dataset;
- define module boundaries.

Critical schemas:

```text
ScheduleActivity
ExecutionEvent
MatchResult
ProgressUpdate
```

---

# 46. DEVELOPMENT PHASE 2

## Days 4–10

Parallel development.

### Amritha

Build:

```text
Exact
Fuzzy
Embedding
Hybrid
```

### Adithyan

Build:

```text
Free-text
 ↓
ExecutionEvent
```

### Yazeen

Build:

```text
Schedule file
 ↓
ScheduleActivity
```

### Adithyagopan

Build:

```text
Upload
 ↓
Raw normalized content
```

### Adithyanbalu

Build:

```text
MatchResult
 ↓
Progress
 ↓
Variance
```

### Aliadnan

Build:

```text
Frontend with mock data
```

---

# 47. DEVELOPMENT PHASE 3

## Days 11–14

First integration.

Target:

```text
Schedule
+
Report
 ↓
Extraction
 ↓
Matching
```

The team should be able to demonstrate:

```text
Report:
"Spool erection completed for Line 24."

       ↓

PIP-238
Confidence: 93%
```

---

# 48. DEVELOPMENT PHASE 4

## Days 15–18

Connect:

```text
Match
 ↓
Progress
 ↓
Actual dates
 ↓
Variance
```

Demo:

```text
Planned finish:
20 Aug

Actual finish:
23 Aug

Variance:
+3 days
```

---

# 49. DEVELOPMENT PHASE 5

## Days 19–22

Frontend integration.

Complete:

```text
Upload
 ↓
Extract
 ↓
Match
 ↓
Review
 ↓
Approve
 ↓
Update
 ↓
Gantt
```

---

# 50. DEVELOPMENT PHASE 6

## Days 23–26

Add:

```text
Granularity
Audit Trail
Unmatched Events
Historical Memory
Review History
```

---

# 51. FINAL PHASE

## Days 27–30

Freeze the architecture.

Focus on:

```text
Evaluation
Demo
Presentation
Documentation
Screenshots
Architecture diagram
Research results
```

Do not introduce huge new features.

---

# 52. IDEAL SIH DEMO

The judge sees a daily report:

> "Piping team completed spool erection for Line 24 yesterday."

The system shows:

```text
EXTRACTED EVENT

Discipline: Piping
Activity: Spool erection for Line 24
Status: Completed
Date: 30 Aug
```

Then:

```text
TOP MATCH

PIP-238
Erect Line 24-XX

Confidence:
93%
```

Evidence:

```text
✓ Discipline
✓ Line identifier
✓ Location
✓ Semantic similarity
```

Then:

```text
AUTO-LINKED
```

The schedule updates:

```text
Actual Finish:
30 Aug
```

Variance:

```text
+3 days
```

The Gantt changes.

Then show:

```text
Audit trail
Historical record
```

That is a complete story.

---

# 53. WHAT THE JUDGE SHOULD UNDERSTAND

By the end of the demo, the judge should understand five things:

### 1.

Site information is messy.

### 2.

Project schedules are structured.

### 3.

Our AI bridges these two worlds.

### 4.

We do not blindly trust AI.

Confidence + human review makes the system safer.

### 5.

The resulting structured execution data can power future analytics and institutional memory.

---

# 54. ONE-MINUTE PROJECT EXPLANATION

> SYNAPSE is an AI-powered planning-to-execution bridge built for infrastructure projects like Oil India Limited's EPC operations. Today, planners spend 3–5 hours per day manually reconciling free-text site reports against hundreds of schedule activities — introducing a 24–72 hour update lag and significant mis-linking errors. SYNAPSE ingests heterogeneous field data (text reports, spreadsheets, PDFs), extracts structured execution events using a hybrid rule-LLM pipeline, and links each event to the correct L5/L6 planned activity using a seven-layer AI architecture including semantic embeddings, schedule-context scoring, and confidence-gated human review. When reports are ambiguous, an agentic clarification agent asks the supervisor targeted questions at the point of data entry — avoiding downstream review queue bottlenecks. Every reviewer decision feeds an active learning loop that continuously improves future matching accuracy. Verified execution history powers delay risk intelligence for future projects. SYNAPSE does not replace planners. It eliminates the manual reconciliation work that prevents them from doing actual planning.

---

# 55. FINAL MVP

The minimum successful system is:

```text
                INPUT
                  │
                  ▼
        ┌──────────────────┐
        │ Ingestion        │
        └────────┬─────────┘
                 ▼
        ┌──────────────────┐
        │ Extraction       │
        └────────┬─────────┘
                 ▼
          ExecutionEvent
                 │
                 ▼
        ┌──────────────────┐
        │ Matching Engine  │
        └────────┬─────────┘
                 ▼
           MatchResult
                 │
                 ▼
        ┌──────────────────┐
        │ Confidence       │
        └────────┬─────────┘
                 │
          ┌──────┴──────┐
          ▼             ▼
       Auto-link      Review
          │             │
          └──────┬──────┘
                 ▼
             Approved
                 │
                 ▼
        ┌──────────────────┐
        │ Progress Engine  │
        └────────┬─────────┘
                 ▼
              Variance
                 │
                 ▼
               Gantt
                 │
                 ▼
         Historical Memory
```

---

# 56. FINAL PROJECT PRINCIPLE

SYNAPSE should **not** be presented as:

> "An AI chatbot for construction."

It should **not** be presented as:

> "A project-management dashboard."

It should be presented as:

> **SYNAPSE — A self-improving, trustworthy data-linking layer between field execution and project schedule, with agentic clarification at input and delay risk intelligence as output.**

The core innovation stack:

```text
MESSY FIELD REALITY (text / Excel / PDF / voice)
        ↓
AGENTIC CLARIFICATION (ask before guessing)
        ↓
STRUCTURED EXECUTION EVENT
        ↓
SEVEN-LAYER HYBRID MATCHING ENGINE
        ↓
CONFIDENCE-AWARE DECISION (auto / review / unmatched)
        ↓
MULTI-SOURCE CONFLICT DETECTION
        ↓
HUMAN REVIEW (only for genuine ambiguity)
        ↓
ACTIVE LEARNING (reviewer decisions improve future matching)
        ↓
TRUSTED SCHEDULE UPDATE + AUDIT TRAIL
        ↓
DELAY RISK INTELLIGENCE (from historical patterns)
        ↓
INSTITUTIONAL MEMORY FOR FUTURE PROJECTS
```

**What makes SYNAPSE a 10/10 idea:**

1. It solves a real, named organizational pain (Oil India Limited, SIH26122).
2. It is not just an app — it is a complete DATA → INTELLIGENCE → DECISION → ACTION pipeline.
3. The agentic clarification layer addresses ambiguity at source, not downstream.
4. The active learning feedback loop is a genuine engineering innovation — the system improves with use.
5. Multi-source conflict detection addresses a real-world problem no tool handles today.
6. Historical delay risk intelligence gives the system a forward-looking output, not just backward-looking reconciliation.
7. Every AI decision is explainable, auditable, and confidence-gated — no silent hallucination.

That is SYNAPSE.