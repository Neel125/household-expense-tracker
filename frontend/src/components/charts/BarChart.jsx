import { fmtINR, shortINR } from '../../lib/format';
import { useContainerWidth, fitLabel } from '../../lib/useSize';

function niceMax(v) {
  if (v <= 0) return 10;
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / mag;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * mag;
}

// categories: string[]; series: [{ name, color, values:number[] }]
export default function BarChart({ categories, series }) {
  // Draw at 1:1 with the container so font sizes below are real pixels at
  // any width — see useContainerWidth.
  const [wrapRef, cw] = useContainerWidth();
  const W = Math.max(240, cw);
  const H = Math.round(Math.min(260, Math.max(168, W * 0.42)));

  const allVals = series.flatMap((s) => s.values);
  const maxV = Math.max(0, ...allVals);
  const minV = Math.min(0, ...allVals);
  const topMax = niceMax(Math.max(maxV, -minV, 1));
  const botMax = minV < 0 ? niceMax(-minV) : 0;
  const padL = 46, padR = 10, padT = 12, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const denom = topMax + botMax || 1;
  const zeroY = padT + plotH * (topMax / denom);
  const yScale = (v) => zeroY - (v / denom) * plotH;

  // Fewer gridlines when there's little vertical room to label them.
  const steps = plotH < 150 ? 3 : 4;
  const gridLines = [];
  for (let i = 0; i <= steps; i++) {
    const v = topMax - i * (topMax / steps);
    gridLines.push({ v, y: yScale(v) });
  }

  const n = categories.length, s = series.length;
  // Groups get at most ~200px each and the whole band is centred in the plot.
  // Without this, one or two categories on a full-width card leave the bars
  // marooned in empty space (and uncapped they become unreadable slabs).
  const bandW = Math.min(plotW, Math.max(n, 1) * 200);
  const bandX = padL + (plotW - bandW) / 2;
  const groupW = bandW / Math.max(n, 1);
  const barGap = groupW < 40 ? 3 : 6;
  const barW = Math.min(56, Math.max(4, (groupW - barGap * (s + 1)) / s));
  const clusterW = barW * s + barGap * (s - 1);
  // Every other tick once labels would otherwise overlap.
  const tickEvery = groupW < 44 ? 2 : 1;

  return (
    <div ref={wrapRef}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display: 'block', overflow: 'visible' }}>
        {gridLines.map((g, i) => (
          <g key={i}>
            <line x1={padL} x2={W - padR} y1={g.y} y2={g.y} style={{ stroke: 'var(--chart-grid)', strokeWidth: 1 }} />
            <text x={padL - 8} y={g.y + 3} textAnchor="end" style={{ fill: 'var(--chart-muted)', fontSize: 9.5 }}>
              {shortINR(g.v)}
            </text>
          </g>
        ))}
        {botMax > 0 && (
          <g>
            <line x1={padL} x2={W - padR} y1={yScale(-botMax)} y2={yScale(-botMax)} style={{ stroke: 'var(--chart-grid)', strokeWidth: 1 }} />
            <text x={padL - 8} y={yScale(-botMax) + 3} textAnchor="end" style={{ fill: 'var(--chart-muted)', fontSize: 9.5 }}>
              {shortINR(-botMax)}
            </text>
          </g>
        )}
        <line x1={padL} x2={W - padR} y1={zeroY} y2={zeroY} style={{ stroke: 'var(--chart-axis)', strokeWidth: 1.2 }} />

        {categories.map((cat, ci) => {
          const groupX = bandX + ci * groupW;
          return (
            <g key={cat + ci}>
              {series.map((ser, si) => {
                const v = ser.values[ci] || 0;
                const x = groupX + (groupW - clusterW) / 2 + si * (barW + barGap);
                const y0 = yScale(0), y1 = yScale(v);
                const y = Math.min(y0, y1), h = Math.max(1, Math.abs(y1 - y0));
                return (
                  <rect key={ser.name} x={x} y={y} width={barW} height={h} rx={Math.min(3, barW / 3)} style={{ fill: ser.color }}>
                    <title>{`${ser.name} — ${cat}: ${fmtINR(v)}`}</title>
                  </rect>
                );
              })}
              {ci % tickEvery === 0 && (
                <text x={groupX + groupW / 2} y={H - 10} textAnchor="middle" style={{ fill: 'var(--chart-muted)', fontSize: 10 }}>
                  {fitLabel(cat, groupW * tickEvery - 4)}
                  <title>{cat}</title>
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {series.length > 1 && (
        <div className="legend" style={{ marginTop: 10 }}>
          {series.map((ser) => (
            <div className="item" key={ser.name}>
              <span className="sw" style={{ background: ser.color }}></span>
              {ser.name}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
