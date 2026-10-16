import { useState } from 'react';

// How an assistant answer is drawn. Kept out of the page because it is
// the part with real structure — insights, actions, the figures a claim
// rests on — and because it can then be rendered against a payload in a
// test without standing up the whole chat.

function Severity({ level }) {
  const label = { high: 'Important', medium: 'Worth noting', low: 'Minor' }[level] || '';
  if (!label) return null;
  return <span className={'sev sev-' + level}>{label}</span>;
}

/** The assistant's typed answer, rendered section by section. */
export default function AssistantAnswer({ result, meta }) {
  const [showWork, setShowWork] = useState(false);
  const insights = result.insights || [];
  const actions = result.actions || [];
  const figures = result.figuresUsed || [];
  const gaps = result.dataGaps || [];
  const tools = meta?.toolCalls || [];

  return (
    <div className="chat-answer">
      {result.answer && <p className="chat-lead">{result.answer}</p>}
      {result.summary && result.summary !== result.answer && <p>{result.summary}</p>}

      {insights.length > 0 && (
        <div className="chat-block">
          {insights.map((it, i) => (
            <div className="chat-item" key={i}>
              <div className="chat-item-head">
                <strong>{it.title}</strong>
                <Severity level={it.severity} />
              </div>
              {it.detail && <div className="chat-item-body">{it.detail}</div>}
              {it.evidence && <div className="chat-evidence">{it.evidence}</div>}
            </div>
          ))}
        </div>
      )}

      {actions.length > 0 && (
        <div className="chat-block">
          <div className="chat-block-label">What you could do</div>
          {actions.map((a, i) => (
            <div className="chat-item" key={i}>
              <div className="chat-item-head">
                <strong>{a.title}</strong>
                <Severity level={a.priority} />
              </div>
              {a.detail && <div className="chat-item-body">{a.detail}</div>}
              {a.expectedImpact && <div className="chat-evidence">{a.expectedImpact}</div>}
            </div>
          ))}
        </div>
      )}

      {figures.length > 0 && (
        <div className="chat-figures">
          {figures.map((f, i) => (
            <span className="chat-figure" key={i}>{f}</span>
          ))}
        </div>
      )}

      {gaps.length > 0 && (
        <div className="chat-gaps">
          <strong>To answer this better, the books would need:</strong>
          <ul>{gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
        </div>
      )}

      {tools.length > 0 && (
        <div className="chat-work">
          <button className="chat-work-toggle" onClick={() => setShowWork((v) => !v)}>
            {showWork ? 'Hide' : 'Show'} how this was worked out
          </button>
          {showWork && (
            <div className="chat-work-body">
              {/* Every figure above came out of one of these. Naming them
                  is what lets a household check the answer instead of
                  trusting it. */}
              <div>Read: {[...new Set(tools)].join(', ')}</div>
              {meta?.durationMs ? <div>Took {(meta.durationMs / 1000).toFixed(1)}s</div> : null}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
