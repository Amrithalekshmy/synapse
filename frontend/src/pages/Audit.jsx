import React, { useState, useEffect } from 'react';
import { FileText } from 'lucide-react';
import { getAudit } from '../api';

const STAGE_COLORS = {
  INGEST: '#3B82F6',
  EXTRACT: '#8B5CF6',
  CLARIFY: '#D97706',
  MATCH: '#1E40AF',
  CONFLICT: '#DC2626',
  REVIEW: '#059669',
  LEARN: '#06B6D4',
  SCHEDULE_UPDATE: '#10B981',
  HISTORY: '#64748B',
  SYSTEM: '#94A3B8',
};

export default function Audit() {
  const [entries, setEntries] = useState([]);
  const [stage, setStage] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getAudit(stage || undefined)
      .then((res) => setEntries(res.entries || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [stage]);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Audit Trail</h1>
        <p className="page-subtitle">
          Every automated step and every human decision, in order, with who did it.
        </p>
      </div>

      <div className="flex gap-4 mb-4 items-center">
        <select className="form-input" style={{ maxWidth: 220 }} value={stage} onChange={(e) => setStage(e.target.value)}>
          <option value="">All stages</option>
          {Object.keys(STAGE_COLORS).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <span className="text-xs text-muted">{entries.length} entries</span>
      </div>

      {loading ? (
        <div className="loading-overlay"><div className="spinner" /> Loading audit trail...</div>
      ) : entries.length === 0 ? (
        <div className="card"><div className="empty-state"><FileText size={48} /><p>No audit entries yet.</p></div></div>
      ) : (
        <div className="card">
          <div className="flex-col">
            {entries.map((e, i) => (
              <div key={i} className="pipeline-step">
                <div
                  className="pipeline-icon"
                  style={{ background: `${STAGE_COLORS[e.stage] || '#94A3B8'}20`, color: STAGE_COLORS[e.stage] || '#94A3B8' }}
                >
                  <FileText size={14} />
                </div>
                <div className="pipeline-content">
                  <div className="pipeline-stage">{e.stage}</div>
                  <div className="pipeline-text">{e.summary}</div>
                  <div className="pipeline-meta">
                    {e.timestamp && <span>{e.timestamp}</span>}
                    {e.actor && <span> &middot; {e.actor}</span>}
                    {e.event_id && <span> &middot; {e.event_id}</span>}
                    {e.activity_id && <span> &middot; {e.activity_id}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
