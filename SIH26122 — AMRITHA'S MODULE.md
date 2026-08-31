# SIH26122 — AMRITHA'S MODULE

# AI Semantic Matching, Contextual Ranking & Granularity Handling

**Owner:** Amritha  
**Module:** Execution-to-Schedule Matching  
**Priority:** 🔴 Critical  
**Difficulty:** Medium–Hard  
**Core Question:**

> Given a messy field execution event, which planned L5/L6 activity does it actually represent?

---

# TABLE OF CONTENTS

1. Your Responsibility
2. Why Your Module Is the Core
3. The Exact Problem You Are Solving
4. Input and Output
5. Complete Matching Pipeline
6. Understanding Semantic Matching
7. Why Exact Matching Fails
8. Fuzzy Matching
9. Embedding-Based Matching
10. Candidate Retrieval
11. Contextual Matching
12. Identifier Extraction
13. Discipline Matching
14. Location Matching
15. WBS Matching
16. Temporal Context
17. Dependency Context
18. Hybrid Scoring
19. Confidence
20. Auto-Link vs Review vs Unmatched
21. Reviewer Queue
22. Explanation Generation
23. Granularity Mismatch
24. Partial Progress
25. One-to-Many Relationships
26. Many-to-One Relationships
27. Hard Matching Cases
28. Synthetic Dataset
29. Ground Truth
30. Evaluation
31. Baselines
32. Experiments
33. Error Analysis
34. Improving the Model
35. Database / Vector Search
36. API Contract
37. Development Plan
38. Learning Plan
39. What You Should NOT Build
40. Research/Paper Direction
41. Demo
42. Definition of Done

---

# 1. YOUR RESPONSIBILITY

Your responsibility is the **semantic matching engine**.

The system receives:

```text
ExecutionEvent
```

from Adithyan.

You compare it against:

```text
ScheduleActivity[]
```

from Yazeen.

You return:

```text
MatchResult
```

Your responsibility is therefore:

```text
Execution Event
       ↓
Candidate Activities
       ↓
Rank Candidates
       ↓
Calculate Confidence
       ↓
Auto-link / Review / Unmatched
```

---

# 2. WHY YOUR MODULE IS THE CORE

The project could technically ingest reports without your module.

It could also extract events without your module.

But then the system still cannot answer the most important question:

> **Which planned activity did this field event actually refer to?**

Without matching:

```text
Report
 ↓
Extracted event
```

With matching:

```text
Report
 ↓
Extracted event
 ↓
Correct schedule activity
 ↓
Actual progress
 ↓
Schedule update
```

Therefore the matching engine is the bridge between:

```text
FIELD REALITY
```

and:

```text
PROJECT PLAN
```

---

# 3. THE EXACT PROBLEM YOU ARE SOLVING

Suppose the schedule contains:

```text
Activity ID: PIP-238

Activity Name:
Erect Line 24-XX

Discipline:
Piping

Location:
Unit 4
```

The field report says:

> "Piping crew completed spool erection for line twenty-four yesterday."

The system receives:

```json
{
  "description": "Piping crew completed spool erection for line twenty-four",
  "discipline": "piping",
  "asset": "24",
  "status": "completed"
}
```

You need to produce:

```text
PIP-238
```

with a confidence score.

---

# 4. INPUT AND OUTPUT

## Input 1 — ExecutionEvent

You receive something like:

```json
{
  "event_id": "EVT-001",
  "description": "Spool erection completed for Line 24",
  "discipline": "piping",
  "asset": "24",
  "location": "Unit-4",
  "start_time": null,
  "end_time": "2026-08-30",
  "status": "completed"
}
```

---

