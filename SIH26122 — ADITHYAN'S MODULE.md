# SIH26122 — ADITHYAN'S MODULE

# Heterogeneous Data Ingestion & Activity Event Extraction

**Owner:** Adithyan  
**Module:** Data Ingestion + Event Extraction  
**Priority:** 🔴 Critical  
**Difficulty:** Medium  
**Depends on:** Nothing initially  
**Feeds into:** Amritha's AI Matching Engine

---

# 1. YOUR RESPONSIBILITY

Your job is to answer:

> **"What actually happened on site?"**

The project receives messy field information such as:

- Daily progress reports
- Discipline-wise Excel sheets
- Site diary entries
- Free-text supervisor updates
- Later, voice-transcribed reports

Your module converts these different formats into **one standard structured format** called an `ExecutionEvent`.

You are **not** responsible for deciding which schedule activity the event belongs to.

That is Amritha's job.

Your pipeline is:

```text
RAW FIELD DATA
      ↓
INGESTION
      ↓
TEXT / TABLE EXTRACTION
      ↓
NORMALIZATION
      ↓
EVENT EXTRACTION
      ↓
STRUCTURED ExecutionEvent
      ↓
AMRITHA'S MATCHING ENGINE
```

---

# 2. WHY YOUR MODULE IS IMPORTANT

The SIH problem begins with fragmented execution data.

A real project might contain:

```text
Daily report
Excel spreadsheet
Site diary
Supervisor message
Scanned document
```

and every source can describe the same work differently.

For example:

```text
Daily Report:
"Line 24 spool erection completed."

Excel:
"Spool erect - L24 - Done"

Supervisor:
"24 line erection finished today."

Site diary:
"L-24 erection completed."
```

A human understands these.

A computer sees four different strings.

Your job is to convert them into a common representation.

---

# 3. YOUR MODULE'S POSITION

The complete system:

```text
                  FIELD
                    │
        ┌───────────┼───────────┐
        ↓           ↓           ↓
      PDF         Excel       Text
        │           │           │
        └───────────┼───────────┘
                    ↓
              ADITHYAN
                    │
                    ↓
             ExecutionEvent
                    │
                    ↓
              AMRITHA
                    │
                    ↓
             MatchResult
                    │
                    ↓
            ADITHYANBALU
                    │
                    ↓
            Progress/Variance
                    │
                    ↓
               ALIADNAN
                    │
                    ↓
                  UI
```

---

# 4. THE CORE OUTPUT

Everything you build should eventually produce this structure:

```json
{
  "event_id": "EVT-001",
  "source_id": "DPR-2026-08-30",
  "description": "Spool erection completed for Line 24",
  "discipline": "piping",
  "activity_type": "erection",
  "asset": "Line 24",
  "location": "Unit 4",
  "status": "completed",
  "event_date": "2026-08-30",
  "start_time": null,
  "end_time": "2026-08-30",
  "quantity": null,
  "unit": null,
  "confidence": 0.94
}
```

This is the contract between you and Amritha.

---

# 5. WHAT IS AN ExecutionEvent?

Think of an `ExecutionEvent` as:

> **One structured statement describing something that happened during project execution.**

Examples:

```text
Spool erected
Concrete poured
Pump installed
Cable tray completed
Valve tested
Welding completed
Equipment inspection completed
```

Each should become an event.

---

# 6. EVENT TYPES

Start with a controlled set.

```text
START
PROGRESS
COMPLETE
INSPECTION
TEST
DELAY
ISSUE
QUANTITY_UPDATE
```

Example:

```text
"Pump installation started."

→ START
```

```text
"Pump installation completed."

→ COMPLETE
```

```text
"50 metres of cable tray installed."

→ PROGRESS
```

---

# 7. INPUT FORMATS

Your prototype should support **at least two different input formats**.

The SIH statement specifically suggests examples such as:

```text
Free-text daily report
+
Discipline spreadsheet
```

This is enough for the initial working prototype.

Do not attempt to support every possible format immediately.

---

# 8. INPUT 1 — FREE TEXT

