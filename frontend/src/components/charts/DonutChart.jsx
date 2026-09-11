import { fmtINR, shortINR, sum } from '../../lib/format';
import { useContainerWidth } from '../../lib/useSize';

// data: [{ label, value, color }]
export default function DonutChart({ data }) {
  // 1:1 with the container (see useContainerWidth) so the centre total stays
  // readable whether the card is 260px or 600px wide.
  const [wrapRef, cw] = useContainerWidth(300);
  const total = sum(data, (d) => d.value);

  const W = Math.max(200, cw);
  const d = Math.round(Math.min(220, Math.max(140, W * 0.62)));
  const cx = W / 2, cy = d / 2;
  const rOuter = d / 2 - 4;
  const rInner = rOuter * 0.62;

  if (total <= 0) {
    return (
      <div ref={wrapRef}>
        <div className="empty">No spend logged for this month yet.</div>
      </div>
    );
  }

  let angle = -Math.PI / 2;
  const slices = data
    .filter((s) => s.value > 0)
    .map((s) => {
      const frac = s.value / total;
      const a0 = angle;
      const a1 = angle + frac * Math.PI * 2;
      angle = a1;
      const large = a1 - a0 > Math.PI ? 1 : 0;
      const x0 = cx + rOuter * Math.cos(a0), y0 = cy + rOuter * Math.sin(a0);
      const x1 = cx + rOuter * Math.cos(a1), y1 = cy + rOuter * Math.sin(a1);
      const xi0 = cx + rInner * Math.cos(a1), yi0 = cy + rInner * Math.sin(a1);
      const xi1 = cx + rInner * Math.cos(a0), yi1 = cy + rInner * Math.sin(a0);
      const path = `M ${x0} ${y0} A ${rOuter} ${rOuter} 0 ${large} 1 ${x1} ${y1} L ${xi0} ${yi0} A ${rInner} ${rInner} 0 ${large} 0 ${xi1} ${yi1} Z`;
      return { ...s, path };
    });

  return (
    <div ref={wrapRef}>
      <svg viewBox={`0 0 ${W} ${d}`} width="100%" height={d} style={{ display: 'block' }}>
        {slices.map((s) => (
          <path key={s.label} d={s.path} style={{ fill: s.color }} stroke="var(--chart-surface)" strokeWidth="2">
            <title>{`${s.label}: ${fmtINR(s.value)} (${Math.round((s.value / total) * 100)}%)`}</title>
          </path>
        ))}
        <text x={cx} y={cy - 3} textAnchor="middle" style={{ fill: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 16 }}>
          {shortINR(total)}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" style={{ fill: 'var(--chart-muted)', fontSize: 10 }}>
          total
        </text>
      </svg>
      <div className="legend" style={{ marginTop: 14 }}>
        {data.map((s) => {
          const pct = total > 0 ? Math.round((s.value / total) * 100) : 0;
          return (
            <div className="item" key={s.label}>
              <span className="sw" style={{ background: s.color }}></span>
              {s.label} — {fmtINR(s.value)} <span style={{ color: 'var(--text-muted)' }}>({pct}%)</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
