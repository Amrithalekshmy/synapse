# SIH26122 — YAZEEN
## Primavera / MS Project Schedule Parser & Standardization

**Owner:** Yazeen  
**Module:** Schedule ingestion and normalization  
**Priority:** Critical  
**Depends on:** None initially  
**Feeds:** Amritha's matching engine

### What you build
Convert Primavera P6 / MS Project exports into one standardized `ScheduleActivity` format. Your job is to answer:

> What activities are planned, what are their official L5/L6 IDs, and what baseline dates/context belong to them?

### Pipeline
```text
P6 / MS Project export
        ↓
Format parser
        ↓
Field normalization
        ↓
WBS reconstruction
        ↓
L5/L6 filtering
        ↓
ScheduleActivity[]
        ↓
Amritha's matching engine
```

### Output contract
```json
{
  "activity_id": "PIP-L6-024",
  "activity_name": "Erect Line 24",
  "wbs_id": "L5-PIP-02",
  "wbs_level": 6,
  "discipline": "piping",
  "planned_start": "2026-08-20",
  "planned_finish": "2026-08-24",
  "duration_days": 5,
  "predecessors": [],
  "location": "Unit 4",
  "status": "planned"
}
```

### Rules
1. Preserve the original activity ID exactly.
2. Preserve original activity name alongside normalized text.
3. Preserve WBS hierarchy/context.
4. Keep planned dates separate from actual dates.
5. Do not decide whether a field report matches an activity.
6. Do not own final delay analytics.

### Data-quality checks
Flag:
- missing IDs
- duplicate IDs
- invalid dates
- finish before start
- missing activity names
- missing WBS context
- non-L5/L6 rows

### Minimum version
- [ ] Parse one synthetic schedule format.
- [ ] Extract L5/L6 activities.
- [ ] Preserve IDs.
- [ ] Extract planned start/finish.
- [ ] Extract discipline/location where available.
- [ ] Preserve WBS context.
- [ ] Return JSON/API output.

### Strong version
- [ ] Primavera + MS Project support
- [ ] automatic format detection
- [ ] WBS reconstruction
- [ ] schedule-version handling
- [ ] data-quality report
- [ ] normalized search fields

### Development order
1. Freeze `ScheduleActivity` schema.
2. Build parser for the simplest synthetic export.
3. Validate IDs and dates.
4. Reconstruct WBS.
5. Add second format.
6. Add quality checks.
7. Freeze API contract.

### Handoff
Your only job in the integration is to give Amritha clean `ScheduleActivity[]`. She should never need to understand XER/XML parsing.
