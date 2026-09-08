export function fmtINR(n) {
  const v = Math.round(Number(n) || 0);
  const neg = v < 0;
  const abs = Math.abs(v).toLocaleString('en-IN');
  return (neg ? '−' : '') + '₹' + abs;
}

export function shortINR(n) {
  const v = Number(n) || 0;
  const a = Math.abs(v);
  let s;
  if (a >= 100000) s = (v / 100000).toFixed(a % 100000 === 0 ? 0 : 1) + 'L';
  else if (a >= 1000) s = (v / 1000).toFixed(a % 1000 === 0 ? 0 : 1) + 'k';
  else s = String(Math.round(v));
  return '₹' + s;
}

export function monthKey(dateStr) {
  return (dateStr || '').slice(0, 7);
}

export function monthLabel(mk) {
  if (!mk) return '';
  const [y, m] = mk.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
}

export function sum(arr, f) {
  return arr.reduce((a, t) => a + (f ? f(t) : Number(t.amount) || 0), 0);
}

// "2026-09-27" -> "27 Sep". Used on narrow screens where the full ISO date
// would force the table to scroll sideways.
export function shortDate(dateStr) {
  const [y, m, d] = (dateStr || '').split('-').map(Number);
  if (!y || !m || !d) return dateStr || '';
  return d + ' ' + new Date(y, m - 1, d).toLocaleDateString('en-IN', { month: 'short' });
}
