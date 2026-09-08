import { monthLabel } from '../../lib/format';

// A month dropdown. months: sorted ["YYYY-MM"]. Set includeAll to offer an
// "All time" / "All months" entry.
export default function MonthSelect({ months, value, onChange, includeAll = false, allLabel = 'All months' }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {includeAll && <option value="">{allLabel}</option>}
      {months.length === 0 && !includeAll && <option value="">—</option>}
      {months
        .slice()
        .reverse()
        .map((mo) => (
          <option key={mo} value={mo}>
            {monthLabel(mo)}
          </option>
        ))}
    </select>
  );
}
