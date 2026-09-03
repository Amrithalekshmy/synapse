import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, ArrowRight, Search } from 'lucide-react';
import { useAuth } from '../App';
import { getReviewQueue, getActivities, reviewMatch } from '../api';

export default function ReviewQueue() {
  const { user } = useAuth();
  const [queue, setQueue] = useState([]);
  const [thresholds, setThresholds] = useState({});
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [reassignEvent, setReassignEvent] = useState(null);
  const [searchQ, setSearchQ] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  const load = async () => {
    try {
      const res = await getReviewQueue();
      setQueue(res.queue || []);
      setThresholds({ auto: res.auto_threshold, review: res.review_threshold });
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
          Events the engine couldn't auto-link. Each decision here trains the matching engine
          — the queue shrinks as the system learns your corrections.
        </p>
      </div>

      <div className="flex gap-4 mb-4 text-xs">
        <span className="badge badge-auto">Auto-link &ge; {((thresholds.auto || 0.85) * 100).toFixed(0)}%</span>
        <span className="badge badge-pending">Review {((thresholds.review || 0.65) * 100).toFixed(0)}%–{((thresholds.auto || 0.85) * 100).toFixed(0)}%</span>
        <span className="badge badge-rejected">Reject &lt; {((thresholds.review || 0.65) * 100).toFixed(0)}%</span>
      </div>

      {queue.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <CheckCircle size={48} />
            <p>Review queue is empty. All events have been processed.</p>
          </div>
        </div>
      ) : (
        <div className="flex-col gap-3">
          {queue.map((ev) => (
            <div key={ev.event_id} className="card">
              <div className="flex justify-between items-center mb-2">
                <div>
                  <span className="font-mono text-sm font-semibold">{ev.event_id}</span>
                  <span className="badge badge-pending" style={{ marginLeft: 8 }}>
                    {ev.match_confidence != null ? `${(ev.match_confidence * 100).toFixed(0)}%` : '—'}
                  </span>
                </div>
                <span className="text-xs text-muted">{ev.discipline || 'No discipline'}</span>
              </div>
              <p className="text-sm mb-2">{ev.description}</p>
              {ev.matched_activity_id && (
                <div className="text-xs text-muted mb-2">
                  Best match: <span className="font-mono font-semibold">{ev.matched_activity_id}</span>
                  {ev.matched_activity_name && ` — ${ev.matched_activity_name}`}
                </div>
              )}
              {ev.match_evidence && (
                <div className="flex gap-2 mb-4" style={{ flexWrap: 'wrap' }}>
                  {Object.entries(ev.match_evidence).map(([k, v]) => (
                    v && <span key={k} className="badge badge-info">{k}</span>
                  ))}
                </div>
              )}

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
                <div className="flex gap-2">
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
          ))}
        </div>
      )}
    </div>
  );
}
