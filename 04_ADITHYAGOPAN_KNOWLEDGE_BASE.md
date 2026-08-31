# SIH26122 — ADITHYAGOPAN
## Institutional Memory & Project Execution Knowledge Base

**Owner:** Adithyagopan  
**Module:** Historical execution knowledge  
**Priority:** Important  
**Depends on:** Verified matching/progress data  
**Feeds:** Future-project search and analytics

### What you build
Turn completed-project execution history into a searchable repository.

The SIH requirement is not only live tracking; it also wants hard-won project knowledge to survive project closure.

> What actually happened on previous projects, and what can future projects learn?

### Records to store
- project ID
- discipline
- activity ID
- activity description
- planned duration
- actual duration
- planned/actual dates
- variance
- location/system
- delay cause, when available
- source reference
- match confidence
- reviewer status

### Example
```json
{
  "project_id": "SYN-PROJECT-01",
  "activity_id": "PIP-L6-024",
  "activity": "Erect Line 24",
  "planned_duration_days": 5,
  "actual_duration_days": 7,
  "variance_days": 2,
  "delay_cause": "material availability",
  "record_quality": "verified"
}
```

### Architecture
```text
Verified match
      ↓
Progress / variance
      ↓
Historical record
      ↓
PostgreSQL
      ↓
Vector/search index
      ↓
Historical retrieval
```

### Useful questions
- How long did similar piping erection activities take?
- Which disciplines repeatedly experienced delays?
- What were common causes of delay?
- Show historical activities similar to this one.
- Which activities consistently exceeded baseline?
- What is the delay risk for this current activity type?
- What was the actual productivity (spools/day) for similar piping activities?
- Which contractor/crew historically performs erection activities fastest?

### Delay Risk Feed (feeds Adithyanbalu)

This is the knowledge base's most important forward-looking output.

For any current activity, the knowledge base can return:

```json
{
  "query_activity": "Erect Line 24-XX",
  "discipline": "piping",
  "action": "erection",
  "historical_matches": 23,
  "avg_planned_duration_days": 5.0,
  "avg_actual_duration_days": 7.2,
  "delay_frequency": 0.68,
  "common_delay_causes": [
    {"cause": "crane availability", "frequency": 0.42},
    {"cause": "material delay", "frequency": 0.31}
  ],
  "suggested_buffer_days": 2
}
```

This feeds Adithyanbalu's risk scoring engine.

No EPC tool provides this. SYNAPSE's historical knowledge base makes it possible.

### Productivity Benchmarking

Track real productivity rates from execution history:

```text
Piping erection — Oil India EPC projects:
  Avg: 3.2 spools/day per crew
  Best observed: 5.1 spools/day
  Worst observed: 1.4 spools/day

Current project PIP-238:
  Actual rate so far: 2.1 spools/day
  → Below historical average
  → Flag for planner attention
```

### Quality control
Do not let rejected or obviously corrupted records become trusted historical knowledge.

Use:
```text
verified
provisional
rejected
```

### Minimum version
- [ ] PostgreSQL schema
- [ ] historical activity table
- [ ] verified records inserted
- [ ] filters by discipline/project
- [ ] 3–5 useful historical queries

### Strong version
- [ ] pgvector
- [ ] semantic similarity search
- [ ] delay-cause aggregation
- [ ] discipline productivity summaries
- [ ] natural-language query layer

### Demo
```text
Project closes
      ↓
Verified execution history saved
      ↓
User asks:
"What usually delays piping erection?"
      ↓
Relevant historical records
      ↓
AI summary + supporting records
```

### Independence
You can build the database and retrieval layer using synthetic records before the rest of the backend is complete. Integrate later with verified outputs from Adithyanbalu and Amritha.