Example:

```text
Daily Progress Report
Date: 30/08/2026

Piping:
Line 24 spool erection completed at Unit 4.
Line 25 welding is in progress.

Electrical:
Cable tray installation started in Area B.
```

Your module should identify:

```text
Event 1:
Line 24 spool erection
Status = completed

Event 2:
Line 25 welding
Status = in progress

Event 3:
Cable tray installation
Status = started
```

---

# 9. INPUT 2 — EXCEL

Example:

| Date | Discipline | Description | Status |
|---|---|---|---|
| 30-08-26 | Piping | Spool erect L24 | Done |
| 30-08-26 | Piping | Welding L25 | Ongoing |
| 30-08-26 | Electrical | Cable tray Area B | Started |

Convert every row into:

```text
ExecutionEvent
```

---

# 10. INPUT 3 — SCANNED DOCUMENT

This is optional for the first prototype.

Pipeline:

```text
Scanned PDF
     ↓
OCR
     ↓
Text
     ↓
Event Extraction
```

Do not spend most of your time building a perfect OCR system.

The SIH statement explicitly says:

> Full production-grade OCR/ASR is not required.

A prototype-level OCR pipeline is enough.

---

# 11. INPUT 4 — VOICE

Voice is another optional extension.

Pipeline:

```text
Supervisor speaks
       ↓
Speech-to-text
       ↓
Raw transcript
       ↓
Event extraction
```

Example:

> "Line twenty-four spool erection completed today."

becomes:

```json
{
  "description": "Line 24 spool erection completed",
  "asset": "Line 24",
  "status": "completed"
}
```

Do not make voice your first priority.

---

# 12. NORMALIZATION

Different people may write:

```text
L24
Line 24
LINE-24
Line-24
24
```

Your system should normalize obvious variations.

For example:

```text
"LINE-24"
        ↓
"Line 24"
```

Similarly:

```text
Completed
Complete
Done
Finished
```

can be normalized to:

```text
completed
```

---

# 13. DO NOT OVER-NORMALIZE

Be careful.

Suppose:

```text
Line 24
Line 240
```

These are different.

A careless normalization rule could incorrectly convert them into the same identifier.

Therefore:

> Preserve the original text alongside normalized fields.

Always store:

```json
{
  "raw_text": "Spool erect L24 done",
  "normalized_description": "Spool erection Line 24 completed"
}
```

---

# 14. INFORMATION EXTRACTION

Your extractor should attempt to identify:

```text
WHAT happened?
WHEN?
WHERE?
WHICH discipline?
WHICH asset?
HOW MUCH?
WHAT status?
```

Example:

> "Piping crew completed erection of 4 spools on Line 24 in Unit 4 on August 30."

Extract:

```text
Action:
erection

Quantity:
4

Object:
spools

Asset:
Line 24

Location:
Unit 4

Discipline:
piping

Date:
30 August

Status:
completed
```

---

# 15. LLM EXTRACTION

An LLM can be useful for messy free text.

Give it a strict schema.

For example:

```text
Extract execution events from this report.

Return ONLY JSON.

Fields:
event_id
description
discipline
activity_type
asset
location
status
event_date
start_time
end_time
quantity
unit
```

The important point:

> **The LLM extracts information; it does not decide the schedule match.**

---

# 16. WHY YOU SHOULD NOT LET THE LLM MATCH

Bad architecture:

```text
Report
 ↓
LLM
 ↓
"PIP-238"
```

This can hallucinate.

Better:

```text
Report
 ↓
LLM extraction
 ↓
Structured event
 ↓
Deterministic/embedding matcher
 ↓
Candidate activities
```

This separates responsibilities.

---

# 17. STRUCTURED OUTPUT

Use Pydantic or equivalent schema validation.

Example:

```python
class ExecutionEvent:
    event_id: str
    description: str
    discipline: str | None
    activity_type: str | None
    asset: str | None
    location: str | None
    status: str
    event_date: str | None
    start_time: str | None
    end_time: str | None
    quantity: float | None
    unit: str | None
    confidence: float
```