## Input 2 — ScheduleActivity

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
  "planned_finish": "2026-08-20"
}
```

---

## Output — MatchResult

```json
{
  "event_id": "EVT-001",
  "activity_id": "PIP-238",
  "semantic_score": 0.94,
  "context_score": 0.92,
  "final_confidence": 0.93,
  "match_status": "auto_linked",
  "explanation": "Strong semantic, discipline, location and identifier agreement."
}
```

---

# 5. COMPLETE MATCHING PIPELINE

Your module should eventually look like:

```text
                 ExecutionEvent
                       │
                       ▼
              ┌─────────────────┐
              │ Normalization   │
              └────────┬────────┘
                       │
                       ▼
              Identifier Extraction
                       │
                       ▼
              Candidate Retrieval
                       │
                       ▼
              ┌─────────────────┐
              │ Embedding Model │
              └────────┬────────┘
                       │
                       ▼
                  Top-K Results
                       │
                       ▼
              Contextual Ranking
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      Discipline    Location     Identifier
          │            │            │
          └────────────┼────────────┘
                       ▼
                  Final Score
                       │
                       ▼
                  Confidence
                       │
             ┌─────────┼─────────┐
             ▼         ▼         ▼
           HIGH      MEDIUM      LOW
             │         │         │
             ▼         ▼         ▼
          Auto-link  Review   Unmatched
```

---

# 6. UNDERSTANDING SEMANTIC MATCHING

Semantic matching means comparing **meaning**, not just identical words.

Consider:

```text
Schedule:
Erect Line 24-XX

Report:
Spool erection completed for line twenty-four.
```

The words aren't identical.

But semantically:

```text
erect
≈
erection

24-XX
≈
line twenty-four
```

An embedding model can represent both sentences as vectors.

Conceptually:

```text
Sentence A
   ↓
[0.12, 0.45, -0.31, ...]


Sentence B
   ↓
[0.11, 0.43, -0.29, ...]
```

Their vectors should be relatively close.

---

# 7. WHY EXACT MATCHING FAILS

A naive approach:

```python
if report_description == activity_name:
    match
```

fails immediately.

Example:

```text
Erect Line 24-XX

vs

Line 24 spool erection completed
```

These strings differ significantly.

Yet a human recognizes them as related.

---

# 8. FUZZY MATCHING

Before embeddings, implement fuzzy matching.

It helps with:

```text
Erect Line 24-XX
```

vs:

```text
Erect Line 24 XX
```

or:

```text
Erect Line 24-XX
```

vs:

```text
Erect line 24 xx
```

It can handle:
- spelling errors;
- punctuation;
- word order;
- minor textual differences.

But fuzzy matching does not understand domain meaning very well.

---

# 9. EMBEDDING-BASED MATCHING

Use an embedding model such as a Sentence Transformer.

Conceptually:

```text
Schedule Activities
       ↓
Embedding Model
       ↓
Vectors
       ↓
Vector Database
```

For a new event:

```text
Execution Event
       ↓
Embedding
       ↓
Vector Search
       ↓
Top-K Schedule Activities
```

Example:

```text
EVENT:

"Spool erection completed for Line 24"

TOP CANDIDATES:

PIP-238   0.94
PIP-241   0.62
PIP-245   0.48
```

---

# 10. CANDIDATE RETRIEVAL

Do not immediately perform expensive reasoning over every activity.

Suppose there are:

```text
50,000 schedule activities
```

Comparing one event against all 50,000 repeatedly is unnecessary.

Instead:

```text
50,000 activities
       ↓
Vector index
       ↓
Top 20 candidates
       ↓
Contextual ranking
       ↓
Top 3
```

This is called candidate retrieval.

---

# 11. WHY TOP-K MATTERS

Suppose the correct activity isn't ranked first by embeddings.

It may still appear in:

```text
Top 5
```

or:

```text
Top 10
```

Your second-stage ranking can then recover it.

This is why evaluation should include:

```text
Top-1 accuracy
```

and:

```text
Top-3 / Top-5 recall
```

---

# 12. CONTEXTUAL MATCHING

Semantic similarity alone is insufficient.

Imagine:

```text
PIP-101
Erect Line 24
Unit 3

