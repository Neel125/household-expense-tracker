export const VEHICLE_KINDS = [
  { value: 'car', label: 'Car', icon: '🚗' },
  { value: 'bike', label: 'Bike', icon: '🏍️' },
  { value: 'scooter', label: 'Scooter', icon: '🛵' },
  { value: 'other', label: 'Other', icon: '🚛' },
];

export const FUELS = [
  { value: 'petrol', label: 'Petrol' },
  { value: 'diesel', label: 'Diesel' },
  { value: 'cng', label: 'CNG' },
  { value: 'ev', label: 'Electric' },
  { value: 'hybrid', label: 'Hybrid' },
];

export const RECORD_KINDS = [
  { value: 'maintenance', label: 'Service', icon: '🔧', vendor: 'Workshop', hasExpiry: false, hasOdo: true },
  { value: 'insurance', label: 'Insurance', icon: '🛡', vendor: 'Insurer', hasExpiry: true, hasOdo: false },
  { value: 'puc', label: 'PUC', icon: '🌿', vendor: 'Centre', hasExpiry: true, hasOdo: false },
  { value: 'rc', label: 'RC', icon: '📄', vendor: 'RTO', hasExpiry: true, hasOdo: false },
  { value: 'challan', label: 'Challan', icon: '⚠', vendor: 'Location / authority', hasExpiry: false, hasOdo: false, hasStatus: true },
  { value: 'fitness', label: 'Fitness', icon: '✅', vendor: 'RTO', hasExpiry: true, hasOdo: false },
  { value: 'other', label: 'Other', icon: '◎', vendor: 'Vendor', hasExpiry: false, hasOdo: false },
];

export const CHALLAN_STATUSES = [
  { value: 'unpaid', label: 'Unpaid' },
  { value: 'paid', label: 'Paid' },
  { value: 'contested', label: 'Contested' },
];

export function vehicleIcon(kind) {
  return VEHICLE_KINDS.find((k) => k.value === kind)?.icon || '🚗';
}

export function recordMeta(kind) {
  return RECORD_KINDS.find((k) => k.value === kind) || RECORD_KINDS[RECORD_KINDS.length - 1];
}

export function daysUntil(iso) {
  if (!iso) return null;
  const t = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(t.getTime())) return null;
  const n = new Date();
  n.setHours(0, 0, 0, 0);
  return Math.round((t - n) / 86400000);
}

export function paperTone(daysLeft) {
  if (daysLeft == null) return '';
  if (daysLeft < 0) return 'debt';
  if (daysLeft <= 30) return 'warning';
  return 'good';
}

export function paperLabel(daysLeft) {
  if (daysLeft == null) return 'Not on file';
  if (daysLeft < 0) return `${Math.abs(daysLeft)}d overdue`;
  if (daysLeft === 0) return 'Due today';
  return `${daysLeft}d left`;
}
