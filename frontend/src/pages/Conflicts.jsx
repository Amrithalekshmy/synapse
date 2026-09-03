import React, { useState, useEffect } from 'react';
import { AlertCircle, Check } from 'lucide-react';
import { useAuth } from '../App';
import { getConflicts, resolveConflict } from '../api';

export default function Conflicts() {
  const { user } = useAuth();
  const [conflicts, setConflicts] = useState([]);
  const [showResolved, setShowResolved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  const load = async () => {
    try {
      const res = await getConflicts(showResolved);
      setConflicts(res.conflicts || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [showResolved]);

  const handleResolve = async (conflictId, action, keepEventId) => {
    setActionLoading(conflictId);
    try {
      await resolveConflict(conflictId, {
        action,
        resolver: user?.username || 'admin',
        keep_event_id: keepEventId,
      });
      await load();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return <div className="loading-overlay"><div className="spinner" /> Loading conflicts...</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Conflict Resolution</h1>
        <p className="page-subtitle">
          When sources disagree about the same activity, SYNAPSE flags the conflict
          rather than picking silently. The planner decides which source to trust.
        </p>
      </div>

      <div className="flex gap-4 mb-4 items-center">
        <label className="flex gap-2 items-center text-sm">
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
          />
          Show resolved
        </label>
        <span className="text-xs text-muted">{conflicts.length} conflicts</span>
      </div>

      {conflicts.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Check size={48} />
            <p>No open conflicts. All sources agree.</p>
          </div>
        </div>
      ) : (
        <div className="flex-col gap-3">
          {conflicts.map((c) => (
            <div key={c.conflict_id} className="card">
              <div className="flex justify-between items-center mb-2">
                <div className="flex gap-2 items-center">
                  <AlertCircle size={16} color={c.severity === 'HIGH' ? 'var(--danger)' : 'var(--accent)'} />
                  <span className="font-mono text-sm font-semibold">{c.conflict_id}</span>
                  <span className={`badge badge-${c.severity?.toLowerCase() || 'muted'}`}>{c.severity}</span>
                  {c.resolved && <span className="badge badge-auto">Resolved</span>}
                </div>
                <span className="text-xs text-muted font-mono">{c.activity_id}</span>
              </div>
              <p className="text-sm mb-2">{c.description || c.type || 'Conflicting reports'}</p>
              {c.event_ids && (
                <div className="text-xs text-muted mb-2">
                  Events: {c.event_ids.map((id) => (
                    <span key={id} className="font-mono" style={{ marginRight: 8 }}>{id}</span>
                  ))}
                </div>
              )}
              {!c.resolved && (
                <div className="flex gap-2 mt-2">
                  {c.event_ids?.map((id) => (
                    <button
                      key={id}
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleResolve(c.conflict_id, 'keep', id)}
                      disabled={actionLoading === c.conflict_id}
                    >
                      Keep {id}
                    </button>
                  ))}
                  <button
                    className="btn btn-warning btn-sm"
                    onClick={() => handleResolve(c.conflict_id, 'investigate')}
                    disabled={actionLoading === c.conflict_id}
                  >
                    Investigate
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