PIP-102
Erect Line 24
Unit 4
```

Report:

> "Line 24 erection completed in Unit 4."

Both descriptions may be semantically similar.

But:

```text
Location = Unit 4
```

strongly favors:

```text
PIP-102
```

Therefore matching needs contextual evidence.

---

# 13. IDENTIFIER MATCHING

Identifiers are extremely useful.

Examples:

```text
Line 24
Equipment E-102
Pump P-101
Valve V-203
Area A-04
```

The report may say:

```text
24
```

while the schedule says:

```text
24-XX
```

Your system should normalize identifiers before comparing them.

Example:

```text
Line 24
LINE-24
line twenty-four
24-XX
```

can potentially be represented through extracted identifier components.

Do not blindly equate identifiers if the domain rules do not justify it.

---

# 14. DISCIPLINE MATCHING

Each activity can have:

```text
discipline = piping
```

and the event can have:

```text
discipline = piping
```

This is strong contextual evidence.

If:

```text
event = electrical
activity = piping
```

the candidate should usually be penalized heavily or filtered out, depending on project rules.

---

# 15. LOCATION MATCHING

Possible location information:

```text
Unit 4
Area A
Pipe Rack B
Train 2
```

Normalize location strings.

Example:

```text
Unit-4
Unit 4
UNIT4
U-4
```

may refer to the same location depending on the domain dictionary.

Create normalization rules rather than relying only on an LLM.

---

# 16. WBS MATCHING

Suppose:

```text
WBS:
Construction
 └── Piping
      └── Unit 4
           └── Pipe Rack
```

An event that is clearly piping-related and occurs in Unit 4 should have stronger compatibility with this WBS branch.

WBS context can therefore become a ranking signal.

---

# 17. TEMPORAL CONTEXT

Suppose an activity was planned:

```text
16 Aug → 20 Aug
```

and a report says it was completed:

```text
23 Aug
```

The activity may be late.

That does **not** mean it should be rejected.

Temporal context should help ranking, not blindly eliminate late activities.

This is important.

A real system must be able to recognize:

> "The activity happened later than planned."

rather than:

> "It cannot be this activity because it happened after the planned finish."

---

# 18. DEPENDENCY CONTEXT

Suppose:

```text
PIP-237
Prepare line

      ↓

PIP-238
Erect line

      ↓

PIP-239
Inspect line
```

If the report says:

> "Inspection completed."

and the predecessor activity is still incomplete, this may indicate:
- wrong match;
- schedule inconsistency;
- reporting inconsistency;
- unusual execution sequence.

Dependencies can therefore provide additional evidence.

Do not use them as absolute truth.

Real projects can deviate from plans.

---

# 19. HYBRID SCORE

Your final ranking can combine:

```text
Semantic similarity
Identifier similarity
Discipline compatibility
Location compatibility
WBS compatibility
Temporal compatibility
Dependency compatibility
```

Conceptually:

```text
Final Score =
    w1 × Semantic
  + w2 × Identifier
  + w3 × Discipline
  + w4 × Location
  + w5 × WBS
  + w6 × Temporal
  + w7 × Dependency
```

The `w` values are weights.

Do not arbitrarily claim that your weights are scientifically optimal.

Instead:

```text
Initial weights
       ↓
Validation dataset
       ↓
Experiment
       ↓
Tune
       ↓
Evaluate
```

---

# 20. CONFIDENCE

The final system needs an operational decision.

For example:

```text
Confidence ≥ 0.90
       ↓
Auto-link
```

```text
0.70 ≤ Confidence < 0.90
       ↓
Human review
```

```text
Confidence < 0.70
       ↓
Unmatched
```

These numbers are **illustrative starting points**.

Your project should determine appropriate thresholds using validation data.

---

# 21. CONFIDENCE IS NOT JUST A NUMBER

A strong UI should explain why.

Example:

```text
PIP-238

Confidence: 93%