The exact implementation can change.

The important thing is the schema.

---

# 18. EXTRACTION CONFIDENCE

Your extraction model should also produce confidence.

Example:

```text
Discipline:
piping
confidence = 0.98

Asset:
Line 24
confidence = 0.95

Location:
Unit 4
confidence = 0.88
```

This is different from Amritha's **matching confidence**.

You need to keep the two separate.

---

# 19. TWO DIFFERENT CONFIDENCES

### Extraction confidence

> "Did we correctly understand the report?"

### Matching confidence

> "Did we correctly connect this event to a schedule activity?"

Example:

```text
Extraction:
94%

Matching:
91%
```

Do not merge them into one unexplained number.

---

# 20. EVENT DEDUPLICATION

The same event may appear in multiple sources.

Example:

```text
Daily report:
Line 24 completed.

Excel:
Line 24 — Done.

Supervisor:
Line 24 finished.
```

Your system could create three events.

Instead, eventually detect:

```text
EVT-001
EVT-002
EVT-003
```

as possible duplicates.

For the first version, you can flag duplicates rather than automatically deleting them.

---

# 21. SOURCE TRACEABILITY

Every event should remember where it came from.

Example:

```json
{
  "event_id": "EVT-001",
  "source_id": "DPR-023",
  "source_type": "daily_report",
  "source_reference": "page_2"
}
```

This is essential for the audit trail.

A reviewer should be able to ask:

> "Where did this information come from?"

and see the original source.

---

# 22. RAW + PROCESSED DATA

Never destroy the original input.

Store:

```text
RAW DATA
   +
PROCESSED DATA
```

Example:

```text
raw_text:
"spool erect l24 done"

normalized:
"Spool erection Line 24 completed"
```

This lets the team debug extraction errors.

---

# 23. ERROR HANDLING

Suppose the input says:

> "Pipe work completed."

There is not enough information.

Do NOT invent:

```text
Line 24
Unit 4
Piping
```

Instead:

```json
{
  "description": "Pipe work completed",
  "discipline": null,
  "asset": null,
  "location": null,
  "status": "completed",
  "confidence": 0.55
}
```

Then Amritha's matcher can decide whether enough information exists for a candidate match.

---

# 24. MISSING INFORMATION

Use:

```text
null
```

rather than fabricated information.

Bad:

```text
location = "Unit 4"
```

when the report never mentioned Unit 4.

Good:

```text
location = null
```

This principle is extremely important for the project.

---

# 25. TEMPORAL EXTRACTION

Reports may say:

```text
today
yesterday
last night
morning
afternoon
completed on Friday
started two days ago
```

Your system should convert relative dates using the report date.

Example:

```text
Report date:
30 Aug 2026

"completed yesterday"

→
29 Aug 2026
```

---

# 26. START AND END EVENTS

The SIH problem specifically wants:

> Activity-level actual start/end events.

Therefore distinguish:

```text
START
```

from:

```text
END
```

Example:

> "Line 24 erection started on August 20."

```json
{
  "status": "started",
  "event_date": "2026-08-20"
}
```

Example:

> "Line 24 erection completed on August 24."

```json
{
  "status": "completed",
  "event_date": "2026-08-24"
}
```

---

# 27. EVENT TIMELINE

Eventually multiple events can form:

```text
PIP-238
   │
   ├── START — Aug 20
   ├── PROGRESS — Aug 21
   ├── PROGRESS — Aug 22
   └── COMPLETE — Aug 24
```

This is useful for the downstream progress engine.

---

# 28. QUANTITY EXTRACTION

Example:

> "Installed 120 metres of cable tray."

Extract:

```text
quantity = 120
unit = metres
activity_type = installation
object = cable tray
```

Another:

> "Four spools erected."

```text
quantity = 4
unit = spools
```

Keep quantity separate from status.

---

# 29. DISCIPLINE CLASSIFICATION

Possible disciplines:

```text
Civil
Piping
Mechanical
Static Equipment
Rotating Equipment
Electrical
Instrumentation
HSE
```

