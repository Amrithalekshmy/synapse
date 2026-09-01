/* =========================================================================
   SYNAPSE — frontend application
   Module 06 · Aliadnan

   Deliberately zero-build: no npm, no bundler, no CDN. The demo machine needs
   Python and a browser, nothing else, and it works with the venue wifi down.

   This file contains NO extraction, matching or scoring logic. Every number on
   screen came from a backend module that owns it. The only intelligence here is
   about how to show uncertainty honestly.
   ========================================================================= */

const API = '';

const VIEWS = [
  { id: 'supervisor', step: '0', label: 'Supervisor input' },
  { id: 'ingest',     step: '1', label: 'Upload & ingest' },
  { id: 'events',     step: '2', label: 'Extracted events' },
  { id: 'review',     step: '3', label: 'Review queue',     badge: 'in_review_queue' },
  { id: 'conflicts',  step: '4', label: 'Conflicts',        badge: 'open_conflicts' },
  { id: 'schedule',   step: '5', label: 'Schedule & Gantt' },
  { id: 'risk',       step: '6', label: 'Risk intelligence' },
  { id: 'history',    step: '7', label: 'Institutional memory' },
  { id: 'audit',      step: '8', label: 'Audit trail' },
];

const state = {
  view: 'supervisor',
  progress: {},
  pendingClarification: null,
  supervisorEventId: null,
};

/* ------------------------------------------------------------------ utils */

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (html !== undefined) node.innerHTML = html;
  return node;
};

/** Everything user- or backend-supplied goes through this before innerHTML. */
function esc(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let message = res.statusText;
    try { message = (await res.json()).detail || message; } catch { /* keep statusText */ }
    throw new Error(message);
  }
  return res.json();
}

let toastTimer;
function toast(message, isError = false) {
  const node = $('#toast');
  node.className = 'toast' + (isError ? ' err' : '');
  node.innerHTML = esc(message);
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 4200);
}

const pct = (value) => value === null || value === undefined ? '—' : Math.round(value * 100) + '%';

/** ISO timestamp -> local clock time a planner can read at a glance. */
function clock(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso || '';
  const today = new Date().toDateString() === d.toDateString();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    + (today ? '' : ' · ' + d.toLocaleDateString([], { day: 'numeric', month: 'short' }));
}
const bandOf = (conf) => conf >= 0.85 ? 'high' : conf >= 0.65 ? 'medium' : 'low';
const dash = (value) => value === null || value === undefined || value === '' ? '—' : esc(value);

function meter(confidence) {
  if (confidence === null || confidence === undefined) return '<span class="faint">—</span>';
  const width = Math.min(100, Math.max(0, confidence * 100));
  const band = bandOf(confidence);
  return `<div class="meter">
    <div class="meter-track"><div class="meter-fill ${band}" style="width:${width}%"></div></div>
    <span class="meter-value">${pct(confidence)}</span>
  </div>`;
}

const LINK_STATE_BADGE = {
  auto_linked:         ['high',   'AUTO-LINKED'],
  approved:            ['high',   'APPROVED'],
  pending_review:      ['medium', 'NEEDS REVIEW'],
  clarification_needed:['violet', 'NEEDS CLARIFICATION'],
  unmatched:           ['low',    'UNMATCHED'],
  rejected:            ['low',    'REJECTED'],
  superseded:          ['mute',   'SUPERSEDED'],
};

function linkBadge(linkState) {
  const [cls, label] = LINK_STATE_BADGE[linkState] || ['mute', String(linkState || '').toUpperCase()];
  return `<span class="badge ${cls}">${label}</span>`;
}

/** Evidence ticks — the seven-layer signals behind a match. */
function evidenceTicks(explanation) {
  const signals = (explanation && explanation.evidence) || [];
  if (!signals.length) return '';
  return `<div class="evidence">` + signals.map((s) =>
    `<span class="tick" title="${esc(s.detail)}">✓ ${esc(String(s.signal).replace(/_/g, ' '))}</span>`
  ).join('') + `</div>`;
}

/* ------------------------------------------------------------------- nav */

function renderNav() {
  const nav = $('#nav');
  nav.innerHTML = '<div class="nav-group">Pipeline</div>';
  VIEWS.forEach((view) => {
    const button = el('button', 'nav-item' + (state.view === view.id ? ' active' : ''));
    button.innerHTML = `<span class="nav-step">${view.step}</span><span>${esc(view.label)}</span>`;
    if (view.badge) {
      const count = state.progress[view.badge] || 0;
      const badge = el('span', 'nav-badge', String(count));
      badge.hidden = count === 0;
      button.appendChild(badge);
    }
    button.onclick = () => show(view.id);
    nav.appendChild(button);
  });
}

const LOADERS = {
  supervisor: () => {},
  ingest:    loadSamples,
  events:    loadEvents,
  review:    loadReview,
  conflicts: loadConflicts,
  schedule:  loadSchedule,
  risk:      loadRisk,
  history:   () => {},
  audit:     loadAudit,
};

function show(viewId) {
  if (!VIEWS.some((v) => v.id === viewId)) viewId = VIEWS[0].id;
  state.view = viewId;
  VIEWS.forEach((v) => { $('#view-' + v.id).hidden = v.id !== viewId; });
  renderNav();
  if (location.hash.slice(1) !== viewId) location.hash = viewId;
  (LOADERS[viewId] || (() => {}))();
  $('#main').scrollTop = 0;
}

// Deep links and the browser back button both work: /#risk opens the risk screen.
window.addEventListener('hashchange', () => {
  const target = location.hash.slice(1);
  if (target && target !== state.view) show(target);
});

