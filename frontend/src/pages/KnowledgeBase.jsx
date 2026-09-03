import React, { useState } from 'react';
import { Search, BookOpen } from 'lucide-react';
import { searchHistory } from '../api';

const EXAMPLES = [
  'What causes piping erection delays?',
  'Average delay for electrical cable pulling',
  'Which discipline is most delayed?',
  'Historical hydrotest completion rate',
];

export default function KnowledgeBase() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (q) => {
    const text = q || query;
    if (!text.trim() || loading) return;
    setQuery(text);
    setLoading(true);
    try {
      const res = await searchHistory(text);
      setResult(res);
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Institutional Memory</h1>
        <p className="page-subtitle">
          Ask the archive of completed projects in plain English.
          Knowledge that used to leave with the project team.
        </p>
      </div>

      <div className="card mb-4">
        <div className="flex gap-2">
          <input
            className="form-input"
            type="search"
            placeholder="Which piping activities delay most often?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button className="btn btn-primary" onClick={() => handleSearch()} disabled={loading || !query.trim()}>
            <Search size={16} /> Ask
          </button>
        </div>
        <div className="flex gap-2 mt-4" style={{ flexWrap: 'wrap' }}>
          <span className="text-xs text-muted">Try:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              className="btn btn-ghost btn-sm"
              onClick={() => handleSearch(ex)}
              disabled={loading}
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="loading-overlay"><div className="spinner" /> Searching knowledge base...</div>
      )}

      {result && !result.error && (
        <div className="flex-col gap-4">
          {result.summary && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: 8 }}>
                <BookOpen size={16} style={{ verticalAlign: -3, marginRight: 6 }} />
                Answer
              </div>
              <p className="text-sm" style={{ lineHeight: 1.7 }}>{result.answer || result.summary}</p>
              {result.intent && (
                <div className="text-xs text-muted mt-2">Intent: {result.intent}</div>
              )}
            </div>
          )}

          {result.supporting_records?.length > 0 && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: 12 }}>
                Supporting Records ({result.supporting_records.length} of {result.total_records || '?'})
              </div>
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Activity Type</th>
                      <th>Discipline</th>
                      <th>Outcome</th>
                      <th>Variance</th>
                      <th>Cause</th>
                      <th>Similarity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.supporting_records.map((r, i) => (
                      <tr key={i}>
                        <td>{r.activity_type || '—'}</td>
                        <td>{r.discipline || '—'}</td>
                        <td>
                          <span className={`badge badge-${r.outcome === 'delayed' ? 'high' : r.outcome === 'on_time' ? 'low' : 'muted'}`}>
                            {r.outcome || '—'}
                          </span>
                        </td>
                        <td className="mono">{r.variance_days != null ? `${r.variance_days}d` : '—'}</td>
                        <td className="truncate" style={{ maxWidth: 200 }}>{r.delay_cause || '—'}</td>
                        <td className="mono">{r.similarity != null ? `${(r.similarity * 100).toFixed(0)}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {result?.error && (
        <div className="card">
          <p className="text-sm" style={{ color: 'var(--danger)' }}>{result.error}</p>
        </div>
      )}
    </div>
  );
}