If explicitly stated:

```text
Piping:
Line 24 completed.
```

then:

```text
discipline = piping
```

If not stated, infer cautiously.

If uncertain:

```text
discipline = null
```

or:

```text
discipline_confidence < threshold
```

---

# 30. ACTIVITY TYPE

Extract verbs/actions.

Examples:

```text
erection
welding
installation
inspection
testing
excavation
concreting
painting
cabling
commissioning
```

This becomes valuable context for Amritha.

---

# 31. NORMALIZATION DICTIONARY

Build a small domain dictionary.

Example:

```text
erect
erection
erected
→ erection
```

```text
install
installed
installation
→ installation
```

```text
complete
completed
done
finished
→ completed
```

Do not try to create a dictionary containing every possible engineering term.

Start small and expand based on errors.

---

# 32. SYNTHETIC DATASET

You need test data.

Create approximately:

```text
100–200 reports
```

containing:

- piping;
- civil;
- electrical;
- instrumentation;
- mechanical.

Include both easy and difficult examples.

---

# 33. DATASET DIFFICULTY LEVELS

### Easy

```text
Line 24 erection completed.
```

### Medium

```text
Spool erection for L24 completed today.
```

### Hard

```text
Piping crew finished putting the prefabricated spool
in place on the twenty-four line.
```

### Very hard

```text
Crew finished the remaining spool work on the north
rack; line reference was mentioned verbally as 24.
```

---

# 34. GROUND TRUTH

For every synthetic report, manually define:

```text
Correct event fields
```

Example:

```json
{
  "discipline": "piping",
  "asset": "Line 24",
  "activity_type": "erection",
  "status": "completed",
  "event_date": "2026-08-30"
}
```

This allows evaluation.

---

# 35. EXTRACTION EVALUATION

Measure field-level accuracy.

For example:

```text
Discipline accuracy
Asset extraction accuracy
Date extraction accuracy
Status accuracy
Quantity accuracy
Location accuracy
```

You can calculate:

```text
Correct fields
───────────────
Total fields
```

---

# 36. EVENT-LEVEL ACCURACY

An event is correct only if the critical fields are correct.

For example:

```text
Description ✓
Discipline ✓
Asset ✓
Date ✓
Status ✓
```

Then:

```text
Event extraction = correct
```

If the asset is wrong:

```text
Event extraction = incorrect
```

depending on your evaluation definition.

Document your criteria clearly.

---

# 37. LLM VS RULE-BASED EXTRACTION

You should experiment.

### Approach A

```text
Rules
```

### Approach B

```text
LLM
```

### Approach C

```text
Rules + LLM
```

For structured fields such as dates and identifiers, deterministic parsing can be more reliable.

For messy descriptions, an LLM can help.

---

# 38. RECOMMENDED HYBRID ARCHITECTURE

```text
                 RAW INPUT
                     │
                     ▼
               Format Parser
                     │
          ┌──────────┴──────────┐
          ↓                     ↓
     Deterministic          LLM Extraction
       Extraction
          │                     │
          └──────────┬──────────┘
                     ↓
              Schema Validation
                     ↓
               Normalization
                     ↓
               ExecutionEvent
```

---

# 39. WHAT YOU SHOULD BUILD FIRST

## Week/Phase 1

Build:

```text
CSV/Excel reader
```

Input:

```text
date
discipline
description
status
```

Output:

```text
ExecutionEvent
```

---

# 40. PHASE 2

Add:

```text
Free-text report parser
```

Start with rule-based extraction.

---

# 41. PHASE 3

Add:

```text
LLM extraction
```

for messy descriptions.

---

# 42. PHASE 4

Add:

```text
PDF text extraction
```

Do not start with OCR.

First support text-based PDFs.

---

# 43. PHASE 5

Add:

```text
OCR
```

only if time allows.

---

# 44. PHASE 6

Add:

```text
Voice → transcription → event extraction
```

This becomes a strong demo extension.

---

# 45. PHASE 7

Add:

```text
Deduplication
Source traceability
Confidence
Validation
```

