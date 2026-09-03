import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic } from 'lucide-react';
import { useAuth } from '../App';
import { supervisorMessage, supervisorClarify } from '../api';

export default function Supervisor() {
  const { user } = useAuth();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pendingClarification, setPendingClarification] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  const addMsg = (type, text, extra) => {
    setMessages((prev) => [...prev, { type, text, extra, ts: new Date().toISOString() }]);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    addMsg('user', text);
    setLoading(true);

    try {
      const res = await supervisorMessage(text, user?.username || 'supervisor');

      if (res.clarification) {
        const c = res.clarification;
        setPendingClarification(c);
        addMsg('clarification', c.question, { options: c.options, clarification_id: c.clarification_id });
      } else if (res.event) {
        const ev = res.event;
        addMsg('success', `Event extracted: ${ev.description}`, {
          event_id: ev.event_id,
          confidence: ev.match_confidence,
          link_state: ev.link_state,
          matched: ev.matched_activity_id,
        });
        setPendingClarification(null);
      } else {
        addMsg('system', 'Processed — check the events page for details.');
      }
    } catch (err) {
      addMsg('system', `Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClarify = async (index) => {
    if (!pendingClarification || loading) return;
    const option = pendingClarification.options[index];
    addMsg('user', option.label || option.text || `Option ${index + 1}`);
    setLoading(true);

    try {
      const res = await supervisorClarify(
        pendingClarification.clarification_id,
        index,
        user?.username || 'supervisor'
      );
      if (res.event) {
        addMsg('success', `Linked to ${res.event.matched_activity_id || 'schedule'}: ${res.event.description}`, {
          event_id: res.event.event_id,
          confidence: res.event.match_confidence,
          link_state: res.event.link_state,
        });
      } else {
        addMsg('system', 'Clarification applied.');
      }
      setPendingClarification(null);
    } catch (err) {
      addMsg('system', `Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Supervisor Input</h1>
        <p className="page-subtitle">
          Report what happened on site. Say it the way you would on the field — if
          SYNAPSE can't tell which activity you mean, it asks one question rather than guessing.
        </p>
      </div>

      <div className="grid-2">
        <div className="console-container">
          <div className="console-messages" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="console-empty">
                Send a message to start. Try: "Erection completed today."
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i}>
                <div className={`msg msg-${m.type}`}>
                  {m.text}
                </div>
                {m.extra?.options && (
                  <div className="flex gap-2 mt-2" style={{ flexWrap: 'wrap', paddingLeft: 4 }}>
                    {m.extra.options.map((opt, idx) => (
                      <button
                        key={idx}
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleClarify(idx)}
                        disabled={loading || !pendingClarification}
                      >
                        {opt.label || opt.text || opt.activity_id || `Option ${idx + 1}`}
                      </button>
                    ))}
                  </div>
                )}
                {m.extra?.event_id && (
                  <div className="text-xs text-muted mt-2" style={{ paddingLeft: 4 }}>
                    <span className="font-mono">{m.extra.event_id}</span>
                    {m.extra.confidence != null && (
                      <> &middot; Confidence: {(m.extra.confidence * 100).toFixed(0)}%</>
                    )}
                    {m.extra.link_state && <> &middot; {m.extra.link_state.replace(/_/g, ' ')}</>}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="msg msg-system" style={{ opacity: 0.6 }}>
                <div className="spinner" style={{ width: 14, height: 14 }} />
              </div>
            )}
          </div>

          <div className="console-input">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="e.g. Erection completed today."
              disabled={loading}
            />
            <button className="btn btn-primary" onClick={handleSend} disabled={loading || !input.trim()}>
              <Send size={16} />
            </button>
          </div>
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>How it works</div>
          <div className="flex-col gap-3">
            {[
              { step: '1', title: 'You report', desc: 'Type or speak what happened on site.' },
              { step: '2', title: 'SYNAPSE extracts', desc: 'NLP identifies the event, discipline, asset, and status.' },
              { step: '3', title: 'Clarification', desc: 'If ambiguous, one targeted question is asked.' },
              { step: '4', title: 'Matching', desc: 'Seven-layer engine finds the right schedule activity.' },
              { step: '5', title: 'Confidence', desc: 'HIGH → auto-linked. MEDIUM → review queue. LOW → flagged.' },
            ].map((s) => (
              <div key={s.step} className="flex gap-3 items-center">
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'var(--primary)', color: '#fff',
                  display: 'grid', placeItems: 'center',
                  fontSize: 12, fontWeight: 600, flexShrink: 0
                }}>
                  {s.step}
                </div>
                <div>
                  <div className="font-semibold text-sm">{s.title}</div>
                  <div className="text-xs text-muted">{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