Evidence:
✓ Piping discipline
✓ Line 24 identifier
✓ Unit 4 location
✓ Strong semantic similarity
✓ Compatible WBS
```

This makes the AI more trustworthy.

---

# 22. AUTO-LINK

High-confidence match:

```text
Event
 ↓
PIP-238
 ↓
93%
 ↓
AUTO-LINK
```

The system can proceed toward schedule updating according to the team's configured safety policy.

---

# 23. HUMAN REVIEW

Medium-confidence match:

```text
Event
 ↓
PIP-238
 ↓
76%
 ↓
REVIEW QUEUE
```

The planner sees:

```text
EVENT

"Pipe work completed in Unit 4."

CANDIDATES:

PIP-238
Erect Line 24
78%

PIP-241
Weld Line 24
74%

PIP-245
Valve installation
69%
```

The planner chooses the correct activity.

---

# 24. UNMATCHED

Low confidence:

```text
Event
 ↓
No reliable match
```

Do NOT throw the event away.

Store:

```text
UNMATCHED EVENT
```

Possible reasons:

```text
New activity
Missing schedule activity
Bad report
Insufficient information
Incorrect extraction
Unexpected field work
```

This is important because the SIH statement explicitly says unmatched/new activities should be flagged rather than silently dropped.

---

# 25. REVIEW QUEUE DESIGN

The review interface should show:

```text
┌───────────────────────────────────────┐
│ EVENT                                 │
│                                       │
│ "Pipe work completed in Unit 4."      │
│                                       │
│ Discipline: Piping                    │
│ Location: Unit 4                      │
│                                       │
├───────────────────────────────────────┤
│ CANDIDATES                            │
│                                       │
│ PIP-238    Erect Line 24      78%     │
│ PIP-241    Weld Line 24       74%     │
│ PIP-245    Valve Installation 69%     │
│                                       │
│ [APPROVE] [REJECT] [UNMATCHED]        │
└───────────────────────────────────────┘
```

---

# 26. EXPLANATION GENERATION

The explanation should ideally be structured rather than hallucinated.

Instead of:

> "The AI thinks this is probably correct."

Use evidence:

```text
Semantic similarity: 0.94
Identifier match: Yes
Discipline match: Yes
Location match: Yes
WBS compatibility: Yes
```

Then:

```text
Reason:
Strong agreement across semantic and contextual signals.
```

---

# 27. GRANULARITY MISMATCH

This is one of your most important research challenges.

The schedule may contain:

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

The relationship is not necessarily:

```text
Spool 001 = PIP-200
```

Instead:

```text
Spool 001
Spool 002
Spool 003
Spool 004
        ↓
PIP-200
```

This is a many-to-one relationship.

---

# 28. ONE-TO-MANY RELATIONSHIP

Another possibility:

```text
One planned activity
        ↓
Multiple execution events
```

Example:

```text
PIP-200
```

has:

```text
EVT-001
EVT-002
EVT-003
EVT-004
```

Each event may represent a portion of the work.

Your matcher should not overwrite previous evidence.

Instead:

```text
PIP-200
 ├── EVT-001
 ├── EVT-002
 ├── EVT-003
 └── EVT-004
