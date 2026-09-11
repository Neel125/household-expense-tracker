import { monthLabel } from '../../lib/format';
import Select from './Select';

// A month dropdown. months: sorted ["YYYY-MM"]. Set includeAll to offer an
// "All time" / "All months" entry.
export default function MonthSelect({ months, value, onChange, includeAll = false, allLabel = 'All months' }) {
  const options = [];
  if (months.length === 0 && !includeAll) options.push({ value: '', label: '—' });
  for (const mo of months.slice().reverse()) {
    options.push({ value: mo, label: monthLabel(mo) });
  }
  return (
    <Select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={includeAll ? allLabel : undefined}
      options={options}
    />
  );
}