/* --------------------------------------------------------------- vitals */

async function loadProgress() {
  try {
    state.progress = await api('/api/progress');
  } catch (error) {
    toast('Backend unreachable: ' + error.message, true);
    return;
  }
  const p = state.progress;
  const vitals = [
    { label: 'Events ingested', value: p.events_ingested },
    { label: 'Auto-linked',     value: p.auto_linked + p.approved, cls: 'good' },
    { label: 'In review',       value: p.in_review_queue, cls: p.in_review_queue ? 'warn' : '' },
    { label: 'Open conflicts',  value: p.open_conflicts, cls: p.open_conflicts ? 'alert' : '' },
    { label: 'Progress',        value: (p.overall_progress_percent ?? 0) + '%' },
    { label: 'Avg variance',    value: (p.average_variance_days ?? 0) + 'd',
      cls: p.average_variance_days > 0 ? 'warn' : '' },
    { label: 'Corrections learned', value: p.corrections_learned },
  ];
  $('#vitals').innerHTML = vitals.map((v) =>
    `<div class="vital ${v.cls || ''}">
       <div class="vital-value">${esc(v.value)}</div>
       <div class="vital-label">${esc(v.label)}</div>
     </div>`).join('');
  renderNav();
}

/* ------------------------------------------------- 0 · supervisor console */

function consoleLine(cls, text) {
  const node = el('div', 'line ' + cls, esc(text));
  $('#console').appendChild(node);
  $('#console').scrollTop = $('#console').scrollHeight;
  return node;
}

async function sendSupervisor(text) {
  if (!text.trim()) return;
  $('#sup-input').value = '';
  consoleLine('user', text);
  const busy = consoleLine('system', 'reading…');

  try {
    let result;
    if (state.pendingClarification) {
      result = await api('/api/supervisor/clarify', {
        method: 'POST',
        body: JSON.stringify({ event_id: state.pendingClarification, answer: text }),
      });
      state.pendingClarification = null;
    } else {
      result = await api('/api/supervisor/message', {
        method: 'POST',
        body: JSON.stringify({ text }),
      });
    }
    busy.remove();

    if (result.needs_clarification) {
      state.pendingClarification = result.event_id;
      consoleLine('system', result.question);
      const options = result.options || [];
      const group = el('div', 'option-group');
      options.forEach((option, index) => {
        const label = String.fromCharCode(97 + index);
        const button = el('button', 'option-btn', `(${label})  ${esc(option)}`);
        button.onclick = () => {
          // Once answered these options are history, not live controls —
          // leaving them clickable would fire a stale question as a new report.
          group.querySelectorAll('.option-btn').forEach((b) => {
            b.disabled = true;
            b.classList.add('spent');
          });
          button.classList.add('chosen');
          sendSupervisor(option);
        };
        group.appendChild(button);
      });
      $('#console').appendChild(group);
      if (!options.length) consoleLine('system', 'Type your answer below.');
      $('#console').scrollTop = $('#console').scrollHeight;
      return;
    }

    const event = result.event;
    state.supervisorEventId = event.event_id;

    if (!event.matched_activity_id) {
      consoleLine('err', 'No confident match found — sent to the planner queue for investigation.');
    } else {
      const target = `${event.matched_activity_id} — ${event.matched_activity_name}`;
      if (event.link_state === 'approved') {
        // You told SYNAPSE which activity this was. That is a verified fact,
        // not a guess — so it does not get reported as a confidence score.
        // The engine's own ranking is still shown, because hiding it would
        // hide how much work the clarification actually did.
        consoleLine('ok', `Linked to ${target}. Confirmed by you — schedule updated.`);
        consoleLine('system',
          `For the record: on the text alone the engine ranked this ${pct(event.match_confidence)}. ` +
          `Your answer is what settled it, and it is now training the matcher.`);
      } else if (event.link_state === 'auto_linked') {
        consoleLine('ok',
          `Linked to ${target} at ${pct(event.match_confidence)} confidence ` +
          `(${event.confidence_band}). Auto-linked — schedule updated.`);
      } else {
        consoleLine('ok',
          `Best match ${target} at ${pct(event.match_confidence)} ` +
          `(${event.confidence_band}) — below the auto-link threshold, so it is ` +
          `in the planner review queue rather than on the schedule.`);
      }
    }
    await loadProgress();
    await loadSupervisorChain(event.event_id);
  } catch (error) {
    busy.remove();
    consoleLine('err', error.message);
  }
}

async function loadSupervisorChain(eventId) {
  try {
    const data = await api('/api/audit/event/' + encodeURIComponent(eventId));
    $('#sup-chain').innerHTML = chainHtml(data.chain);
  } catch { /* the console already told the story */ }
}

function chainHtml(entries) {
  if (!entries || !entries.length) return '<div class="empty">Nothing recorded yet.</div>';
  return entries.map((entry) => `
    <div class="chain-node stage-${esc(entry.stage)}">
      <div class="chain-stage">${esc(entry.stage.replace(/_/g, ' '))}
        · <span class="faint">${esc(entry.actor)}</span></div>
      <div>${esc(entry.summary)}</div>
      <div class="tiny faint mono">${esc(clock(entry.timestamp))}</div>
    </div>`).join('');
}

/* ------------------------------------------------------------ 1 · ingest */

