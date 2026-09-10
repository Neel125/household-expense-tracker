// Turns a month's numbers into plain-language observations for the
// dashboard. Kept as pure functions with no React and no formatting of
// its own beyond what the sentence needs, so the thresholds are in one
// place and can be checked without rendering anything.
//
// Every builder returns null when it has nothing honest to say — a
// household with no debts should not see an EMI insight at all, rather
// than one reading "0%".
import { fmtINR, monthLabel } from './format';
import { outflowSplit } from './compute';

// Rules of thumb this file applies. They are deliberately conservative
// and stated here rather than buried in the sentences.
export const TARGETS = {
  savingsRate: 20, // % of income saved
  investmentRate: 15, // % of income into assets
  wantsShare: 35, // % of spend that is discretionary
  emiShare: 40, // % of income going to EMIs — the usual lender ceiling
  categoryJump: 25, // % change worth pointing out
  merchantShare: 20, // one merchant taking this much of spend
};

function pct(part, whole) {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

export function buildInsights(ctx) {
  const out = [
    savingsInsight(ctx),
    investmentInsight(ctx),
    emiInsight(ctx),
    categoryMoverInsight(ctx),
    wantsInsight(ctx),
    budgetInsight(ctx),
    portfolioInsight(ctx),
    interestInsight(ctx),
    merchantInsight(ctx),
  ];
  return out.filter(Boolean);
}

// --------------------------------------------------------------- builders
function savingsInsight({ income, savings }) {
  if (income <= 0) return null;
  const rate = pct(savings, income);
  const ok = rate >= TARGETS.savingsRate;
  return {
    key: 'savings',
    tone: savings < 0 ? 'bad' : ok ? 'good' : 'warning',
    title: `Saved ${rate}% of income`,
    detail:
      savings < 0
        ? `You spent ${fmtINR(-savings)} more than came in this month.`
        : ok
          ? `${fmtINR(savings)} kept back — above the ${TARGETS.savingsRate}% mark.`
          : `${fmtINR(savings)} kept back. ${TARGETS.savingsRate}% would be ${fmtINR((income * TARGETS.savingsRate) / 100)}.`,
  };
}

function investmentInsight({ income, m }) {
  const { investments } = outflowSplit(m);
  if (income <= 0 || investments <= 0) return null;
  const rate = pct(investments, income);
  return {
    key: 'investment-rate',
    tone: rate >= TARGETS.investmentRate ? 'good' : 'warning',
    title: `${rate}% of income invested`,
    detail: `${fmtINR(investments)} into assets this month.`,
  };
}

function emiInsight({ income, m, debts }) {
  if (income <= 0) return null;
  const open = (debts || []).filter((d) => (d.outstandingNow ?? d.outstanding ?? 0) > 0);
  // The lender's debt-to-income test uses the *contracted* EMI, not
  // whatever left the account this month — a voluntary prepayment is the
  // opposite of a burden, and counting it here would flag a good month as
  // a red one.
  const scheduled = open.reduce((a, d) => a + (d.emi || 0), 0);
  if (scheduled > 0) {
    const share = pct(scheduled, income);
    return {
      key: 'emi-load',
      tone: share >= TARGETS.emiShare ? 'bad' : share >= 30 ? 'warning' : 'good',
      title: `EMIs commit ${share}% of income`,
      detail:
        `${fmtINR(scheduled)} a month across ${open.length} loan${open.length === 1 ? '' : 's'}.` +
        (share >= TARGETS.emiShare ? ` Lenders treat ${TARGETS.emiShare}% as the ceiling.` : ''),
    };
  }
  // No EMI amounts on record — report what actually went out, without the
  // ceiling language that only makes sense for a recurring commitment.
  const actual = outflowSplit(m).loanPaid;
  if (actual <= 0) return null;
  return {
    key: 'emi-load',
    tone: 'info',
    title: `${pct(actual, income)}% of income went to loans`,
    detail: `${fmtINR(actual)} of loan payments this month.`,
  };
}

// The single biggest category change against last month — usually the
// most actionable thing on the page, because it is the one number the
// household can still do something about.
function categoryMoverInsight({ catData, prevCatData, prevMk, comparisonLabel }) {
  if (!prevMk || !prevCatData?.length) return null;
  const before = new Map(prevCatData.map((c) => [c.label, c.value]));
  let best = null;
  for (const c of catData) {
    const was = before.get(c.label) || 0;
    if (was <= 0 || c.value <= 0) continue;
    const change = pct(c.value - was, was);
    if (Math.abs(change) < TARGETS.categoryJump) continue;
    if (!best || Math.abs(c.value - was) > Math.abs(best.diff)) {
      best = { label: c.label, diff: c.value - was, change, color: c.color };
    }
  }
  if (!best) return null;
  const up = best.diff > 0;
  return {
    key: 'category-mover',
    tone: up ? 'warning' : 'good',
    title: `${best.label} ${up ? 'up' : 'down'} ${Math.abs(best.change)}%`,
    detail: `${up ? '+' : '−'}${fmtINR(Math.abs(best.diff))} against ${comparisonLabel || monthLabel(prevMk)}.`,
  };
}

function wantsInsight({ m }) {
  const need = m.necessity?.Need || 0;
  const want = m.necessity?.Want || 0;
  if (need + want <= 0) return null;
  const share = pct(want, need + want);
  return {
    key: 'wants',
    tone: share > TARGETS.wantsShare ? 'warning' : 'good',
    title: `${share}% of spending was a want`,
    detail: `${fmtINR(want)} discretionary against ${fmtINR(need)} of needs.`,
  };
}

function budgetInsight({ m, budget }) {
  const cap = budget?.monthlyBudget || 0;
  if (cap <= 0) return null;
  // Day-to-day expenses only. The budget is an envelope for spending —
  // money put into an SIP or against a loan's principal is not overspend.
  const spent = outflowSplit(m).expense;
  const used = pct(spent, cap);
  const over = spent > cap;
  return {
    key: 'budget',
    tone: over ? 'bad' : used > 85 ? 'warning' : 'good',
    title: over ? `${used}% of budget — over` : `${used}% of budget used`,
    detail: over
      ? `${fmtINR(spent - cap)} above the ${fmtINR(cap)} envelope.`
      : `${fmtINR(cap - spent)} of ${fmtINR(cap)} still unspent.`,
  };
}

function portfolioInsight({ investments }) {
  const rows = investments || [];
  if (!rows.length) return null;
  const invested = rows.reduce((a, i) => a + (i.totalInvested ?? i.amountInvested ?? 0), 0);
  const value = rows.reduce((a, i) => a + (i.effectiveValue ?? i.currentValue ?? 0), 0);
  if (invested <= 0) return null;
  const gain = value - invested;
  return {
    key: 'portfolio',
    tone: gain >= 0 ? 'good' : 'bad',
    title: `Portfolio ${gain >= 0 ? 'up' : 'down'} ${Math.abs(pct(gain, invested))}%`,
    detail: `${fmtINR(value)} against ${fmtINR(invested)} put in.`,
  };
}

// What the loans have actually cost. Only says anything once EMIs are
// linked to a debt, because that is what makes the split knowable.
function interestInsight({ debts }) {
  const rows = debts || [];
  const interest = rows.reduce((a, d) => a + (d.interestPaid || 0), 0);
  const principal = rows.reduce((a, d) => a + (d.principalRepaid || 0), 0);
  if (interest <= 0) return null;
  return {
    key: 'interest',
    tone: 'info',
    title: `${pct(interest, interest + principal)}% of EMIs went to interest`,
    detail: `${fmtINR(interest)} interest against ${fmtINR(principal)} of principal, on the EMIs you've logged.`,
  };
}

function merchantInsight({ merchants, catData }) {
  const total = (catData || []).reduce((a, c) => a + c.value, 0);
  const top = (merchants || [])[0];
  if (!top || total <= 0) return null;
  const share = pct(top.value, total);
  if (share < TARGETS.merchantShare) return null;
  return {
    key: 'merchant',
    tone: 'info',
    title: `${share}% of spend went to ${top.merchant}`,
    detail: `${fmtINR(top.value)} over ${top.count} transaction${top.count === 1 ? '' : 's'}.`,
  };
}