```

---

# 29. MANY-TO-ONE RELATIONSHIP

Example:

```text
Spool 001
Spool 002
Spool 003
```

all contribute toward:

```text
PIP-200
```

This should be represented explicitly.

---

# 30. PARTIAL PROGRESS

If:

```text
3 of 4 spools complete
```

then:

```text
3 / 4 = 75%
```

But if the report says:

> "Several spools completed."

you cannot safely calculate:

```text
75%
```

Therefore your module should preserve granular evidence and leave progress calculation to the progress engine where appropriate.

---

# 31. HARD MATCHING CASES

Your benchmark must contain difficult examples.

## Case 1 — Exact paraphrase

Schedule:

```text
Erect Line 24
```

Report:

```text
Line 24 erection completed.
```

---

## Case 2 — Different terminology

Schedule:

```text
Install pipe spool
```

Report:

```text
Spool fitted in position.
```

---

## Case 3 — Abbreviation

```text
24XX spool erect done
```

---

## Case 4 — Typos

```text
Spool ereciton completed
```

---

## Case 5 — Missing identifier

```text
Piping erection completed in Unit 4.
```

---

## Case 6 — Similar activities

```text
Erect Line 24
Erect Line 25
```

Report:

```text
Line 24 completed.
```

---

## Case 7 — Same name, different location

```text
Pipe installation — Unit 3
Pipe installation — Unit 4
```

Report:

```text
Pipe installation completed in Unit 4.
```

---

## Case 8 — Granularity mismatch

```text
Spool 1 complete
Spool 2 complete
Spool 3 pending
```

---

## Case 9 — Cross-discipline ambiguity

```text
Equipment installation
```

could potentially involve:

```text
Mechanical
Electrical
Instrumentation
```

---

# 32. SYNTHETIC DATASET

Because live project data is not available:

> Build a synthetic dataset resembling real project structures.

Start with:

```text
200–500 activities
```

and:

```text
300–1000 execution events
```

---

# 33. DATA STRUCTURE

Each schedule row should contain:

```text
activity_id
activity_name
wbs
level
discipline
location
planned_start
planned_finish
```

Each event:

```text
event_id
description
discipline
location
asset
date
status
ground_truth_activity_id
```

The `ground_truth_activity_id` is for evaluation only.

Do not expose it to the matcher.

---

# 34. GROUND TRUTH

You need a known correct answer for every test event.

Example:

```text
EVENT:
"Spool erection completed for Line 24."

Correct activity:
PIP-238
```

Therefore:

```text
Ground Truth = PIP-238
```

This allows objective evaluation.

---

# 35. BASELINE EXPERIMENT

You should compare approaches.

### Experiment 1

```text
Exact matching
```

### Experiment 2

```text
Fuzzy matching
```

### Experiment 3

```text
Embedding matching
```

### Experiment 4

```text
Embedding + context
```

### Experiment 5

```text
Embedding + context + confidence/review
```

This progression gives you a strong technical narrative.

---

# 36. EVALUATION METRICS

## Top-1 Accuracy

```text
Correct activity ranked #1
```

Example:

```text
100 test events

Correct first:
87

Accuracy:
87%
```

---

## Top-3 Recall

Suppose the correct activity appears in the top three.

```text
100 events
94 contain correct activity in top 3

Top-3 Recall:
94%
```

This is useful because human review can choose among candidates.

---

# 37. PRECISION

If your system says:

```text
100 automatic matches
```

and:

```text
93 are correct
```

then:

```text
Precision = 93%
```

---

# 38. FALSE AUTO-LINK RATE

This is particularly important.

If:

```text
100 events auto-linked
```

and:

```text
7 were wrong
```

then:

```text
False auto-link rate = 7%
```

A schedule system should care deeply about this.

---

# 39. REVIEW RATE

Example:

```text
100 events

70 auto-linked
20 reviewed
10 unmatched
```

Then:

```text
Auto-link rate = 70%
Review rate = 20%
Unmatched = 10%
```

The goal is not necessarily maximum automation.

The goal is:

> **Safe reduction of manual reconciliation effort.**

---

# 40. ERROR ANALYSIS

After testing, do not only report:

```text
Accuracy = 91%
```

Investigate failures.

Create categories:

```text
Wrong identifier
Wrong discipline
Similar activities
Missing location
Granularity mismatch
Bad extraction
Ambiguous wording
```

Then determine which failure category dominates.

This tells you what to improve.

---

# 41. VECTOR DATABASE

For a practical prototype:

```text
PostgreSQL
+
pgvector
```

Store:

```text
activity_id
activity_name
metadata
embedding
```

Then:

```text
ExecutionEvent
 ↓
