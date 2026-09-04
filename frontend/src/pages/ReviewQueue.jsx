import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, ArrowRight, Zap, AlertTriangle, Brain, GitBranch } from 'lucide-react';
import { useAuth } from '../App';
import { getReviewQueue, getActivities, reviewMatch, getAgentStatus } from '../api';

function RankBadge({ rank }) {
  if (!rank) return null;
  const colors = { 1: '#F59E0B', 2: '#94A3B8', 3: '#CD7C41' };
  const bg = colors[rank] || 'var(--border)';
  return (
    <span style={{
      background: bg, color: rank <= 3 ? '#000' : 'var(--text-muted)',
      borderRadius: '50%', width: 24, height: 24, display: 'inline-flex',
      alignItems: 'center', justifyContent: 'center', fontSize: 11,
      fontWeight: 700, flexShrink: 0,
    }}>#{rank}</span>
  );
}

function AgentBadge({ action }) {
  if (!action) return null;
  const map = {
    auto_link:          { bg: '#DCFCE7', color: '#166534', label: 'auto-link' },
    ask_clarification:  { bg: '#FEF9C3', color: '#713F12', label: 'clarify' },
    send_to_planner:    { bg: '#DBEAFE', color: '#1E40AF', label: 'planner' },
  };
  const s = map[action] || { bg: 'var(--border)', color: 'var(--text)', label: action };
  return (
    <span style={{
      background: s.bg, color: s.color, borderRadius: 4, fontSize: 10,
      fontWeight: 600, padding: '2px 6px', textTransform: 'uppercase',
    }}>
      <Brain size={10} style={{ verticalAlign: -1, marginRight: 3 }} />
      {s.label}
    </span>
  );
}

function CascadeBar({ cascade }) {
  if (!cascade || cascade.total_impacted === 0) return null;
  const critical = cascade.critical_path_hit;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '5px 10px', borderRadius: 4, marginBottom: 8, fontSize: 12,
      background: critical ? '#FEF2F2' : '#FFF7ED',
      borderLeft: `3px solid ${critical ? '#DC2626' : '#D97706'}`,
      color: critical ? '#991B1B' : '#92400E',
    }}>
      {critical ? <AlertTriangle size={13} /> : <GitBranch size={13} />}
      <span>{cascade.summary}</span>
    </div>
  );
}

