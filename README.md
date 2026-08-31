# SYNAPSE
## Synchronized NLP Activity-to-Plan Scheduling Engine

**SIH 2026 | Problem Statement: SIH26122 | Organization: Oil India Limited | Theme: Smart Automation**

---

## What is SYNAPSE?

SYNAPSE is an AI-powered planning-to-execution bridge built for large-scale infrastructure and EPC (Engineering, Procurement, Construction) projects.

Infrastructure projects like Oil India's EPC operations use Primavera P6 or MS Project to plan thousands of activities. But actual site progress arrives as free-text daily reports, supervisor messages, and spreadsheets — using inconsistent terminology that no existing tool can automatically link to the correct planned activity.

Today, planners spend **3–5 hours per day** manually reconciling field reports against schedule activities, introducing a **24–72 hour update lag** and significant mis-linking errors. When projects close, all execution knowledge is lost.

> SYNAPSE closes this gap: it reads messy field data, understands what happened, links it to the right L5/L6 schedule activity with a confidence score, and learns from every human correction.

---

## The Problem in One Line

> A supervisor writes *"Line 24 spool erection done."* No existing tool can automatically find **PIP-238** in a 5000-activity schedule, verify the match, update the actual finish date, and warn that this activity type historically delays 68% of the time.

SYNAPSE can.

---

## What Makes SYNAPSE Different

| What exists today | What SYNAPSE does |
|---|---|
| Primavera requires exact activity IDs — manual entry | Reads free-text, extracts structured events automatically |
| No NLP in any EPC scheduling tool | Seven-layer hybrid AI matching engine |
| Ambiguous reports silently mislinked | Agentic clarification asks the supervisor before guessing |
| AI systems that match but never improve | Active learning: reviewer corrections improve future matching |
| No detection of conflicting multi-source reports | Multi-source conflict detection and flagging |
| Historical data lost when projects close | Institutional memory with delay risk intelligence |

---

## System Architecture

```
SUPERVISOR TYPES/SPEAKS
        ↓
SYNAPSE AGENTIC CLARIFICATION (asks if ambiguous)
        ↓
STRUCTURED EXECUTION EVENT EXTRACTED
        ↓
MULTI-SOURCE CONFLICT CHECK
        ↓
SEVEN-LAYER HYBRID MATCHING ENGINE
  ├── Semantic embedding similarity
  ├── Asset/Line identifier matching
  ├── Discipline matching
  ├── Location matching
  ├── WBS context
  ├── Temporal fit
  └── Dependency context
        ↓
CONFIDENCE SCORE
  ├── HIGH  → AUTO-LINKED (schedule updates immediately)
  ├── MED   → Human review queue (with evidence ticks)
  └── LOW   → Unmatched (flagged for investigation)
        ↓
ACTIVE LEARNING (reviewer decisions improve future matching)
        ↓
SCHEDULE UPDATE + AUDIT TRAIL
        ↓
DELAY RISK INTELLIGENCE (from historical patterns)
        ↓
INSTITUTIONAL MEMORY (searchable for future projects)
```

---

## The Three Core Differentiators

### 1. Active Learning Feedback Loop
Every reviewer decision (approve / reject / reroute) feeds back into the matching engine. Confidence thresholds are recalibrated. The system gets smarter with every use — reducing the review queue load over time.

### 2. Agentic Clarification at Input
When a report is ambiguous, SYNAPSE does not silently return low-confidence results. It asks the supervisor a targeted question at the point of data entry:
> *"I found 3 erection activities in your area. Which line — (a) Line 24-XX, (b) Line 25-XX?"*

The ambiguity is resolved in seconds, not hours later in a planner's queue.

### 3. Historical Delay Risk Intelligence
Verified execution history from past projects powers forward-looking risk alerts:
> *"PIP-238 is HIGH RISK. Similar piping erection activities historically delay 68% of the time. Common cause: crane availability. Suggested buffer: 2 days."*

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Pydantic |
| LLM Extraction | LLM API (structured output) |
| Embedding Matching | Sentence Transformers |
| Vector Search | PostgreSQL + pgvector |
| Data Processing | pandas, openpyxl, PDF parser |
| Frontend | React |
| Active Learning Store | PostgreSQL |

---

## Team & Module Ownership

| Member | Module | Responsibility |
|---|---|---|
| **Amritha** | Matching Engine | Hybrid semantic + context matching, confidence scoring, active learning |
| **Adithyan** | Event Extraction | Heterogeneous data ingestion, NLP extraction, agentic clarification |
| **Yazeen** | Schedule Parser | Primavera/MS Project → standardized ScheduleActivity format |
| **Adithyagopan** | Knowledge Base | Institutional memory, delay risk intelligence, productivity benchmarking |
| **Adithyanbalu** | Progress Analytics | Variance calculation, risk scoring, conflict detection |
| **Aliadnan** | Frontend | Supervisor input, review queue, Gantt, conflict alerts, risk dashboard |

---

## Repository Structure

```
/
├── README.md                              — This file
├── SIH26122 — COMPLETE PROJECT GUIDE.md  — Full system design and architecture
├── SIH26122 — AMRITHA'S MODULE.md        — Matching engine detailed spec
├── SIH26122 — ADITHYAN'S MODULE.md       — Event extraction detailed spec
├── 03_YAZEEN_SCHEDULE_PARSER.md          — Schedule parser spec
├── 04_ADITHYAGOPAN_KNOWLEDGE_BASE.md     — Knowledge base spec
├── 05_ADITHYANBALU_PROGRESS_ANALYTICS.md — Progress engine spec
├── 06_ALIADNAN_FRONTEND_AUDIT.md         — Frontend spec
├── 07_AMRITHA_MATCHING_ENGINE.md         — Matching engine quick reference
├── SIH2026-IDEA-Presentation-Format.pptx — Presentation template
└── SIH PPT guidelines.pdf                — SIH 2026 guidelines
```

---

## Demo Scenario

A judge sees:

1. Supervisor types: *"Erection completed today."*
2. SYNAPSE: *"Which line — (a) Line 24-XX (b) Line 25-XX?"*
3. Supervisor: *"a"*
4. SYNAPSE extracts event → matches PIP-238 at **93% confidence**
5. Evidence shown: ✓ Piping ✓ Line 24 ✓ Unit 4 ✓ Semantic similarity
6. Status: **AUTO-LINKED** — schedule updates, Gantt changes
7. Risk Dashboard: *"PIP-238 — HIGH RISK — 68% historical delay rate"*
8. Audit trail records the full chain from raw input to schedule update

That is a complete story in under 30 seconds.

---

## SIH 2026 Alignment

- **Theme:** Smart Automation
- **Pipeline:** Real-world data → Intelligence → Decision → Action → Impact
- **Not a dashboard** — a complete end-to-end intelligent system
- **Agentic AI:** Clarification agent resolves ambiguity at source
- **Data Fusion:** Free-text reports + Excel sheets + PDFs fused together
- **Domain-specific:** Oil India Limited EPC terminology and workflow
- **Measurable:** Top-1 accuracy, false auto-link rate, review rate, variance days saved

---

*SYNAPSE — Built for SIH 2026 by Team from Amrita Vishwa Vidyapeetham, Amritapuri Campus*
