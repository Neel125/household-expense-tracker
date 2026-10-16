import { sum, monthKey } from './format';

// Everything here mirrors the original spreadsheet's formulas: a credit
// card purchase is an expense the day it's made (accrual), regardless of
// payment mode; the later repayment is cash leaving the bank, not a
// second expense, so it's excluded from accrual totals and necessity
// buckets to avoid double-counting. Income is likewise excluded from
// spend — it feeds the income-vs-expense and savings-rate views instead.

function isLoanOutflow(t) {
  return t.type === 'Loan' || t.type === 'Loan Partial';
}

// Credits a bank/cash/debit running balance without being household income.
function isBankCredit(t) {
  return t.type === 'Income' || t.type === 'Investment Withdrawal';
}

function isNotSpend(t) {
  return t.type === 'CC Repayment' || isBankCredit(t);
}

export function inScope(list, scope, profile) {
  return scope === 'mine' && profile ? list.filter((t) => t.member === profile) : list;
}

export function availableMonths(transactions) {
  const s = new Set(transactions.map((t) => monthKey(t.date)).filter(Boolean));
  return Array.from(s).sort();
}

export function monthTxns(transactions, scope, profile, mk) {
  return inScope(transactions, scope, profile).filter((t) => monthKey(t.date) === mk);
}

// The same, cut off at a day of the month. Comparing a month in progress
// against a whole previous month makes every category look like it
// collapsed, so the dashboard compares the same slice of both.
// `maxDay` of 0 means "no cutoff".
export function monthTxnsUpTo(transactions, scope, profile, mk, maxDay) {
  const list = monthTxns(transactions, scope, profile, mk);
  if (!maxDay) return list;
  return list.filter((t) => Number((t.date || '').slice(8, 10)) <= maxDay);
}

export function thisMonthKey(today = new Date()) {
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
}

// The shared arithmetic: hand it any set of transactions (a month, a
// person, a person's month) and it applies the accrual-vs-cash rules once.
function aggregate(list) {
  const spendable = list.filter((t) => !isNotSpend(t));
  const accrual = sum(spendable);
  const cashOutflow =
    sum(list.filter((t) => !isNotSpend(t) && t.paymentMode !== 'Credit Card')) +
    sum(list.filter((t) => t.type === 'CC Repayment'));
  const stillOnCC = sum(list.filter((t) => t.paymentMode === 'Credit Card' && t.type !== 'CC Repayment'));
  const ccRepaid = sum(list.filter((t) => t.type === 'CC Repayment'));

  const income = sum(list.filter((t) => t.type === 'Income'));
  const investments = sum(list.filter((t) => t.type === 'Investment'));
  const loanPaid = sum(list.filter(isLoanOutflow));
  // Consumption = day-to-day spend + loan outflow; investments are savings,
  // not consumption, so they're left out of the savings-rate denominator.
  const consumption = sum(list.filter((t) => t.type === 'Expense')) + loanPaid;

  const necessity = { Need: 0, Want: 0, Investment: 0, Debt: 0 };
  spendable.forEach((t) => {
    necessity[t.necessity] = (necessity[t.necessity] || 0) + (Number(t.amount) || 0);
  });
  const wants = spendable.filter((t) => t.necessity === 'Want').sort((a, b) => b.amount - a.amount);

  return {
    spendable,
    accrual,
    cashOutflow,
    stillOnCC,
    ccRepaid,
    income,
    investments,
    loanPaid,
    consumption,
    savings: income - consumption,
    savingsRate: income > 0 ? (income - consumption) / income : 0,
    necessity,
    wants,
  };
}

export function computeMonth(transactions, scope, profile, mk) {
  const list = monthTxns(transactions, scope, profile, mk);
  return { list, ...aggregate(list) };
}

export function computeMonthUpTo(transactions, scope, profile, mk, maxDay) {
  const list = monthTxnsUpTo(transactions, scope, profile, mk, maxDay);
  return { list, ...aggregate(list) };
}

// ------------------------------------------------------------ family members
export function computeMember(transactions, memberName, mk) {
  const list = memberTxns(transactions, memberName, mk);
  return { name: memberName, count: list.length, list, ...aggregate(list) };
}

export function memberTxns(transactions, memberName, mk) {
  return transactions.filter((t) => t.member === memberName && (!mk || monthKey(t.date) === mk));
}

export function memberTotals(transactions, memberNames, mk) {
  return memberNames.map((name) => computeMember(transactions, name, mk));
}

export function untaggedTxns(transactions, memberNames, mk) {
  const known = new Set(memberNames);
  return transactions.filter((t) => !known.has(t.member) && (!mk || monthKey(t.date) === mk));
}