async function loadSamples() {
  if ($('#sample-list').dataset.loaded) return;
  const data = await api('/api/demo/sources');
  $('#sample-list').innerHTML = '';
  data.sources.forEach((source) => {
    const row = el('div', 'candidate');
    row.innerHTML = `<div class="candidate-name">
        <div class="mono">${esc(source.name)}</div>
        <div class="tiny faint">${esc(source.kind)}</div>
      </div>`;
    const button = el('button', 'btn sm', 'Process');
    button.onclick = async () => {
      button.disabled = true;
      button.innerHTML = '<span class="busy"></span>';
      try {
        const result = await api('/api/events/load-sample?path=' + encodeURIComponent(source.path),
          { method: 'POST' });
        showIngestResult(result);
        await loadProgress();
      } catch (error) {
        toast(error.message, true);
      } finally {
        button.disabled = false;
        button.textContent = 'Process';
      }
    };
    row.appendChild(button);
    $('#sample-list').appendChild(row);
  });
  $('#sample-list').dataset.loaded = '1';
}

function showIngestResult(result) {
  $('#ingest-result').hidden = false;
  const conflicts = result.conflicts_detected;
  $('#ingest-summary').innerHTML = `
    <div class="stat-row">
      <div><div class="stat-value">${result.events_detected}</div><div class="stat-label">events detected</div></div>
      <div><div class="stat-value" style="color:var(--high)">${result.auto_linked}</div><div class="stat-label">auto-linked</div></div>
      <div><div class="stat-value" style="color:var(--medium)">${result.needs_review}</div><div class="stat-label">need review</div></div>
      <div><div class="stat-value" style="color:var(--violet)">${result.needs_clarification}</div><div class="stat-label">ambiguous</div></div>
      <div><div class="stat-value" style="color:var(--text-faint)">${result.unmatched}</div><div class="stat-label">unmatched</div></div>
      <div><div class="stat-value" style="color:${conflicts ? 'var(--low)' : 'var(--text-faint)'}">${conflicts}</div><div class="stat-label">conflicts detected</div></div>
    </div>
    <p class="tiny faint">Source: ${esc(result.source)} · processed in ${esc(result.processing_time_ms)} ms</p>
    ${(result.warnings || []).map((w) => `<div class="badge medium">${esc(w)}</div>`).join(' ')}
    <div class="row" style="margin-top:12px">
      <button class="btn sm" onclick="show('events')">See extracted events</button>
      <button class="btn sm" onclick="show('review')">Open review queue</button>
      ${conflicts ? `<button class="btn sm danger" onclick="show('conflicts')">Resolve ${conflicts} conflict(s)</button>` : ''}
    </div>`;
}

/* ------------------------------------------------------------ 2 · events */

async function loadEvents() {
  const filter = $('#events-filter').value;
  const data = await api('/api/events' + (filter ? '?link_state=' + filter : ''));
  $('#events-count').textContent = `${data.count} event(s)`;

  if (!data.count) {
    $('#events-table').innerHTML =
      '<div class="empty">No events yet. Ingest a report first.</div>';
    return;
  }

  const rows = data.events.map((event) => `
    <tr>
      <td>
        <div class="quote tiny">${esc(event.raw_text)}</div>
        <div class="tiny faint mono" style="margin-top:4px">${esc(event.event_id)} · ${esc(event.source_id)}</div>
      </td>
      <td>${dash(event.description)}</td>
      <td>${event.discipline ? `<span class="badge mute">${esc(event.discipline)}</span>` : '<span class="faint">—</span>'}</td>
      <td class="mono">${dash(event.asset)}</td>
      <td class="mono">${dash(event.event_date)}</td>
      <td><span class="badge ${event.status === 'completed' ? 'high' : event.status === 'blocked' ? 'low' : 'info'}">${dash(event.status)}</span></td>
      <td>${meter(event.extraction_confidence)}</td>
      <td>${meter(event.match_confidence)}</td>
      <td>${linkBadge(event.link_state)}<div class="tiny mono faint">${dash(event.matched_activity_id)}</div></td>
      <td><button class="btn sm ghost" onclick="openChain('${esc(event.event_id)}')">Trace</button></td>
    </tr>`).join('');

  $('#events-table').innerHTML = `<div class="table-wrap"><table>
    <thead><tr>
      <th>Original text</th><th>Understood as</th><th>Discipline</th><th>Asset</th>
      <th>Date</th><th>Status</th><th>Extraction</th><th>Match</th><th>Link</th><th></th>
    </tr></thead><tbody>${rows}</tbody></table></div>`;
}

/* ------------------------------------------------------------ 3 · review */