---

# 46. API CONTRACT WITH AMRITHA

Your output must be stable.

Recommended endpoint:

```text
POST /events/extract
```

Response:

```json
{
  "events": [
    {
      "event_id": "EVT-001",
      "description": "Spool erection completed for Line 24",
      "discipline": "piping",
      "activity_type": "erection",
      "asset": "Line 24",
      "location": "Unit 4",
      "status": "completed",
      "event_date": "2026-08-30",
      "quantity": null,
      "unit": null,
      "confidence": 0.94
    }
  ]
}
```

Amritha should be able to consume this without knowing how you extracted it.

---

# 47. DO NOT PUT MATCHING LOGIC HERE

Avoid:

```python
if "line 24" in text:
    activity_id = "PIP-238"
```

That is not your responsibility.

Instead:

```python
event.asset = "Line 24"
```

Then Amritha's module determines:

```text
Line 24
       ↓
PIP-238
```

---

# 48. YOUR RELATIONSHIP WITH YAZEEN

Yazeen owns the schedule parser.

You may need the schedule schema for testing, but you should not build his module.

Your input is:

```text
FIELD DATA
```

His input/output revolves around:

```text
SCHEDULE DATA
```

---

# 49. YOUR RELATIONSHIP WITH ADITHYANBALU

You provide events.

He calculates:

```text
Actual progress
Duration
Variance
Delay
```

Example:

```text
Event:
PIP-238 completed Aug 24
```

He compares that against:

```text
Planned finish:
Aug 20
```

and calculates:

```text
Variance = +4 days
```

---

# 50. YOUR RELATIONSHIP WITH ALIADNAN

Aliadnan needs to display:

```text
Source
Extracted event
Confidence
Original text
```

Example:

```text
SOURCE:
DPR_30_08.pdf

EXTRACTED:
Line 24 spool erection completed

CONFIDENCE:
94%
```

---

# 51. YOUR RELATIONSHIP WITH AMRITHA

This is your most important interface.

You give:

```text
ExecutionEvent
```

She gives:

```text
MatchResult
```

Think:

```text
YOU:
"What happened?"

AMRITHA:
"Which planned activity was that?"
```

---

# 52. DATA FLOW BETWEEN YOU TWO

```text
DPR
 │
 ▼
ADITHYAN
 │
 │ Extraction
 ▼
ExecutionEvent
 │
 │
 ▼
AMRITHA
 │
 │ Matching
 ▼
MatchResult
```

Do not tightly couple your implementations.

Only the data contract needs to be shared.

---

# 53. FAILURE CASE

Input:

> "Pipe work completed."

Output:

```json
{
  "description": "Pipe work completed",
  "discipline": null,
  "asset": null,
  "location": null,
  "status": "completed",
  "confidence": 0.51
}
```

Then:

```text
AMRITHA
```

may produce:

```text
No reliable match
```

This is a valid outcome.

The system should not invent information merely to force a match.

---

# 54. AUDIT TRAIL

Every transformation should ideally be traceable:

```text
Original document
       ↓
Extracted text
       ↓
Extracted event
       ↓
Normalized event
       ↓
Matched activity
```

This supports:

```text
debugging
review
trust
audit
```

---

# 55. SECURITY / PRIVACY

The SIH statement says live project data will not be shared.

Therefore your prototype should use:

```text
Synthetic data
```

and avoid putting confidential project information into external services unless explicitly authorized.

For your architecture, design the extraction component so that it can eventually run in a controlled/on-premise environment.

---

# 56. WHAT NOT TO BUILD

Do NOT spend your time building:

```text
❌ Gantt chart
❌ Dashboard
❌ Semantic matching
❌ Schedule optimization
❌ Delay prediction
❌ Knowledge graph
```

Your core responsibility is:

```text
RAW DATA
 ↓
EXECUTION EVENT
```

---

# 57. MINIMUM VIABLE MODULE

Your minimum successful version:

```text
✓ Excel ingestion
✓ Free-text ingestion
✓ Event extraction
✓ Date extraction
✓ Status extraction
✓ Discipline extraction
✓ Asset extraction
✓ Structured JSON
✓ Confidence
✓ Source traceability
```

