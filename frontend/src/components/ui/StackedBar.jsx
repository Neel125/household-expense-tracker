import { fmtINR } from '../../lib/format';

// One horizontal bar that decomposes a total, with a keyed legend under
// it. Used for "where the month's money went" — a donut hides the fact
// that these parts sum to a meaningful whole, and a bar doesn't.
//
// segments: [{ label, value, color, hint? }]
export default function StackedBar({ segments, height = 14 }) {
  const rows = segments.filter((s) => (Number(s.value) || 0) > 0);
  const total = rows.reduce((a, s) => a + Number(s.value), 0);
  if (total <= 0) return <div className="empty">Nothing to split yet.</div>;

  return (
    <div>
      <div className="stackbar" style={{ height }}>
        {rows.map((s) => (
          <span
            key={s.label}
            style={{ width: (s.value / total) * 100 + '%', background: s.color }}
            title={`${s.label}: ${fmtINR(s.value)} (${Math.round((s.value / total) * 100)}%)`}
          />
        ))}
      </div>
      <div className="stackbar-key">
        {rows.map((s) => (
          <div className="stackbar-item" key={s.label}>
            <span className="sw" style={{ background: s.color }} />
            <div className="stackbar-text">
              <div className="stackbar-label">
                {s.label}
                <span className="note"> {Math.round((s.value / total) * 100)}%</span>
              </div>
              <div className="num stackbar-value">{fmtINR(s.value)}</div>
              {s.hint && <div className="note">{s.hint}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