// --------------------------------------------------------------- credit cards
export function computeCard(transactions, scope, profile, selectedMonth, cardName, openingBalances) {
  const list = inScope(transactions, scope, profile);
  const spendAll = sum(
    list.filter((t) => t.paymentMode === 'Credit Card' && t.providerType === cardName && t.type !== 'CC Repayment')
  );
  const repaidAll = sum(list.filter((t) => t.type === 'CC Repayment' && t.account === cardName));
  const opening = Number((openingBalances || {})[cardName] || 0);
  const outstanding = opening + spendAll - repaidAll;
  const spendMonth = sum(
    list.filter(
      (t) =>
        monthKey(t.date) === selectedMonth &&
        t.paymentMode === 'Credit Card' &&
        t.providerType === cardName &&
        t.type !== 'CC Repayment'
    )
  );
  const repaidMonth = sum(
    list.filter((t) => monthKey(t.date) === selectedMonth && t.type === 'CC Repayment' && t.account === cardName)
  );
  return { opening, spendAll, repaidAll, outstanding, spendMonth, repaidMonth };
}

export function computeLoan(transactions, scope, profile, selectedMonth, loanName) {
  const list = inScope(transactions, scope, profile);
  const paidAll = sum(list.filter((t) => isLoanOutflow(t) && t.account === loanName));
  const paidMonth = sum(
    list.filter((t) => monthKey(t.date) === selectedMonth && isLoanOutflow(t) && t.account === loanName)
  );
  return { paidAll, paidMonth };
}

// ------------------------------------------------------------------- accounts
// A running balance for a bank / debit / cash account: opening, plus money
// in (income deposited here), minus money out (anything paid from here that
// isn't a credit-card purchase — those settle later via a CC repayment).
export function computeAccountBalance(transactions, account) {
  if (account.type === 'credit_card') {
    const spend = sum(
      transactions.filter(
        (t) => t.paymentMode === 'Credit Card' && t.providerType === account.name && t.type !== 'CC Repayment'
      )
    );
    const repaid = sum(transactions.filter((t) => t.type === 'CC Repayment' && t.account === account.name));
    const outstanding = (account.openingBalance || 0) + spend - repaid;
    return { balance: -outstanding, outstanding, spend, repaid, kind: 'credit_card' };
  }
  if (account.type === 'loan') {
    const paid = sum(transactions.filter((t) => isLoanOutflow(t) && t.account === account.name));
    return { balance: 0, paid, kind: 'loan' };
  }
  const credits = sum(transactions.filter((t) => isBankCredit(t) && t.providerType === account.name));
  const debits = sum(
    transactions.filter(
      (t) => t.providerType === account.name && !isBankCredit(t) && t.paymentMode !== 'Credit Card'
    )
  );
  return { balance: (account.openingBalance || 0) + credits - debits, credits, debits, kind: account.type };
}

// --------------------------------------------------------------- analytics
// Expenses only (the "spending" the dashboard breaks down). Investments,
// income and CC repayments are their own thing and excluded here.
function expenseTxns(list) {
  return list.filter((t) => t.type === 'Expense');
}

export function categoryBreakdown(list, categories) {
  const byId = Object.fromEntries((categories || []).map((c) => [c.id, c]));
  const totals = new Map();
  expenseTxns(list).forEach((t) => {
    const key = t.categoryId ?? 0;
    totals.set(key, (totals.get(key) || 0) + (Number(t.amount) || 0));
  });
  return Array.from(totals.entries())
    .map(([id, value]) => ({
      id,
      label: byId[id]?.name || 'Uncategorized',
      color: byId[id]?.color || 'var(--text-muted)',
      value,
    }))
    .sort((a, b) => b.value - a.value);
}

export function merchantBreakdown(list, limit = 8) {
  const totals = new Map();
  expenseTxns(list).forEach((t) => {
    const key = (t.merchant || '').trim() || t.name || 'Unknown';
    if (!totals.has(key)) totals.set(key, { merchant: key, value: 0, count: 0 });
    const row = totals.get(key);
    row.value += Number(t.amount) || 0;
    row.count += 1;
  });
  const rows = Array.from(totals.values()).sort((a, b) => b.value - a.value);
  return limit ? rows.slice(0, limit) : rows;
}

// Monthly income including recurring sources, so income-vs-expense reflects
// salary even in a month where no ad-hoc income was logged.
export function monthlyIncome(monthAgg, incomeSources) {
  const recurring = sum((incomeSources || []).filter((s) => s.active), (s) => Number(s.monthlyAmount) || 0);
  return recurring + (monthAgg.income || 0);
}

// The month's outflow, decomposed into the three things money actually
// went to. These sum exactly to `accrual`, which is why the dashboard can
// show them as one stacked bar:
//   accrual = Expense + Investment + Loan
//   consumption = Expense + Loan   (so Expense = consumption − loanPaid)
export function outflowSplit(monthAgg) {
  const investments = monthAgg.investments || 0;
  const loanPaid = monthAgg.loanPaid || 0;
  const expense = Math.max(0, (monthAgg.consumption || 0) - loanPaid);
  return { expense, investments, loanPaid, total: expense + investments + loanPaid };
}

export function prevMonthKey(mk) {
  if (!mk) return '';
  const [y, m] = mk.split('-').map(Number);
  const d = new Date(y, m - 2, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}