export default function ReviewQueue() {
  const { user } = useAuth();
  const [queue, setQueue] = useState([]);
  const [thresholds, setThresholds] = useState({});
  const [agentStatus, setAgentStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [reassignEvent, setReassignEvent] = useState(null);
  const [searchQ, setSearchQ] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  const load = async () => {
    try {
      const [res, agent] = await Promise.all([
        getReviewQueue(),
        getAgentStatus().catch(() => null),
      ]);
      setQueue(res.queue || []);
      setThresholds({ auto: res.auto_threshold, review: res.review_threshold, rl_updates: res.rl_updates });
      setAgentStatus(agent);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleReview = async (eventId, decision, activityId) => {
    setActionLoading(eventId);
    try {
      await reviewMatch(eventId, {
        decision,
        reviewer: user?.username || 'admin',
        activity_id: activityId || undefined,
        note: '',
      });
      await load();
      setReassignEvent(null);
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSearch = async (q) => {
    setSearchQ(q);
    if (q.length < 2) { setSearchResults([]); return; }
    try {
      const res = await getActivities(q);
      setSearchResults(res.activities || []);
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return <div className="loading-overlay"><div className="spinner" /> Loading review queue...</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Review Queue</h1>
        <p className="page-subtitle">
          Sorted by RL priority score — highest project impact first. Each decision trains the matching and routing agent.
        </p>
      </div>

      <div className="flex gap-3 mb-4" style={{ flexWrap: 'wrap' }}>
        <span className="badge badge-auto">Auto-link ≥ {((thresholds.auto || 0.85) * 100).toFixed(0)}%</span>
        <span className="badge badge-pending">Review {((thresholds.review || 0.65) * 100).toFixed(0)}%–{((thresholds.auto || 0.85) * 100).toFixed(0)}%</span>
        {agentStatus && (
          <span className="badge badge-info" style={{ background: '#EFF6FF', color: '#1E40AF', border: '1px solid #BFDBFE' }}>
            <Brain size={11} style={{ verticalAlign: -1, marginRight: 4 }} />
            Agent: {agentStatus.update_count} updates · ε={agentStatus.epsilon}
          </span>
        )}
        {thresholds.rl_updates > 0 && (
          <span className="badge badge-info" style={{ background: '#F0FDF4', color: '#166534', border: '1px solid #BBF7D0' }}>
            <Zap size={11} style={{ verticalAlign: -1, marginRight: 4 }} />
            RL: {thresholds.rl_updates} priority updates
          </span>
        )}
      </div>

      {queue.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <CheckCircle size={48} />
            <p>Queue is clear. All events have been processed.</p>
          </div>
        </div>
      ) : (
        <div className="flex-col gap-3">
          {queue.map((ev) => {
            const rl = ev.rl_priority || {};
            const cascade = ev.cascade_impact || {};
            const agent = ev.agent_decision || {};
            const agentExp = agent.explanation || {};

            return (
              <div key={ev.event_id} className="card">
                {/* Header row */}
                <div className="flex justify-between items-start mb-2" style={{ gap: 8 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="flex items-center gap-2 mb-1" style={{ flexWrap: 'wrap' }}>
                      <RankBadge rank={rl.rank} />
                      <span className="font-mono text-sm font-semibold">{ev.event_id}</span>
                      <span className="badge badge-pending">
                        {ev.match_confidence != null ? `${(ev.match_confidence * 100).toFixed(0)}%` : '—'}
                      </span>
                      <AgentBadge action={agent.action} />
                      {ev.discipline && <span className="text-xs text-muted">{ev.discipline}</span>}
                    </div>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{ev.description || ev.raw_text}</p>
                  </div>
                </div>

                {/* Cascade impact bar */}
                <CascadeBar cascade={cascade} />

                {/* RL driver + agent Q-values */}
                {(rl.top_driver || agentExp.top_driver) && (
                  <div className="flex gap-3 mb-2" style={{ fontSize: 11, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                    {rl.top_driver && (
                      <span>Priority driven by: <strong>{rl.top_driver}</strong> · score {rl.score}</span>
                    )}
                    {agentExp.top_driver && (
                      <span>Agent routed by: <strong>{agentExp.top_driver}</strong></span>
                    )}
                    {agent.q_values && (
                      <span>
                        Q: auto={agent.q_values.auto_link?.toFixed(2)} · clarify={agent.q_values.ask_clarification?.toFixed(2)} · planner={agent.q_values.send_to_planner?.toFixed(2)}
                      </span>
                    )}
                  </div>
                )}

                {/* Match */}
                {ev.matched_activity_id && (
                  <div className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
                    Best match: <span className="font-mono font-semibold" style={{ color: 'var(--text)' }}>{ev.matched_activity_id}</span>
                    {ev.matched_activity_name && ` — ${ev.matched_activity_name}`}
                  </div>
                )}

                {/* Candidates */}
                {(ev.candidates || []).length > 0 && (
                  <div className="flex gap-2 mb-3" style={{ flexWrap: 'wrap' }}>
                    {ev.candidates.slice(0, 3).map((c, i) => (
                      <span key={i} className="text-xs" style={{
                        background: 'var(--border-light)', borderRadius: 4,
                        padding: '2px 8px', fontFamily: 'var(--font-mono)',
                        color: i === 0 ? 'var(--primary)' : 'var(--text-muted)',
                      }}>
                        {c.activity_id} {(c.score * 100).toFixed(0)}%
                      </span>
                    ))}
                  </div>
                )}

                {/* Actions */}
                {reassignEvent === ev.event_id ? (
                  <div className="mt-2">
                    <div className="flex gap-2 mb-2">
                      <input
                        className="form-input"
                        type="text"
                        placeholder="Search activities..."
                        value={searchQ}
                        onChange={(e) => handleSearch(e.target.value)}
                        autoFocus
                      />
                      <button className="btn btn-ghost btn-sm" onClick={() => setReassignEvent(null)}>Cancel</button>
                    </div>
                    {searchResults.length > 0 && (
                      <div className="flex-col gap-1" style={{ maxHeight: 200, overflowY: 'auto' }}>
                        {searchResults.slice(0, 10).map((a) => (
                          <button
                            key={a.activity_id}
                            className="btn btn-ghost text-sm w-full"
                            style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                            onClick={() => handleReview(ev.event_id, 'reassign', a.activity_id)}
                            disabled={actionLoading === ev.event_id}
                          >
                            <span className="font-mono">{a.activity_id}</span> — {a.activity_name}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => handleReview(ev.event_id, 'approve')}
                      disabled={actionLoading === ev.event_id || !ev.matched_activity_id}
                    >
                      <CheckCircle size={14} /> Approve
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleReview(ev.event_id, 'reject')}
                      disabled={actionLoading === ev.event_id}
                    >
                      <XCircle size={14} /> Reject
                    </button>
                    <button
                      className="btn btn-warning btn-sm"
                      onClick={() => { setReassignEvent(ev.event_id); setSearchQ(''); setSearchResults([]); }}
                      disabled={actionLoading === ev.event_id}
                    >
                      <ArrowRight size={14} /> Reassign
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
