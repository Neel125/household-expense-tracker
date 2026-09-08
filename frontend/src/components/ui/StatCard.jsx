import { fmtINR } from '../../lib/format';

// A KPI tile. `value` is formatted as INR unless `raw` is set (e.g. "42%").
export default function StatCard({ label, value, foot, raw = false, tone }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className={'value' + (tone ? ' tone-' + tone : '')}>{raw ? value : fmtINR(value)}</div>
      {foot && <div className="foot">{foot}</div>}
    </div>
  );
}
