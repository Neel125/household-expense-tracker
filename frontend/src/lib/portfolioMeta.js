// Kind registries for investments and debts: labels, icons and chart
// colours. Shared so the Portfolio page and the Dashboard can never
// disagree about what "ppf_epf" is called or what colour an FD is.
// The backend validates the raw strings (models/investment.py, debt.py).
export const INVESTMENT_KINDS = [
  { value: 'fd', label: 'Fixed Deposit', icon: '🏦' },
  { value: 'rd', label: 'Recurring Deposit', icon: '📆' },
  { value: 'sip', label: 'SIP', icon: '📈' },
  { value: 'mutual_fund', label: 'Mutual Fund', icon: '📊' },
  { value: 'stock', label: 'Stocks', icon: '💹' },
  { value: 'bond', label: 'Bond', icon: '📜' },
  { value: 'gold', label: 'Gold / SGB', icon: '🪙' },
  { value: 'ppf_epf', label: 'PPF / EPF / NPS', icon: '🛡️' },
  { value: 'other', label: 'Other', icon: '📦' },
];
export const INV_META = Object.fromEntries(INVESTMENT_KINDS.map((k) => [k.value, k]));
// Nine kinds against a six-colour ramp, so three take fixed mid-tones
// that read the same in both themes. Ordered to keep neighbouring slices
// of a donut apart rather than to match the list order.
export const INV_COLORS = {
  fd: 'var(--series-4)', /* sky */
  rd: 'var(--series-1)', /* teal */
  sip: 'var(--series-3)', /* lime */
  mutual_fund: 'var(--series-5)', /* violet */
  stock: 'var(--series-6)', /* rose */
  gold: 'var(--series-2)', /* amber */
  bond: '#64748B', /* slate */
  ppf_epf: '#6366F1', /* indigo */
  other: '#94A3B8', /* grey */
};

export const DEBT_KINDS = [
  { value: 'home_loan', label: 'Home Loan', icon: '🏠' },
  { value: 'car_loan', label: 'Car Loan', icon: '🚗' },
  { value: 'personal_loan', label: 'Personal Loan', icon: '💳' },
  { value: 'consumer_loan', label: 'Consumer / EMI', icon: '📱' },
  { value: 'education_loan', label: 'Education Loan', icon: '🎓' },
  { value: 'business_loan', label: 'Business Loan', icon: '🏢' },
  { value: 'credit_card_debt', label: 'Credit Card Debt', icon: '💳' },
  { value: 'other', label: 'Other', icon: '📦' },
];
export const DEBT_META = Object.fromEntries(DEBT_KINDS.map((k) => [k.value, k]));