async function loadReview() {
  const data = await api('/api/matches/queue');
  $('#review-thresholds').innerHTML =
    `Auto-link at <b>${pct(data.auto_threshold)}</b><span class="arrow">·</span>` +
    `review between <b>${pct(data.review_threshold)}</b> and <b>${pct(data.auto_threshold)}</b>` +
    `<span class="arrow">·</span>below that, unmatched`;

  const list = $('#review-list');
  if (!data.count) {
    list.innerHTML = '<div class="empty">Queue is clear. Every event was linked with high confidence.</div>';
    return;
  }

  list.innerHTML = '';
  data.queue.forEach((event) => {
    const card = el('div', 'card ' + (event.link_state === 'unmatched' ? 'danger' : 'attention'));
    const top = event.candidates && event.candidates[0];
    // An ambiguous event has candidates but no chosen one — there is nothing to
    // "approve", only a candidate to pick. Gate the button on the choice, not
    // on the existence of candidates.
    const approvable = Boolean(event.matched_activity_id);

    card.innerHTML = `
      <div class="card-head">
        <div style="flex:1;min-width:0">
          <div class="section-label">Field event · ${esc(event.source_id)}</div>
          <div class="quote">${esc(event.raw_text)}</div>
        </div>
        ${linkBadge(event.link_state)}
      </div>

      <div class="row tiny dim" style="margin-bottom:12px">
        ${event.discipline ? `<span class="badge mute">${esc(event.discipline)}</span>` : ''}
        ${event.asset ? `<span class="badge mute">${esc(event.asset)}</span>` : ''}
        ${event.location ? `<span class="badge mute">${esc(event.location)}</span>` : ''}
        ${event.event_date ? `<span class="badge mute">${esc(event.event_date)}</span>` : ''}
        <span class="faint">extraction ${pct(event.extraction_confidence)}</span>
      </div>

      ${event.clarification ? `
        <div class="section-label">SYNAPSE asks</div>
        <div class="badge violet" style="margin-bottom:10px">${esc(event.clarification.question)}</div>` : ''}

      <div class="section-label">${top ? 'Top match' : 'No candidate above threshold'}</div>
      ${(event.candidates || []).map((candidate, index) => `
        <div class="candidate ${index === 0 ? 'top' : ''}">
          <span class="mono">${esc(candidate.activity_id)}</span>
          <span class="candidate-name">${esc(candidate.name)}</span>
          ${meter(candidate.score)}
          <button class="btn sm" data-pick="${esc(candidate.activity_id)}">Link</button>
        </div>`).join('') || '<div class="empty tiny">No candidates returned.</div>'}

      ${evidenceTicks(event.explanation)}

      <div class="row" style="margin-top:14px">
        <button class="btn good sm" data-act="approve" ${approvable ? '' : 'disabled'}
          title="${approvable ? '' : 'Ambiguous — pick a candidate above instead'}">Approve top match</button>
        <button class="btn danger sm" data-act="reject">Reject</button>
        <button class="btn sm" data-act="choose">Choose another activity…</button>
        <span class="spacer"></span>
        <button class="btn sm ghost" onclick="openChain('${esc(event.event_id)}')">Trace</button>
      </div>`;

    card.querySelectorAll('[data-pick]').forEach((button) => {
      button.onclick = () => review(event.event_id, 'reassign', button.dataset.pick);
    });
    card.querySelector('[data-act="approve"]').onclick = () => review(event.event_id, 'approve');
    card.querySelector('[data-act="reject"]').onclick = () => review(event.event_id, 'reject');
    card.querySelector('[data-act="choose"]').onclick = () => openActivityPicker(event.event_id);
    list.appendChild(card);
  });
}

async function review(eventId, decision, activityId) {
  try {
    const result = await api(`/api/matches/${encodeURIComponent(eventId)}/review`, {
      method: 'POST',
      body: JSON.stringify({ decision, activity_id: activityId, reviewer: 'planner' }),
    });
    toast(`${decision === 'reject' ? 'Rejected' : 'Linked'} — correction stored. ` +
          `${result.feedback_count} correction(s) now training the matcher.`);
    closeModal();
    await loadProgress();
    await loadReview();
  } catch (error) {
    toast(error.message, true);
  }
}

async function openActivityPicker(eventId) {
  const render = (rows) => rows.map((row) => `
    <div class="candidate">
      <span class="mono">${esc(row.activity_id)}</span>
      <span class="candidate-name">${esc(row.activity_name)}
        <span class="tiny faint">${esc(row.discipline)} · ${esc(row.location)}</span></span>
      <button class="btn sm" data-pick="${esc(row.activity_id)}">Link</button>
    </div>`).join('');

  const data = await api('/api/activities?limit=200');
  openModal(`
    <h2 style="margin:0 0 4px;font-size:16px">Choose the correct activity</h2>
    <p class="tiny dim" style="margin:0 0 12px">
      Your choice is stored as a correction, so this phrasing matches better next time.</p>
    <input type="search" id="picker-search" placeholder="Search activity id, name, discipline or area…">
    <div id="picker-list" style="margin-top:12px">${render(data.activities)}</div>`);

  const bind = () => $('#picker-list').querySelectorAll('[data-pick]').forEach((button) => {
    button.onclick = () => review(eventId, 'reassign', button.dataset.pick);
  });
  bind();

  let timer;
  $('#picker-search').oninput = (event) => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const found = await api('/api/activities?limit=200&q=' + encodeURIComponent(event.target.value));
      $('#picker-list').innerHTML = render(found.activities);
      bind();
    }, 180);
  };
}

/* --------------------------------------------------------- 4 · conflicts */

