import React, { useState, useEffect } from 'react';
import { getSchedule } from '../api';

const STATUS_COLORS = {
  COMPLETED: '#059669',
  IN_PROGRESS: '#3B82F6',
  NOT_STARTED: '#94A3B8',
  ON_HOLD: '#D97706',
  CANCELLED: '#DC2626',
};

export default function Schedule() {
  const [data, setData] = useState(null);
  const [discipline, setDiscipline] = useState('');
  const [touched, setTouched] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getSchedule(discipline || undefined, touched);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [discipline, touched]);

  const activities = data?.activities || [];
  const disciplines = data?.disciplines || [];
  const window = data?.window || {};

  const ganttStart = window.start ? new Date(window.start) : null;
  const ganttEnd = window.end ? new Date(window.end) : null;
  const ganttRange = ganttStart && ganttEnd ? ganttEnd - ganttStart : 1;

  const barPos = (dateStr) => {
    if (!dateStr || !ganttStart) return null;
    return ((new Date(dateStr) - ganttStart) / ganttRange) * 100;
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Schedule & Variance</h1>
        <p className="page-subtitle">
          Planned versus actual — updated the moment a field report is linked.
          Actual dates come only from evidence.
        </p>
      </div>

      <div className="flex gap-4 mb-4 items-center">
        <select
          className="form-input"
          style={{ maxWidth: 200 }}
          value={discipline}
          onChange={(e) => setDiscipline(e.target.value)}
        >
          <option value="">All disciplines</option>
          {disciplines.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <label className="flex gap-2 items-center text-sm">
          <input
            type="checkbox"
            checked={touched}
            onChange={(e) => setTouched(e.target.checked)}
          />
          Only with field evidence
        </label>
        <span className="text-xs text-muted">{activities.length} activities</span>
      </div>

      {loading ? (
        <div className="loading-overlay"><div className="spinner" /> Loading schedule...</div>
      ) : activities.length === 0 ? (
        <div className="card"><div className="empty-state"><p>No activities match the current filters.</p></div></div>
      ) : (
        <>
          {ganttStart && (
            <div className="card mb-4">
              <div className="card-title" style={{ marginBottom: 8 }}>Timeline</div>
              <div className="flex gap-2 mb-2 text-xs text-muted">
                <span>{window.start}</span>
                <span style={{ flex: 1 }} />
                <span>{window.end}</span>
              </div>
              <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                {activities.slice(0, 40).map((a) => {
                  const ps = barPos(a.planned_start);
                  const pe = barPos(a.planned_finish);
                  return (
                    <div key={a.activity_id} className="flex items-center gap-2 mb-1">
                      <div className="truncate text-xs font-mono" style={{ width: 100, flexShrink: 0 }}>
                        {a.activity_id}
                      </div>
                      <div style={{ flex: 1, height: 18, background: 'var(--border-light)', borderRadius: 3, position: 'relative' }}>
                        {ps != null && pe != null && (
                          <div
                            style={{
                              position: 'absolute',
                              left: `${Math.max(0, ps)}%`,
                              width: `${Math.max(1, pe - ps)}%`,
                              height: '100%',
                              background: STATUS_COLORS[a.status] || '#94A3B8',
                              borderRadius: 3,
                              opacity: 0.7,
                            }}
                            title={`${a.activity_name}\n${a.planned_start} → ${a.planned_finish}\nStatus: ${a.status}`}
                          />
                        )}
                        {a.actual_start && barPos(a.actual_start) != null && (
                          <div
                            style={{
                              position: 'absolute',
                              left: `${barPos(a.actual_start)}%`,
                              width: 3,
                              height: '100%',
                              background: '#D97706',
                              borderRadius: 1,
                            }}
                            title={`Actual start: ${a.actual_start}`}
                          />
                        )}
                        {a.actual_finish && barPos(a.actual_finish) != null && (
                          <div
                            style={{
                              position: 'absolute',
                              left: `${barPos(a.actual_finish)}%`,
                              width: 3,
                              height: '100%',
                              background: '#059669',
                              borderRadius: 1,
                            }}
                            title={`Actual finish: ${a.actual_finish}`}
                          />
                        )}
                      </div>
                      <div className="text-xs" style={{ width: 40, flexShrink: 0, textAlign: 'right' }}>
                        {a.variance_days != null ? (
                          <span style={{ color: a.variance_days > 0 ? 'var(--danger)' : a.variance_days < 0 ? 'var(--success)' : 'var(--text-muted)' }}>
                            {a.variance_days > 0 ? '+' : ''}{a.variance_days}d
                          </span>
                        ) : '—'}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="card overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Activity ID</th>
                  <th>Name</th>
                  <th>Discipline</th>
                  <th>Planned Start</th>
                  <th>Planned Finish</th>
                  <th>Actual Start</th>
                  <th>Actual Finish</th>
                  <th>Status</th>
                  <th>Variance</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {activities.map((a) => (
                  <tr key={a.activity_id}>
                    <td className="mono">{a.activity_id}</td>
                    <td className="truncate" style={{ maxWidth: 200 }}>{a.activity_name}</td>
                    <td>{a.discipline || '—'}</td>
                    <td className="mono">{a.planned_start || '—'}</td>
                    <td className="mono">{a.planned_finish || '—'}</td>
                    <td className="mono">{a.actual_start || '—'}</td>
                    <td className="mono">{a.actual_finish || '—'}</td>
                    <td>
                      <span className={`badge badge-${(a.status || '').toLowerCase().includes('complete') ? 'auto' : (a.status || '').toLowerCase().includes('progress') ? 'info' : 'muted'}`}>
                        {a.status || '—'}
                      </span>
                    </td>
                    <td className="mono" style={{
                      color: a.variance_days > 0 ? 'var(--danger)' : a.variance_days < 0 ? 'var(--success)' : undefined
                    }}>
                      {a.variance_days != null ? `${a.variance_days > 0 ? '+' : ''}${a.variance_days}` : '—'}
                    </td>
                    <td>
                      {a.schedule_risk && (
                        <span className={`badge badge-${a.schedule_risk.toLowerCase()}`}>{a.schedule_risk}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