Embedding
 ↓
Vector search
 ↓
Top-K candidates
```

---

# 42. EMBEDDING STORAGE

Conceptually:

```text
activity_id: PIP-238

text:
"Erect Line 24-XX Piping Unit 4"

embedding:
[0.12, -0.31, 0.44, ...]
```

The embedding can be generated once for the schedule and reused.

---

# 43. API CONTRACT

Your module can expose something like:

```text
POST /matches/run
```

Input:

```json
{
  "event_id": "EVT-001"
}
```

Output:

```json
{
  "event_id": "EVT-001",
  "candidates": [
    {
      "activity_id": "PIP-238",
      "confidence": 0.93
    },
    {
      "activity_id": "PIP-241",
      "confidence": 0.62
    }
  ],
  "decision": "auto_linked"
}
```

---

# 44. DEVELOPMENT PLAN

## Phase 1 — Understand

Learn:

```text
Text similarity
Embeddings
Cosine similarity
```

---

## Phase 2 — Basic Prototype

Build:

```text
Schedule CSV
+
Execution CSV
↓
Exact matching
```

---

## Phase 3 — Fuzzy

Add:

```text
Fuzzy matching
```

---

## Phase 4 — Embeddings

Add:

```text
Sentence Transformer
```

---

## Phase 5 — Candidate Retrieval

Add:

```text
Top-K retrieval
```

---

## Phase 6 — Context

Add:

```text
Discipline
Location
Identifier
WBS
```

---

## Phase 7 — Confidence

Add:

```text
Auto
Review
Unmatched
```

---

## Phase 8 — Granularity

Add:

```text
One-to-many
Many-to-one
Partial evidence
```

---

## Phase 9 — Evaluation

Build:

```text
Benchmark
Ground truth
Metrics
Error analysis
```

---

# 45. LEARNING PLAN

You do NOT need to learn all of AI.

Focus on these topics.

## Level 1

```text
Python
pandas
JSON
APIs
```

## Level 2

```text
Text normalization
String similarity
Fuzzy matching
```

## Level 3

```text
Embeddings
Sentence Transformers
Cosine similarity
```

## Level 4

```text
Vector databases
pgvector
Top-K retrieval
```

## Level 5

```text
Ranking
Hybrid scoring
Confidence
Precision
Recall
```

## Level 6

```text
Human-in-the-loop systems
Granularity
Entity resolution
```

---

# 46. WHAT YOU SHOULD NOT BUILD

Do not become responsible for:

```text
Frontend
PDF upload
Excel ingestion
Schedule parser
Voice transcription
Gantt
Analytics dashboard
Database administration
```

Your responsibility is:

```text
EVENT
 ↓
MATCH
 ↓
CONFIDENCE
```

You may coordinate with everyone, but do not absorb their modules.

---

# 47. YOUR RELATIONSHIP WITH ADITHYAN

Adithyan produces:

```text
ExecutionEvent
```

You consume it.

Example:

```text
Adithyan:

{
  "description":
  "Spool erection completed for Line 24",
  "discipline": "piping",
  "asset": "24"
}
```

You:

```text
PIP-238
Confidence 93%
```

The contract between you two must be frozen early.

---

# 48. YOUR RELATIONSHIP WITH YAZEEN

Yazeen provides:

```text
ScheduleActivity[]
```

You need:

```text
activity_id
activity_name
discipline
location
WBS
dates
dependencies
```

Without this standardized schedule representation, your matching system becomes unnecessarily difficult.

---

# 49. YOUR RELATIONSHIP WITH ADITHYANBALU

You provide:

```text
MatchResult
```

Adithyanbalu uses approved matches to calculate:

```text
actual progress
variance
status
analytics
```

You should not calculate final project progress.

---

# 50. YOUR RELATIONSHIP WITH ALIADNAN

Aliadnan needs your output for the UI:

```text
event
candidate
confidence
decision
explanation
```

Example:

```text
PIP-238
93%
Auto-linked
```

---

# 51. YOUR FIRST WORKING PROTOTYPE

Do NOT start with 50,000 activities.

Start with:

```text
20 activities
30 events
```

Example:

### Schedule

```text
PIP-101 — Erect Line 20
PIP-102 — Erect Line 24
PIP-103 — Weld Line 24
PIP-104 — Install Valve 24
```

### Event

```text
"Line 24 spool erection completed."
```

Expected:

```text
PIP-102
```

---

# 52. SECOND PROTOTYPE

Increase difficulty:

```text
100 activities
150 events
```

Add:

```text
paraphrases
typos
abbreviations
different word order
missing IDs
```

---

# 53. THIRD PROTOTYPE

Now add:

```text
500 activities
1000 events
```

and:

```text
Unit
Discipline
WBS
Asset IDs
Dates
```

Then test hybrid ranking.

---

# 54. FOURTH PROTOTYPE

Hard cases:

```text
Granularity mismatch
Ambiguous events
Similar activities
Missing identifiers
Cross-discipline descriptions
```

Now test:

```text
Auto-link
Review
Unmatched
```

---

# 55. RESEARCH / PAPER DIRECTION

Your module can form the strongest technical section of the project.

Possible research question:

> **Can hybrid semantic and schedule-context matching reliably map heterogeneous field execution descriptions to planned L5/L6 activities?**

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
Hybrid + Confidence
```

---

# 56. SECOND RESEARCH QUESTION

> **How should confidence thresholds balance automation against the risk of incorrect schedule updates?**

Experiment:

```text
Threshold 0.70
Threshold 0.80
Threshold 0.90
Threshold 0.95
```

Measure:

```text
Auto-link rate
Precision
False auto-link rate
Review rate
```

Then choose the operating point.

---

# 57. THIRD RESEARCH QUESTION

> **How can fine-grained field execution events be safely related to coarser planned activities?**

Test:

```text
1 activity
 ↓
4 spool events
```

and:

```text
3 field events
 ↓
1 planned activity
```

---

# 58. ACTIVE LEARNING — YOUR STRONGEST DIFFERENTIATOR

Every reviewer decision in SYNAPSE becomes a training signal.

This is **active learning applied to EPC domain matching**.

No existing EPC tool does this.

### How it works

When a reviewer approves or rejects a match:

```text
Reviewer APPROVES PIP-238 for event "spool erection Line 24"

        ↓

Feedback store:
{
  event_embedding: [...],
  features: {discipline: "piping", asset: "24", action: "erection"},
  approved_activity: "PIP-238",
  initial_score: 0.76
}

        ↓

Confidence recalibration:
Next similar event → PIP-238 boosted by +0.12 (learned from 10 past approvals)
```

### Minimum implementation (Day 1)

Simple lookup table:

```python
feedback_store = {
  ("piping", "24", "erection"): {"boosted_activity": "PIP-238", "boost": +0.15}
}
```

If a new event matches a known pattern, boost the historically-approved activity.

### Strong implementation (Week 2)

Contrastive fine-tuning of the embedding model using approved pairs (positive) and rejected pairs (negative).

The model learns that "spool erect" ≈ "erection" and "L24" ≈ "Line 24-XX" in the OIL INDIA domain vocabulary specifically.

### Why this matters for the demo

```text
Demo round 1:
"spool erection Line 24" → 76% → REVIEW (reviewer approves PIP-238)

Demo round 2 (after learning):
Similar event → 88% → AUTO-LINKED

Judge sees:
The system learned from the first decision and no longer needs human intervention.
```

This is the single most powerful demo moment in all of SYNAPSE.

---

# 59. STRONG PROJECT CLAIM

Do NOT say:

> "Our AI has 93% confidence."

Instead say:

> **"SYNAPSE's hybrid matcher combines seven scoring signals with an active learning feedback loop. Reviewer decisions continuously recalibrate confidence thresholds. The false auto-link rate decreases over time as the system learns Oil India's specific domain vocabulary and activity patterns."**