async function loadConflicts() {
  const data = await api('/api/conflicts?include_resolved=true');
  const list = $('#conflict-list');

  if (!data.count) {
    list.innerHTML = `<div class="empty" style="text-align:left;padding:26px 28px">
      <div style="font-size:15px;color:var(--high);margin-bottom:6px">✓ No contradictions outstanding</div>
      <p class="dim" style="margin:0 0 14px">
        Every source that reported on the same activity agrees. SYNAPSE watches for
        two kinds of contradiction and neither is present right now:</p>
      <ul class="dim tiny" style="margin:0 0 16px;padding-left:18px;line-height:1.9">
        <li><b>Same-day disagreement</b> — two sources describing the same activity
            on the same date with different statuses.</li>
        <li><b>State regression</b> — a later report walking back an activity an
            earlier source already recorded as complete.</li>
      </ul>
      <p class="tiny faint" style="margin:0">
        To see it fire: ingest a daily report, then go to
        <b>Supervisor input</b> and report that same activity as blocked.</p>
    </div>`;
    return;
  }

  list.innerHTML = '';
  data.conflicts.forEach((conflict) => {
    const card = el('div', 'card ' + (conflict.resolved ? '' : 'danger'));
    card.innerHTML = `
      <div class="card-head">
        <div style="flex:1">
          <div class="section-label">${conflict.resolved ? 'Resolved conflict' : '⚠ Conflict detected'}
            · ${conflict.kind === 'state_regression' ? 'state walked back' : 'same-day disagreement'}</div>
          <div style="font-weight:650">${esc(conflict.activity_id)} — ${esc(conflict.activity_name)}</div>
          <div class="tiny faint">${conflict.kind === 'state_regression'
            ? 'Latest report: ' : 'Reported date: '}${esc(conflict.event_date)}</div>
        </div>
        <span class="badge ${conflict.severity === 'HIGH' ? 'low' : 'medium'}">${esc(conflict.severity)}</span>
      </div>

      <div class="claims">
        ${conflict.claims.map((claim) => `
          <div class="claim ${esc(String(claim.status).toLowerCase())}">
            <div>
              <div class="mono tiny">${esc(claim.claim_label || claim.source_id)}
                <span class="faint">· ${esc(claim.source_type)}</span></div>
              <div class="tiny dim">${esc(claim.raw_text)}</div>
            </div>
            <div class="row">
              <span class="badge ${claim.status === 'COMPLETED' ? 'high' : claim.status === 'ON_HOLD' ? 'low' : claim.status === 'UNKNOWN' ? 'mute' : 'info'}">${esc(claim.status)}</span>
              ${conflict.resolved ? '' :
                `<button class="btn sm" data-trust="${esc(claim.source_id)}">Trust this</button>`}
            </div>
          </div>`).join('')}
      </div>

      ${conflict.contradictions.map((c) =>
        `<div class="tiny" style="color:var(--low)">⚠ ${esc(c.message)}</div>`).join('')}

      ${conflict.resolved ? `
        <div class="tiny" style="margin-top:10px;color:var(--high)">
          ✓ ${esc(conflict.resolution.reviewer)} trusted
          <b>${esc(conflict.resolution.trusted_source_id)}</b>
          (${esc(conflict.resolution.trusted_status)}) at ${esc(conflict.resolution.decided_at)}
        </div>` : `
        ${conflict.resolution && conflict.resolution.action === 'investigate' ? `
          <div class="tiny" style="margin-top:10px;color:var(--medium)">
            Flagged for site investigation by ${esc(conflict.resolution.reviewer)}
            at ${esc(conflict.resolution.decided_at)} — still open until a source is trusted.
          </div>` : ''}
        <div class="row" style="margin-top:12px">
          <span class="tiny dim">Which source do you trust?</span>
          <span class="spacer"></span>
          <button class="btn sm ghost" data-investigate>Send for site investigation</button>
        </div>`}`;

    card.querySelectorAll('[data-trust]').forEach((button) => {
      button.onclick = () => resolveConflict(conflict.conflict_id,
        { action: 'trust', trusted_source_id: button.dataset.trust, reviewer: 'planner' });
    });
    const investigate = card.querySelector('[data-investigate]');
    if (investigate) {
      investigate.onclick = () => resolveConflict(conflict.conflict_id,
        { action: 'investigate', reviewer: 'planner', note: 'Flagged from conflict screen' });
    }
    list.appendChild(card);
  });
}

async function resolveConflict(conflictId, body) {
  try {
    await api(`/api/conflicts/${encodeURIComponent(conflictId)}/resolve`,
      { method: 'POST', body: JSON.stringify(body) });
    toast(body.action === 'trust'
      ? `Trusted ${body.trusted_source_id}. Schedule updated and decision recorded.`
      : 'Flagged for site investigation — recorded in the audit trail.');
    await loadProgress();
    await loadConflicts();
  } catch (error) {
    toast(error.message, true);
  }
}

/* ---------------------------------------------------------- 5 · schedule */

const DAY_MS = 86400000;
const toDate = (value) => value ? new Date(value + 'T00:00:00Z') : null;

