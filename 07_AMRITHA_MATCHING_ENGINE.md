# SIH26122 — AMRITHA
## AI Semantic Matching, Confidence & Human Review Engine

**Owner:** Amritha  
**Module:** Core semantic matching layer  
**Priority:** Critical / Core differentiator  
**Depends on:** Adithyan's `ExecutionEvent` + Yazeen's `ScheduleActivity`  
**Feeds:** Adithyanbalu + Aliadnan + Adithyagopan

## 1. YOUR CORE QUESTION

> Which planned L5/L6 activity does this real-world execution event correspond to?

Example:
```text
FIELD:
"Spool erected on line 24."

PLAN:
"PIP-L6-024 — Erect Line 24"
```

Expected:
```text
Match: PIP-L6-024
Confidence: 0.94
Status: high-confidence / review
```

## 2. WHY THIS IS THE HEART OF THE PROJECT

The wording will rarely be identical.

```text
"spool erected"
vs
"Erect Line 24"

"tray installation completed"
vs
"Install cable tray in Area B"

"pump fitted"
vs
"Install P-204 rotating equipment"
```

The system needs semantic understanding without silently making dangerous matches.

## 3. RECOMMENDED ARCHITECTURE

```text
ExecutionEvent
      ↓
Candidate generation
      ↓
Embedding similarity
      ↓
Metadata-aware scoring
      ↓
Reranking
      ↓
Confidence + ambiguity check
      ↓
Auto-accept OR reviewer queue
```

## 4. CANDIDATE GENERATION

Use context to narrow candidates:
- discipline
- location
- asset/line/equipment identifier
- activity type
- WBS context

Then perform semantic retrieval.

## 5. EMBEDDINGS

A Sentence-Transformers model is a practical prototype.

Embed schedule context such as:
```text
activity name
+ discipline
+ location
+ asset
+ WBS context
```

Embed the execution event similarly.

Use cosine similarity for retrieval.

For larger datasets, PostgreSQL + pgvector is a strong option.

## 6. METADATA MATTERS

Pure semantic similarity is insufficient.

Example:
```text
Event: Install pump P-204

Candidate A: Install pump P-204
Candidate B: Install pump P-205
```

Asset identity should strongly affect ranking.

A prototype scoring concept:
```text
final_score =
  semantic_similarity
  + asset_match_bonus
  + location_match_bonus
  + discipline_match_bonus
  + activity_type_match_bonus
```

Tune weights experimentally; do not claim arbitrary weights are optimal.

## 7. CONFIDENCE THRESHOLDS

Use initial values only as a starting point:
```text
≥ 0.90 → high confidence
0.70–0.89 → review
< 0.70 → unmatched/review
```

Tune these using your synthetic test set.

### Critical principle
> A wrong automatic match is worse than an unmatched event.

Therefore low-confidence cases go to review.

## 8. TOP-K RESULTS

Return alternatives:
```json
{
  "event_id": "EVT-001",
  "candidates": [
    {"activity_id": "PIP-L6-024", "score": 0.94},
    {"activity_id": "PIP-L6-025", "score": 0.71}
  ],
  "decision": "high_confidence"
}
```

## 9. AMBIGUITY / SCORE MARGIN

If:
```text
Candidate 1 = 0.91
Candidate 2 = 0.90
```

the top score is high but the decision is ambiguous.

Calculate:
```text
margin = top_score - second_score
```

Small margin → reviewer queue.

## 10. HUMAN-IN-THE-LOOP

Planner actions:
```text
Approve
Reject
Choose another candidate
Mark as new/unplanned activity
```

Store the decision for the audit trail and future evaluation.

## 11. GRANULARITY MISMATCH

This is explicitly part of the SIH problem.

Plan:
```text
Install piping section A
```

Field:
```text
Spool 1 installed
Spool 2 installed
Spool 3 installed
```

Do not automatically create a new planned activity. Return the candidate plus partial-progress context.

## 12. UNMATCHED ACTIVITIES

If no candidate is reliable:
```text
UNMATCHED
```

Planner can classify it as:
```text
New activity
Missing schedule node
Wrong description
Insufficient information
```

## 13. ACTIVE LEARNING — THE KEY DIFFERENTIATOR

This is what separates SYNAPSE from any generic semantic search tool.

Every time a reviewer makes a decision, that decision becomes a training signal:

