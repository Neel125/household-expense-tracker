import { fmtINR, shortINR } from '../../lib/format';
import { useContainerWidth, fitLabel } from '../../lib/useSize';

function niceMax(v) {
  if (v <= 0) return 10;
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / mag;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * mag;
}

// A dependency-free line/area chart, matching BarChart's conventions:
// drawn 1:1 with the container so label sizes are real pixels at any
// width, ₹-shortened gridline labels, and a <title> on every point for
// the browser's own tooltip.
//
// categories: string[]; series: [{ name, color, values:number[], area?:bool }]
export default function LineChart({ categories, series, height }) {
  const [wrapRef, cw] = useContainerWidth();
  const W = Math.max(240, cw);
  const H = height || Math.round(Math.min(260, Math.max(168, W * 0.42)));

  const allVals = series.flatMap((s) => s.values);
  const maxV = Math.max(0, ...allVals);
  const minV = Math.min(0, ...allVals);
  const topMax = niceMax(Math.max(maxV, 1));
  const botMax = minV < 0 ? niceMax(-minV) : 0;
  const padL = 46, padR = 12, padT = 12, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const denom = topMax + botMax || 1;
  const zeroY = padT + plotH * (topMax / denom);
  const yScale = (v) => zeroY - (v / denom) * plotH;

  const n = Math.max(categories.length, 1);
  // A single point has no line to draw, so it sits in the middle rather
  // than pinned to the left edge.
  const xScale = (i) => (n === 1 ? padL + plotW / 2 : padL + (i / (n - 1)) * plotW);

  const steps = plotH < 150 ? 3 : 4;
  const gridLines = [];
  for (let i = 0; i <= steps; i++) {
    const v = topMax - i * (topMax / steps);
    gridLines.push({ v, y: yScale(v) });
  }

  const tickEvery = plotW / n < 44 ? Math.ceil(44 / (plotW / n)) : 1;
  const dotR = n > 14 ? 0 : n > 8 ? 2 : 2.8;

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

        {series.map((ser) => {
          const pts = ser.values.map((v, i) => `${xScale(i)},${yScale(v || 0)}`);
          const line = 'M ' + pts.join(' L ');
          const areaPath =
            ser.area && pts.length > 1
              ? `${line} L ${xScale(ser.values.length - 1)},${zeroY} L ${xScale(0)},${zeroY} Z`
              : null;
          return (
            <g key={ser.name}>
              {areaPath && <path d={areaPath} style={{ fill: ser.color, opacity: 0.14 }} />}
              <path
                d={line}
                style={{ fill: 'none', stroke: ser.color, strokeWidth: 2, strokeLinejoin: 'round', strokeLinecap: 'round' }}
              />
              {dotR > 0 &&
                ser.values.map((v, i) => (
                  <circle
                    key={i}
                    cx={xScale(i)}
                    cy={yScale(v || 0)}
                    r={dotR}
                    style={{ fill: 'var(--chart-surface)', stroke: ser.color, strokeWidth: 1.8 }}
                  >
                    <title>{`${ser.name} — ${categories[i]}: ${fmtINR(v)}`}</title>
                  </circle>
                ))}
            </g>
          );
        })}

        {categories.map((cat, i) =>
          i % tickEvery === 0 ? (
            <text
              key={cat + i}
              x={xScale(i)}
              y={H - 10}
              textAnchor={i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}
              style={{ fill: 'var(--chart-muted)', fontSize: 10 }}
            >
              {fitLabel(cat, (plotW / n) * tickEvery + 8)}
              <title>{cat}</title>
            </text>
          ) : null
        )}
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