async function loadSchedule() {
  const discipline = $('#schedule-discipline').value;
  const touched = $('#schedule-touched').checked;
  const data = await api('/api/schedule?' + new URLSearchParams({
    ...(discipline ? { discipline } : {}),
    only_touched: touched,
  }));

  const select = $('#schedule-discipline');
  if (select.options.length <= 1) {
    data.disciplines.forEach((d) => select.appendChild(new Option(d, d)));
  }

  if (!data.count) {
    $('#gantt').innerHTML = '<div class="empty">Nothing to show for this filter.</div>';
    $('#schedule-table').innerHTML = '';
    return;
  }

  // -- gantt
  const start = toDate(data.window.start);
  const end = toDate(data.window.end);
  const span = Math.max(1, (end - start) / DAY_MS);
  const place = (from, to) => {
    const a = toDate(from), b = toDate(to);
    if (!a || !b) return null;
    return {
      left: ((a - start) / DAY_MS / span) * 100,
      width: Math.max(0.6, ((b - a) / DAY_MS + 1) / span * 100),
    };
  };

  const at = (day) => {
    const d = toDate(day);
    return d ? ((d - start) / DAY_MS / span) * 100 : null;
  };

  const bars = data.activities.map((row) => {
    const planned = place(row.planned_start, row.planned_finish);
    const lateness = row.variance_days;
    let overlay = '';

    if (row.actual_finish) {
      const pf = at(row.planned_finish);
      const af = at(row.actual_finish);
      // The slip: the gap between the planned finish and what the field
      // actually reported. Drawing a full "actual" bar would imply we know
      // when the work started — usually we only know when it ended.
      if (pf !== null && af !== null && Math.abs(af - pf) > 0.15) {
        overlay += `<div class="bar slip ${lateness > 0 ? 'late' : 'early'}"
          style="left:${Math.min(pf, af)}%;width:${Math.abs(af - pf)}%"
          title="Planned finish ${esc(row.planned_finish)} → actual ${esc(row.actual_finish)}"></div>`;
      }
      if (af !== null) {
        overlay += `<div class="marker ${lateness > 0 ? 'late' : lateness < 0 ? 'early' : 'ontime'}"
          style="left:${af}%"
          title="Reported finished ${esc(row.actual_finish)}${row.actual_start_inferred
            ? ' (start not reported)' : ''}"></div>`;
      }
    } else if (row.actual_start) {
      const as = at(row.actual_start);
      if (as !== null) {
        overlay += `<div class="marker started" style="left:${as}%"
          title="Reported started ${esc(row.actual_start)} — not yet finished"></div>`;
      }
    }

    return `<div class="gantt-row">
      <span class="mono tiny">${esc(row.activity_id)}</span>
      <span class="tiny">${esc(row.activity_name)}</span>
      <div class="gantt-track">
        ${planned ? `<div class="bar planned" style="left:${planned.left}%;width:${planned.width}%"
            title="Planned ${esc(row.planned_start)} → ${esc(row.planned_finish)}"></div>` : ''}
        ${overlay}
      </div>
      <span class="tiny mono" style="text-align:right;color:${
        lateness === null ? 'var(--text-faint)' : lateness > 0 ? 'var(--low)' : 'var(--high)'}">
        ${lateness === null ? '—' : (lateness > 0 ? '+' : '') + lateness + 'd'}</span>
    </div>`;
  }).join('');

  $('#gantt').innerHTML =
    `<div class="gantt-row gantt-head">
       <span>Activity</span><span>Name</span>
       <span>${esc(data.window.start)} → ${esc(data.window.end)}</span><span>Var</span>
     </div>` + bars;

  // -- table
  const rows = data.activities.map((row) => `
    <tr>
      <td class="mono">${esc(row.activity_id)}</td>
      <td>${esc(row.activity_name)}<div class="tiny faint">${esc(row.discipline)} · ${esc(row.location)}</div></td>
      <td class="mono tiny">${dash(row.planned_start)} → ${dash(row.planned_finish)}</td>
      <td class="mono tiny">${row.actual_finish ? esc(row.actual_start) + ' → ' + esc(row.actual_finish) : '<span class="faint">no field evidence</span>'}</td>
      <td class="num" style="color:${row.variance_days === null ? 'var(--text-faint)' : row.variance_days > 0 ? 'var(--low)' : 'var(--high)'}">
        ${row.variance_days === null ? '—' : (row.variance_days > 0 ? '+' : '') + row.variance_days}</td>
      <td><span class="badge ${row.status === 'COMPLETED' ? 'high' : row.status === 'IN_PROGRESS' ? 'info' : row.status === 'ON_HOLD' ? 'low' : 'mute'}">${esc(row.status)}</span></td>
      <td class="num">${row.progress_percent}%</td>
      <td>${row.evidence_event_ids.length
        ? `<button class="btn sm ghost" onclick="openChain('${esc(row.evidence_event_ids[0])}')">${row.evidence_event_ids.length} source(s)</button>`
        : '<span class="faint tiny">—</span>'}</td>
    </tr>`).join('');

  $('#schedule-table').innerHTML = `<div class="table-wrap"><table>
    <thead><tr><th>ID</th><th>Activity</th><th>Planned</th><th>Actual</th>
      <th>Var (d)</th><th>Status</th><th>Progress</th><th>Evidence</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

/* -------------------------------------------------------------- 6 · risk */

async function loadRisk() {
  const discipline = $('#risk-discipline').value;
  const data = await api('/api/risk?limit=20' + (discipline ? '&discipline=' + discipline : ''));

  const select = $('#risk-discipline');
  if (select.options.length <= 1) {
    ['piping', 'electrical', 'civil', 'mechanical', 'instrumentation']
      .forEach((d) => select.appendChild(new Option(d, d)));
  }

  $('#risk-counts').textContent =
    `${data.high} high · ${data.medium} medium · ${data.low} low, across ${data.count} unfinished activities`;

  if (!data.activities.length) {
    $('#risk-list').innerHTML = '<div class="empty">No unfinished activities for this filter.</div>';
    return;
  }

  $('#risk-list').innerHTML = data.activities.map((row) => {
    // A rate computed from a handful of records is indicative, not a
    // statistic. Say so next to the number, not in a footnote under it.
    const thin = ['low', 'none'].includes(row.evidence_confidence);
    return `
    <div class="risk-card ${esc(row.historical_risk)}">
      <div class="card-head">
        <div style="flex:1">
          <div class="row">
            <span class="badge ${row.historical_risk === 'HIGH' ? 'low' : row.historical_risk === 'MEDIUM' ? 'medium' : 'high'}">${esc(row.historical_risk)} RISK</span>
            <span class="mono">${esc(row.activity_id)}</span>
            <span>${esc(row.activity_name)}</span>
          </div>
          <div class="tiny faint">${esc(row.discipline)} · ${esc(row.location)} ·
            planned ${esc(row.planned_start)} → ${esc(row.planned_finish)}</div>
        </div>
      </div>

      <div class="stat-row">
        <div><div class="stat-value" style="color:${thin ? 'var(--medium)' : 'var(--low)'}">
               ${row.delay_rate_percent}%</div>
             <div class="stat-label">delay rate · n=${row.historical_matches}</div></div>
        <div><div class="stat-value">${row.avg_variance_days}d</div>
             <div class="stat-label">avg overrun</div></div>
        <div><div class="stat-value" style="color:var(--medium)">+${row.suggested_buffer_days}d</div>
             <div class="stat-label">suggested buffer</div></div>
        <div><div class="stat-value">${row.historical_matches}</div>
             <div class="stat-label">similar past activities</div></div>
      </div>

      ${thin ? `<div class="caution">
          Based on only ${row.historical_matches} comparable past
          ${row.historical_matches === 1 ? 'activity' : 'activities'} — indicative, not a reliable rate.
        </div>` : ''}

      ${row.common_causes.length ? `<div class="tiny dim" style="margin-top:8px">Common causes:
        ${row.common_causes.map((c) =>
          `<span class="badge mute">${esc(c.cause)} · ${Math.round(c.frequency * 100)}%</span>`).join(' ')}</div>` : ''}

      <div class="row" style="margin-top:10px">
        <span class="badge ${thin ? 'medium' : 'mute'}">evidence confidence: ${esc(row.evidence_confidence)}</span>
        ${row.variance_days !== null ? `<span class="badge ${row.variance_days > 0 ? 'low' : 'high'}">live variance ${row.variance_days > 0 ? '+' : ''}${row.variance_days}d</span>` : ''}
        <span class="spacer"></span>
        <button class="btn sm ghost" onclick="openRiskEvidence('${esc(row.activity_id)}')">View historical evidence</button>
      </div>
    </div>`;
  }).join('');
}

async function openRiskEvidence(activityId) {
  const data = await api(`/api/risk/${encodeURIComponent(activityId)}/evidence`);
  const assessment = data.assessment;
  openModal(`
    <h2 style="margin:0 0 4px;font-size:16px">${esc(data.activity_id)} — ${esc(data.activity_name)}</h2>
    <p class="tiny dim" style="margin:0 0 14px">
      ${assessment.historical_matches} similar completed activities ·
      ${Math.round(assessment.delay_frequency * 100)}% were delayed ·
      average overrun ${assessment.avg_variance_days} days ·
      evidence confidence ${esc(assessment.confidence)}</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Project</th><th>Activity</th><th>Planned</th><th>Actual</th>
        <th>Var</th><th>Cause</th><th>Sim</th></tr></thead>
      <tbody>${data.records.map((record) => `
        <tr>
          <td class="mono tiny">${esc(record.project_id)}</td>
          <td class="tiny">${esc(record.activity_description)}</td>
          <td class="num">${record.planned_duration_days}d</td>
          <td class="num">${record.actual_duration_days}d</td>
          <td class="num" style="color:${record.variance_days > 0 ? 'var(--low)' : 'var(--high)'}">
            ${record.variance_days > 0 ? '+' : ''}${record.variance_days}</td>
          <td class="tiny">${dash(record.delay_cause)}</td>
          <td class="num tiny">${record.similarity ?? '—'}</td>
        </tr>`).join('')}</tbody>
    </table></div>`);
}

/* ----------------------------------------------------------- 7 · history */

async function runHistory(question) {
  $('#history-input').value = question;
  $('#history-result').innerHTML = '<div class="panel"><span class="busy"></span> Searching institutional memory…</div>';
  try {
    const data = await api('/api/history/search?q=' + encodeURIComponent(question));
    $('#history-result').innerHTML = `
      <div class="panel">
        <div class="panel-title">Answer · intent detected: ${esc(data.intent)}</div>
        <p style="font-size:15px;margin:0 0 6px">${esc(data.summary)}</p>
        <p class="tiny faint" style="margin:0">Drawn from ${data.total_records} verified historical records.</p>
      </div>
      <div class="panel">
        <div class="panel-title">Supporting records</div>
        <div class="table-wrap"><table>
          <thead><tr><th>Project</th><th>Discipline</th><th>Activity</th><th>Planned</th>
            <th>Actual</th><th>Var</th><th>Delay cause</th><th>Sim</th></tr></thead>
          <tbody>${data.supporting_records.map((record) => `
            <tr>
              <td class="mono tiny">${esc(record.project_id)}</td>
              <td><span class="badge mute">${esc(record.discipline)}</span></td>
              <td class="tiny">${esc(record.activity_description)}</td>
              <td class="num">${record.planned_duration_days}d</td>
              <td class="num">${record.actual_duration_days}d</td>
              <td class="num" style="color:${record.variance_days > 0 ? 'var(--low)' : 'var(--high)'}">
                ${record.variance_days > 0 ? '+' : ''}${record.variance_days}</td>
              <td class="tiny">${dash(record.delay_cause)}</td>
              <td class="num tiny">${record.similarity ?? '—'}</td>
            </tr>`).join('')}</tbody></table></div>
      </div>`;
  } catch (error) {
    $('#history-result').innerHTML = `<div class="empty">${esc(error.message)}</div>`;
  }
}

/* ------------------------------------------------------------- 8 · audit */

async function loadAudit() {
  const stage = $('#audit-stage').value;
  const data = await api('/api/audit' + (stage ? '?stage=' + stage : ''));
  $('#audit-count').textContent = `${data.count} recorded step(s)`;
  $('#audit-list').innerHTML = data.entries.length
    ? data.entries.map((entry) => `
        <div class="chain-node stage-${esc(entry.stage)}">
          <div class="chain-stage">${esc(entry.stage.replace(/_/g, ' '))}
            · <span class="faint">${esc(entry.actor)}</span>
            ${entry.event_id ? `· <span class="mono faint">${esc(entry.event_id)}</span>` : ''}</div>
          <div>${esc(entry.summary)}</div>
          <div class="tiny faint mono">${esc(clock(entry.timestamp))}</div>
        </div>`).join('')
    : '<div class="empty">Nothing recorded yet.</div>';
}

async function openChain(eventId) {
  const data = await api('/api/audit/event/' + encodeURIComponent(eventId));
  const event = data.event;
  openModal(`
    <h2 style="margin:0 0 4px;font-size:16px">Provenance · ${esc(eventId)}</h2>
    <div class="quote" style="margin-bottom:14px">${esc(event.raw_text)}</div>
    <div class="row" style="margin-bottom:14px">
      ${linkBadge(event.link_state)}
      <span class="badge mute">extraction ${pct(event.extraction_confidence)}</span>
      <span class="badge mute">match ${pct(event.match_confidence)}</span>
      ${event.matched_activity_id ? `<span class="badge info">${esc(event.matched_activity_id)}</span>` : ''}
    </div>
    ${evidenceTicks(event.explanation)}
    ${data.schedule_state ? `
      <div class="section-label" style="margin-top:16px">Resulting schedule state</div>
      <div class="candidate">
        <span class="mono">${esc(data.schedule_state.activity_id)}</span>
        <span class="candidate-name">${esc(data.schedule_state.activity_name)}</span>
        <span class="badge mute">planned ${esc(data.schedule_state.planned_finish)}</span>
        <span class="badge ${data.schedule_state.variance_days > 0 ? 'low' : 'high'}">actual ${esc(data.schedule_state.actual_finish)}</span>
      </div>` : ''}
    <div class="section-label" style="margin:16px 0 10px">Audit chain</div>
    <div class="chain">${chainHtml(data.chain)}</div>`);
}

/* ------------------------------------------------------------ modal/wire */

function openModal(html) { $('#modal').innerHTML = html; $('#overlay').hidden = false; }
function closeModal() { $('#overlay').hidden = true; }

$('#overlay').onclick = (event) => { if (event.target.id === 'overlay') closeModal(); };
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeModal(); });

$('#btn-send').onclick = () => sendSupervisor($('#sup-input').value);
$('#sup-input').onkeydown = (event) => { if (event.key === 'Enter') sendSupervisor($('#sup-input').value); };

$('#btn-voice').onclick = () => {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) { toast('This browser has no speech recognition. Type instead.', true); return; }
  const recognition = new Recognition();
  recognition.lang = 'en-IN';
  recognition.onresult = (event) => sendSupervisor(event.results[0][0].transcript);
  recognition.onerror = () => toast('Could not hear that.', true);
  recognition.start();
  toast('Listening…');
};

$('#file-input').onchange = (event) => { $('#btn-upload').disabled = !event.target.files.length; };
$('#btn-upload').onclick = async () => {
  const file = $('#file-input').files[0];
  if (!file) return;
  const body = new FormData();
  body.append('file', file);
  $('#btn-upload').disabled = true;
  $('#btn-upload').innerHTML = '<span class="busy"></span> Processing';
  try {
    const res = await fetch('/api/events/upload', { method: 'POST', body });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    showIngestResult(await res.json());
    await loadProgress();
  } catch (error) {
    toast(error.message, true);
  } finally {
    $('#btn-upload').disabled = false;
    $('#btn-upload').textContent = 'Process document';
  }
};

$('#btn-paste').onclick = async () => {
  const text = $('#paste-input').value.trim();
  if (!text) { toast('Paste some report text first.', true); return; }
  try {
    showIngestResult(await api('/api/events/extract', {
      method: 'POST',
      body: JSON.stringify({ text, source_id: 'pasted_' + Date.now(), source_type: 'daily_report' }),
    }));
    await loadProgress();
  } catch (error) {
    toast(error.message, true);
  }
};

$('#events-filter').onchange = loadEvents;
$('#schedule-discipline').onchange = loadSchedule;
$('#schedule-touched').onchange = loadSchedule;
$('#risk-discipline').onchange = loadRisk;
$('#audit-stage').onchange = loadAudit;

$('#btn-history').onclick = () => runHistory($('#history-input').value.trim());
$('#history-input').onkeydown = (event) => {
  if (event.key === 'Enter') runHistory(event.target.value.trim());
};
document.querySelectorAll('.history-example').forEach((button) => {
  button.onclick = () => runHistory(button.textContent);
});

$('#btn-refresh').onclick = async () => { await loadProgress(); show(state.view); };
$('#btn-reset').onclick = async () => {
  await api('/api/session/reset', { method: 'POST' });
  $('#console').innerHTML = '';
  $('#sup-chain').innerHTML = '<div class="empty">Send a message to see its journey through the pipeline.</div>';
  $('#ingest-result').hidden = true;
  state.pendingClarification = null;
  toast('Session reset. Schedule and historical memory kept.');
  await loadProgress();
  show(state.view);
};

/* ------------------------------------------------------------------ boot */

(async function boot() {
  try {
    const health = await api('/api/health');
    consoleLine('system',
      `Ready. ${health.activities_loaded} schedule activities and ` +
      `${health.historical_records} historical records loaded. Describe what happened on site.`);
  } catch (error) {
    consoleLine('err', 'Cannot reach the SYNAPSE API: ' + error.message);
  }
  await loadProgress();
  show(location.hash.slice(1) || 'supervisor');
})();