```text
Event: "Line 24 spool erection done."

Matcher: PIP-238 @ 76% → sent to REVIEW

Reviewer action: APPROVE PIP-238

        ↓

Feedback store records:
{
  "event_embedding": [...],
  "event_features": {
    "discipline": "piping",
    "asset": "24",
    "action_type": "erection"
  },
  "approved_activity": "PIP-238",
  "initial_confidence": 0.76,
  "reviewer": "planner_01"
}
```

The feedback store drives two improvements:

### Improvement A — Confidence Recalibration

If similar events keep being approved for the same activity, the threshold for auto-linking that activity type is lowered.

Before feedback:
```text
"spool erection Line 24" → 76% → REVIEW
```

After 10 similar approvals:
```text
"spool erection Line 24" → 76% → adjusted to 88% equivalent → AUTO-LINK
```

### Improvement B — Embedding Fine-Tuning (strong version)

Reviewer approvals form positive pairs.
Reviewer rejections form negative pairs.

These can be used to fine-tune the embedding model on domain vocabulary:

```text
Positive pair:
("spool erect L24", "Erect Line 24-XX")

Negative pair:
("spool erect L24", "Weld Line 24-XX")
```

This is contrastive learning applied to EPC domain vocabulary.

After fine-tuning:
- Domain abbreviations (L24, PIP-238, spool) are understood better.
- Hard negatives (Line 24 vs Line 25) are separated more clearly.

### Minimum version of active learning

Even without model fine-tuning, a simple lookup table is valuable:

```text
If (event_discipline == "piping"
    AND asset_match == "24"
    AND action == "erection"
    AND reviewer previously approved PIP-238 for this pattern):

        → Boost PIP-238 confidence by +0.15
```

This is rule-based active learning — implementable in Week 2.

## 14. LLM ROLE

Use embeddings for retrieval first.

A strong architecture is:
```text
Embedding retrieval
       ↓
Top 5 candidates
       ↓
LLM reranker
       ↓
Final ranking + explanation
```

Do not ask an LLM to blindly search a huge schedule.

## 14. EVALUATION DATASET

Build synthetic pairs:
```text
Event                         Correct activity
------------------------------------------------
Spool erected L24             PIP-L6-024
Spool erection line twenty4   PIP-L6-024
L24 erection completed        PIP-L6-024
Erect Line 25                 PIP-L6-025
```

Include hard negatives:
- L24 vs L25
- installation vs inspection
- Unit 4 vs Unit 5
- same name, different discipline
- similar equipment IDs

## 15. METRICS

Measure:
- Top-1 accuracy
- Top-3 recall
- false-match rate
- unmatched precision
- review rate
- confidence calibration

The most important safety metric is:
> False-positive matching rate.

## 16. API CONTRACT

Recommended:
```text
POST /matches
```

Output:
```json
{
  "event_id": "EVT-001",
  "best_match": "PIP-L6-024",
  "confidence": 0.94,
  "margin": 0.21,
  "decision": "high_confidence",
  "alternatives": []
}
```

## 17. DEVELOPMENT ORDER

1. Freeze schemas with Adithyan and Yazeen.
2. Build keyword baseline.
3. Build embedding matcher.
4. Add metadata-aware ranking.
5. Add top-k candidates.
6. Add thresholds.
7. Add ambiguity/margin logic.
8. Add reviewer feedback store (active learning — minimum version).
9. Add confidence recalibration based on feedback.
10. Add LLM reranking if useful.
11. Evaluate rigorously.
12. Add embedding fine-tuning on domain pairs if time allows (strong version).

## 18. MINIMUM VERSION

- [ ] embedding-based matching
- [ ] top-k candidates
- [ ] confidence
- [ ] thresholds
- [ ] unmatched state
- [ ] reviewer API
- [ ] evaluation dataset

## 19. STRONG VERSION

- [ ] pgvector
- [ ] metadata-aware ranking
- [ ] margin-based ambiguity
- [ ] LLM reranking
- [ ] feedback loop
- [ ] granularity handling
- [ ] calibrated confidence

## 20. CENTRAL DEMO

```text
"Spool erection completed on Line 24"
                 ↓
Semantic retrieval
                 ↓
PIP-L6-024 — Erect Line 24
                 ↓
94% confidence
                 ↓
Approve
                 ↓
Actual finish updated
                 ↓
+4 days variance
                 ↓
Historical execution record saved
```

This is the central technical story of SIH26122.
