import React, { useState, useEffect } from 'react';
import { Upload, FileText, CloudUpload, Zap } from 'lucide-react';
import { getDemoSources, loadSample, uploadDocument, extractFromText, seedDemo } from '../api';

export default function Ingest() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [pasteText, setPasteText] = useState('');
  const [file, setFile] = useState(null);
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    getDemoSources().then((res) => setSources(res.sources || [])).catch(console.error);
  }, []);

  const handleSeedDemo = async () => {
    setSeeding(true);
    setResult(null);
    try {
      const res = await seedDemo();
      setResult({ ...res, _seed: true });
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setSeeding(false);
    }
  };

  const handleLoadSample = async (path) => {
    setLoading(true);
    setResult(null);
    try {
      const res = await loadSample(path);
      setResult(res);
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await uploadDocument(file);
      setResult(res);
      setFile(null);
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleExtract = async () => {
    if (!pasteText.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await extractFromText(pasteText);
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
        <h1 className="page-title">Upload & Ingest</h1>
        <p className="page-subtitle">
          Daily progress reports, discipline spreadsheets, and pasted text all enter the same pipeline.
        </p>
      </div>

      <div className="card mb-4" style={{ background: 'var(--primary-dim, #0d2a26)', border: '1px solid var(--primary)' }}>
        <div className="flex items-center gap-3" style={{ flexWrap: 'wrap' }}>
          <Zap size={20} color="var(--primary)" style={{ flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div className="font-semibold text-sm">Load all demo data in one click</div>
            <div className="text-xs text-muted mt-1">Ingests all 3 DPRs + 2 discipline sheets (Oil India sample dataset) and seeds the Conflict Resolution queue for showcase.</div>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleSeedDemo}
            disabled={seeding || loading}
            style={{ flexShrink: 0 }}
          >
            <Zap size={16} /> {seeding ? 'Loading...' : 'Load demo data'}
          </button>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>Sample Sources</div>
          <p className="text-xs text-muted mb-4">Bundled Oil India site data — one click to ingest.</p>
          <div className="flex-col gap-2">
            {sources.map((s) => (
              <button
                key={s.path}
                className="btn btn-ghost w-full"
                style={{ justifyContent: 'flex-start' }}
                onClick={() => handleLoadSample(s.path)}
                disabled={loading}
              >
                <FileText size={16} />
                <span>{s.name}</span>
                <span className="text-xs text-muted" style={{ marginLeft: 'auto' }}>{s.kind}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>Upload Document</div>
          <p className="text-xs text-muted mb-4">PDF, TXT, CSV, or Excel.</p>
          <input
            type="file"
            className="form-input"
            accept=".txt,.md,.csv,.xlsx,.xls,.pdf"
            onChange={(e) => setFile(e.target.files[0] || null)}
          />
          <button
            className="btn btn-primary mt-4"
            onClick={handleUpload}
            disabled={loading || !file}
          >
            <CloudUpload size={16} /> Process document
          </button>

          <div className="card-title" style={{ marginTop: 24, marginBottom: 8 }}>Or Paste Text</div>
          <textarea
            className="form-input"
            placeholder="=== PIPING ===&#10;Line 24 spool erection completed today at Unit 4."
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            rows={4}
          />
          <button
            className="btn btn-primary mt-4"
            onClick={handleExtract}
            disabled={loading || !pasteText.trim()}
          >
            <Upload size={16} /> Extract events
          </button>
        </div>
      </div>

      {loading && (
        <div className="loading-overlay"><div className="spinner" /> Processing...</div>
      )}

      {result && (
        <div className="card mt-4">
          <div className="card-title" style={{ marginBottom: 8 }}>Result</div>
          {result.error ? (
            <p className="text-sm" style={{ color: 'var(--danger)' }}>{result.error}</p>
          ) : result._seed ? (
            <div>
              <p className="text-sm font-semibold mb-2" style={{ color: 'var(--primary)' }}>{result.message}</p>
              {(result.loaded || []).map((f, i) => (
                <div key={i} className="flex gap-3 text-xs text-muted" style={{ padding: '3px 0' }}>
                  <span className="font-mono">{f.file}</span>
                  <span>{f.events} events</span>
                </div>
              ))}
              <p className="text-xs mt-2 text-muted">Check the Review Queue and Conflict Resolution pages.</p>
            </div>
          ) : (
            <div>
              <p className="text-sm mb-2">
                {result.events_extracted != null
                  ? `${result.events_extracted} events extracted`
                  : result.events?.length != null
                    ? `${result.events.length} events extracted`
                    : 'Processing complete'}
              </p>
              {(result.events || []).slice(0, 5).map((ev, i) => (
                <div key={i} className="flex gap-2 items-center text-sm" style={{ padding: '6px 0', borderBottom: '1px solid var(--border-light)' }}>
                  <span className="font-mono">{ev.event_id}</span>
                  <span className="truncate">{ev.description}</span>
                  <span className="badge badge-info">{ev.discipline || '—'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