---

# 58. STRONG VERSION

A strong version additionally contains:

```text
✓ PDF extraction
✓ LLM extraction
✓ OCR
✓ Deduplication
✓ Quantity extraction
✓ Activity-type extraction
✓ Validation
✓ Error handling
✓ Evaluation benchmark
```

---

# 59. ADVANCED VERSION

If the core system is already stable:

```text
✓ Voice input
✓ Multilingual normalization
✓ Supervisor conversational interface
✓ Automatic clarification questions
✓ Event history
✓ Extraction feedback loop
```

---

# 60. AGENTIC CLARIFICATION LOOP — FIRST-CLASS FEATURE (NOT OPTIONAL)

This is SYNAPSE's Agentic AI layer. It is not an extension. It is a core differentiator.

SIH 2026 specifically rewards Agentic AI: *"systems that plan, use tools, and perform tasks."*

## What it does

When a supervisor's input lacks enough information for a confident extraction, the system does not silently return `null` fields. It asks.

```text
Supervisor: "Erection completed today."

        ↓

SYNAPSE Agent detects:
  activity_type = erection ✓
  status = completed ✓
  asset = MISSING ✗
  location = MISSING ✗

        ↓

Agent responds:
"I found 3 erection activities active in your area today:
  (a) Line 24-XX — Pipe Rack A
  (b) Line 25-XX — Pipe Rack A
  (c) Structural steel erection — Unit 4

Which one did you complete?"

        ↓

Supervisor: "a"

        ↓

ExecutionEvent:
  asset: "Line 24-XX"
  activity_type: "erection"
  status: "completed"
  extraction_confidence: 0.97
```

The event that arrives at Amritha's matcher is now **high-confidence** because ambiguity was resolved **at the source**, not hours later in a planner's review queue.

## Why this is better than the current approach

```text
CURRENT APPROACH (without agentic layer):
Supervisor writes ambiguously
        ↓
Event extracted with null fields + low confidence
        ↓
Goes to Amritha's matcher
        ↓
All candidates score low
        ↓
Sent to planner review queue
        ↓
Planner reviews 6 hours later
        ↓
Planner approves → schedule updates

SYNAPSE AGENTIC APPROACH:
Supervisor writes ambiguously
        ↓
Agent asks one clarifying question (instant)
        ↓
Supervisor confirms in seconds
        ↓
High-confidence event extracted
        ↓
AUTO-LINKED by matcher → schedule updates immediately
```

## Minimum implementation

A rule-based agent that detects which fields are null and generates a question:

```python
def clarify(event: ExecutionEvent, active_activities: list) -> str:
    if event.asset is None:
        candidates = filter_by(discipline=event.discipline, location=event.location)
        return f"Which activity? {format_options(candidates)}"
    if event.location is None:
        return "Which area or unit?"
    return None  # No clarification needed
```

This is achievable in 2–3 days.

## Strong implementation

An LLM-powered agent that:
- Understands natural language replies ("the second one" / "the north rack one")
- Can handle multi-turn conversation
- Adapts questions based on supervisor's role and past activity history

## Demo value

This is one of the most demo-friendly features in SYNAPSE.

```text
Judge watches supervisor type: "Erection finished."

SYNAPSE instantly responds:
"Did you mean:
  (a) Line 24-XX erection?
  (b) Line 25-XX erection?"

Supervisor types: "a"

SYNAPSE: "Got it. Linked to PIP-238. Schedule updated."
```

That takes 8 seconds. A judge will remember it.

---

# 61. DEMO SCENARIO

Upload:

```text
DPR_30_08.pdf
```

The system displays:

```text
✓ Document processed
✓ 7 events detected
```

Then:

```text
EVENT 01

Discipline:
Piping

Activity:
Spool erection

Asset:
Line 24

Status:
Completed

Date:
30 Aug 2026

Confidence:
94%
```

Then the event goes to:

```text
AMRITHA'S MATCHING ENGINE
```