That is a 10/10 claim.

---

# 59. DEMO FLOW FOR YOUR MODULE

Judge sees:

```text
FIELD REPORT

"Piping crew completed spool erection
for Line 24 yesterday."
```

Your system extracts:

```text
Discipline: Piping
Asset: Line 24
Action: Spool erection
Status: Complete
Date: Yesterday
```

Then your matcher produces:

```text
TOP MATCH

PIP-238
Erect Line 24-XX

Semantic: 94%
Context: 92%
Final: 93%
```

Evidence:

```text
✓ Piping
✓ Line 24
✓ Unit 4
✓ Semantic similarity
```

Decision:

```text
AUTO-LINKED
```

Then the progress engine updates the schedule.

---

# 60. HARD DEMO CASE

Then intentionally give the system:

> "Pipe work completed in Unit 4."

The system should NOT pretend to know.

It should say:

```text
AMBIGUOUS

PIP-238 — 78%
PIP-241 — 75%
PIP-245 — 71%

Human review required.
```

This is an excellent demo moment.

It proves:

> **We designed the system not to hallucinate certainty.**

---

# 61. YOUR MODULE'S FINAL ARCHITECTURE

```text
                ExecutionEvent
                      │
                      ▼
                Normalization
                      │
                      ▼
             Identifier Extraction
                      │
                      ▼
               Embedding Model
                      │
                      ▼
                Vector Search
                      │
                      ▼
                  Top-K
                      │
                      ▼
             Contextual Ranking
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
   Semantic       Identifier      Context
       │              │              │
       └──────────────┼──────────────┘
                      ▼
                 Final Score
                      │
                      ▼
                 Confidence
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
        HIGH        MEDIUM        LOW
          │           │            │
          ▼           ▼            ▼
       AUTO-LINK    REVIEW      UNMATCHED
```

---

# 62. YOUR SUCCESS CRITERIA

Your module is successful if:

```text
✓ Correct activity usually ranks #1
✓ Correct activity usually appears in Top-K
✓ Context improves over embeddings alone
✓ False auto-links are controlled
✓ Ambiguous cases reach review
✓ Unmatched events are preserved
✓ Granularity is not ignored
✓ Every decision has evidence
✓ Results are reproducible
```

---

# 63. DEFINITION OF DONE

## Basic

- [ ] Schedule activities can be loaded.
- [ ] Execution events can be loaded.
- [ ] Exact baseline exists.
- [ ] Fuzzy baseline exists.
- [ ] Embeddings work.
- [ ] Cosine similarity works.

## Intermediate

- [ ] Top-K retrieval works.
- [ ] Identifier extraction works.
- [ ] Discipline context works.
- [ ] Location context works.
- [ ] WBS context works.
- [ ] Hybrid score works.

## Advanced

- [ ] Confidence threshold exists.
- [ ] Review routing exists.
- [ ] Unmatched routing exists.
- [ ] Explanations exist.
- [ ] Granularity is represented.
- [ ] Multiple events can map to one activity.
- [ ] Evaluation benchmark exists.
- [ ] Error analysis exists.

## Research

- [ ] Baselines compared.
- [ ] Hybrid method evaluated.
- [ ] Threshold experiment performed.
- [ ] False auto-link rate measured.
- [ ] Results documented.

---

# 64. FINAL MENTAL MODEL

Whenever you work on this module, remember:

```text
Adithyan:
"What happened?"

       ↓

YOU:
"Which planned activity did it correspond to?"

       ↓

Adithyanbalu:
"What does that mean for project progress?"

       ↓

Aliadnan:
"How do we show it to the user?"
```

Your module is the **bridge between the real world and the schedule**.

The objective is not maximum automation.

The objective is:

> **Correct automation when confidence is high, human intervention when confidence is uncertain, and zero silent loss of field information.**