import { useEffect, useState } from 'react';

/** The pending state while a run is in flight. */
export default function ThinkingIndicator({ startedAt }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.round((Date.now() - startedAt) / 1000)), 500);
    return () => clearInterval(id);
  }, [startedAt]);
  return (
    <div className="chat-thinking">
      <span className="chat-dots" aria-hidden="true"><i /><i /><i /></span>
      {/* An agent run reads the ledger over several steps and routinely
          takes 10–30s. Saying so beats a spinner that looks stuck. */}
      <span>Reading your books{elapsed >= 3 ? ` · ${elapsed}s` : ''}</span>
    </div>
  );
}