---

# 62. HARD DEMO SCENARIO

Input:

> "Remaining pipe work finished today."

Your system should produce:

```text
Activity:
pipe work

Status:
completed

Date:
30 Aug 2026

Asset:
unknown

Location:
unknown

Confidence:
low
```

Then Amritha should not confidently map it to a schedule activity.

This demonstrates responsible AI behavior.

---

# 63. TESTING

Create unit tests for:

```text
Date extraction
Status extraction
Identifier extraction
Discipline classification
Quantity extraction
Normalization
JSON validation
```

Example:

```text
Input:
"Line 24 spool erection completed."

Expected:

asset = Line 24
activity_type = erection
status = completed
```

---

# 64. YOUR MODULE'S ARCHITECTURE

```text
                    RAW DATA
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
       PDF            XLSX           TXT
        │              │              │
        └──────────────┼──────────────┘
                       ↓
                 Input Parser
                       │
                       ▼
              Text/Table Extraction
                       │
                       ▼
             Rule + LLM Extraction
                       │
                       ▼
                Normalization
                       │
                       ▼
              Schema Validation
                       │
                       ▼
               Confidence Score
                       │
                       ▼
               ExecutionEvent
                       │
                       ▼
                 AMRITHA
```

---

# 65. DEVELOPMENT ORDER

Follow this exact order:

```text
1. Define ExecutionEvent schema
        ↓
2. Build Excel parser
        ↓
3. Build text parser
        ↓
4. Add basic normalization
        ↓
5. Add rule-based extraction
        ↓
6. Add LLM extraction
        ↓
7. Add confidence
        ↓
8. Add PDF support
        ↓
9. Add deduplication
        ↓
10. Add OCR if time permits
        ↓
11. Add voice if core system is stable
```

---

# 66. DEFINITION OF DONE

## Basic

- [ ] Excel file accepted.
- [ ] Free text accepted.
- [ ] Events extracted.
- [ ] JSON schema implemented.
- [ ] Dates extracted.
- [ ] Status extracted.
- [ ] Discipline extracted.
- [ ] Assets extracted.

## Intermediate

- [ ] LLM extraction works.
- [ ] Rule-based extraction works.
- [ ] Confidence is generated.
- [ ] Raw source retained.
- [ ] PDF text extraction works.
- [ ] Validation exists.

## Advanced

- [ ] OCR works.
- [ ] Duplicate events detected.
- [ ] Quantity extracted.
- [ ] Activity type extracted.
- [ ] Clarification flow works.
- [ ] Voice input works.

---

# 67. YOUR FINAL MENTAL MODEL

Remember this:

```text
ADITHYAN

"What did the field report say
actually happened?"
```

You answer:

```text
"This is the structured event."
```

Then:

```text
AMRITHA

"Which planned L5/L6 activity
does this event correspond to?"
```

Then:

```text
ADITHYANBALU

"What does that mean for
actual progress and variance?"
```

Then:

```text
ALIADNAN

"How should the user see it?"
```

---

# 68. THE MOST IMPORTANT RULE

### Never manufacture certainty.

If the report doesn't tell you:

```text
which line
which unit
which activity
which date
```

don't invent it.

Return:

```text
unknown / null
```

with an appropriate confidence.

That makes your extraction engine useful to the matching engine instead of poisoning it with fabricated data.

---

# 69. YOUR ONE-LINE JOB DESCRIPTION

> **Build the pipeline that converts messy, heterogeneous field execution data into reliable, traceable, structured ExecutionEvents that the AI matching engine can safely connect to the project's L5/L6 schedule.**

---

# 70. HANDOFF TO AMRITHA

Your final deliverable to Amritha is:

```text
ExecutionEvent[]
```

with:

```text
event_id
source_id
raw_text
description
discipline
activity_type
asset
location
status
event_date
start_time
end_time
quantity
unit
extraction_confidence
```

Her deliverable back into the overall system is:

```text
MatchResult[]
```

This clean separation lets both of you develop **independently** and integrate later without rewriting each other's work.