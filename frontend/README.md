# SYNAPSE — Frontend, Reviewer Queue & Audit Trail

**Module 06 · Owner: Aliadnan**

The user-facing half of SYNAPSE: `server.py` (integration API) plus this
`frontend/` directory (the UI it serves).

---

## Run it

```bash
pip install -r requirements.txt
python server.py            # or: uvicorn server:app
```

- UI → <http://127.0.0.1:8000/>
- API docs → <http://127.0.0.1:8000/docs>

First boot takes ~15 s: the schedule is parsed, the sentence-transformer model
loads, and the historical knowledge base is read into memory.

---

## Why there is no `npm install`

The spec calls for React. This ships as plain HTML/CSS/JS served by FastAPI
instead, and that was a deliberate call:

- **No Node on the demo machine.** `node` and `npm` are not installed. A build
  step is one more thing that can fail an hour before judging.
- **No CDN dependency.** A React-from-CDN page is dead if the venue wifi is.
  Everything here is served from the same process as the API.
- **One command to run the whole system.** `python server.py` starts the API and
  the UI together. No second terminal, no proxy config, no CORS surprises.

The architectural rule that actually matters — *no AI logic in the client* — is
kept strictly. `app.js` contains no extraction, scoring or matching code. Every
number it renders arrived from a backend module that owns it. Migrating to React
later means rewriting the render functions against the same API; nothing else.

```
frontend/
├── index.html   view shells, one <section> per screen
├── styles.css   design system (tokens, confidence bands, gantt, chain)
└── app.js       fetch + render, one loader per screen
```

---

## API contract

The spec fixed the ownership boundaries, not the names. These are the names.

| Screen | Endpoint |
|---|---|
| 0 · Supervisor input | `POST /api/supervisor/message` → `POST /api/supervisor/clarify` |
| 1 · Upload / ingest | `POST /api/events/upload`, `POST /api/events/extract`, `POST /api/events/load-sample`, `GET /api/demo/sources` |
| 2 · Extracted events | `GET /api/events`, `GET /api/events/{id}` |
| 3 · Review queue | `GET /api/matches/queue`, `POST /api/matches/{event_id}/review`, `GET /api/activities` |
| 4 · Conflicts | `GET /api/conflicts`, `POST /api/conflicts/{id}/resolve` |
| 5 · Schedule / Gantt | `GET /api/schedule`, `GET /api/progress` |
| 6 · Risk dashboard | `GET /api/risk`, `GET /api/risk/{activity_id}/evidence`, `GET /api/productivity` |
| 7 · History search | `GET /api/history/search?q=` |
| 8 · Audit trail | `GET /api/audit`, `GET /api/audit/event/{event_id}` |
| — | `GET /api/health`, `POST /api/session/reset` |

### Who computes what

`server.py` is a backend-for-frontend. It orchestrates and shapes; it does not
decide.

| Concern | Owner | Called as |
|---|---|---|
| Free text / CSV / PDF → `ExecutionEvent` | Adithyan | `ExtractionPipeline.process_file / process_text` |
| Ambiguity detection & the question to ask | Adithyan | `generate_clarification`, `apply_clarification` |
| Schedule file → `ScheduleActivity` | Yazeen | `ScheduleParser.parse` |
| Event → activity, confidence, evidence | Amritha | `SynapseMatchingEngine.process_event` |
| Reviewer correction → future matching | Amritha | `record_feedback` |
| Confidence → auto / review / reject | Adithyanbalu | `get_review_decision` |
| Planned vs actual variance | Adithyanbalu | `calculate_finish_variance` |
| Project rollup, schedule risk | Adithyanbalu | `calculate_project_summary`, `calculate_risk` |
| Status contradiction between two claims | Adithyanbalu | `detect_status_conflict` |
| Historical delay risk & buffer | Adithyagopan | `DelayRiskEngine.assess` |
| Natural-language history query | Adithyagopan | `NLQueryEngine.query` |

What this layer genuinely adds, because no other module owns it: grouping claims
into multi-source conflicts, the reviewer queue, the audit trail, and the
schedule state that results from a human decision.

---

## Two UX rules the code enforces

**1 · Never hide uncertainty.** No screen says "matched successfully". Every
machine claim carries a confidence bar, a HIGH/MEDIUM/LOW band, and the evidence
ticks behind it (`✓ discipline`, `✓ identifier`, `✓ temporal`, …) drawn from the
matching engine's own explanation payload. A delay rate computed from three
historical records says so next to the number, not in a footnote.

**2 · No number without a source.** An activity with no linked field event shows
an empty actual and an empty variance — never an assumption. Every actual date
in the schedule table links back through `Trace` to the raw sentence it came
from, and every risk verdict opens to the historical records underneath it.

Two places where this rule shaped the design:

- **The Gantt draws no "actual" bar.** A completed report tells you when work
  *ended*, not when it started, so an actual bar would render a duration nobody
  reported. Instead it draws the planned window, a hatched *slip* between the
  planned and reported finish, and a marker on the reported date itself.
- **A human-verified link is not shown as a confidence score.** When the
  supervisor picks the activity, that is a fact, not a 43% guess — so the
  console says "confirmed by you" and discloses the engine's own ranking on the
  next line rather than presenting it as the system's certainty.

## Two kinds of conflict

| Kind | Trigger |
|---|---|
| `same_day` | Two sources describe the same activity on the same date with different statuses. |
| `state_regression` | A later report walks back an activity an earlier source already recorded as complete — the spec's supervisor case, invisible to same-day grouping because the reports are days apart. |

`detect_status_conflict` (Adithyanbalu) decides whether a pair is a hard
contradiction; the wording is rewritten here because his message is phrased for
schedule-vs-execution and the planner is looking at source-vs-source.

The bundled sample sources genuinely agree with each other, so the conflict
screen is empty until you create a real contradiction — ingest a daily report,
then report that same activity as blocked from **Supervisor input**. The empty
state on that screen explains this rather than looking broken.

---

## Demo script (~90 seconds)

1. **Supervisor** — type `Erection completed today.` SYNAPSE asks which line
   instead of guessing. Answer `PIP-002`. It links and the schedule moves.
2. **Ingest** — process `DPR_2026_08_28.txt`, then
   `discipline_report_piping.csv`. Note the counters: events detected, auto-linked,
   needing review, **conflicts detected**.
3. **Conflicts** — the same activity, the same day, two sources disagreeing.
   Pick which one to trust. The decision is recorded.
4. **Review queue** — approve, reject or reassign. The "corrections learned"
   counter in the top bar climbs with each one.
5. **Schedule** — planned vs actual bars, variance in days, evidence per row.
6. **Risk** — the highest-risk unfinished activities with their historical delay
   rate and suggested buffer. Open the evidence.
7. **Audit** — the whole run, in order, with who did what.

`Reset session` clears the run and keeps the schedule, so the demo can be given
twice in a row.

---

## Tests

```bash
python -m pytest tests/test_server_integration.py -q
```

These cover the seams between modules — routing buckets adding up, actuals
appearing only where evidence exists, corrections reaching the matcher's feedback
store, superseded claims after a conflict decision, audit ordering — rather than
re-testing logic each module already covers.
