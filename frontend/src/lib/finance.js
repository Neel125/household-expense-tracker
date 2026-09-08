// Pure functions used by the Tools calculators. No React, no I/O.
// Kept small and unit-testable — each takes primitives, returns numbers /
// plain arrays.

// ------------------------------------------------------------------ EMI
export function emiFor(principal, annualRatePct, months) {
  const r = annualRatePct / 1200;
  if (r === 0) return principal / months;
  const f = Math.pow(1 + r, months);
  return (principal * r * f) / (f - 1);
}

// Absolute upper bound on the loop — the schedule can now extend past the
// original tenure when a rate hike keeps the EMI flat, so we guard against
// runaway iterations with a very generous ceiling (60 years).
const MAX_SCHEDULE_MONTHS = 720;

/**
 * Amortize a loan month by month with any number of dated events.
 *
 * Behaviour of each event type:
 *   - rateChanges: change the applied interest rate for the rest of the
 *     loan. The EMI is NOT recomputed — the borrower keeps paying the
 *     current EMI, which means the tenure shortens if the rate drops and
 *     lengthens if it rises.
 *   - prepayments: reduce the outstanding principal after that month's
 *     EMI. EMI unchanged, tenure naturally shortens.
 *   - stepUps: multiply the current EMI by (1 + pct/100). This is the
 *     ONLY thing that changes the EMI amount.
 *
 * opts: {
 *   startYear, startMonth,
 *   rateChanges: [{ month, newAnnualRatePct }],
 *   stepUps:     [{ month, pct }],
 *   prepayments: [{ month, amount }],
 * }
 *
 * Returns { schedule, totalInterest, totalPaid, totalPrepaid, monthsActual,
 *   startingEmi, finalEmi, closed }. `closed` is false when the EMI can't
 * cover interest at some point (loan would never end) — the schedule stops
 * at the last productive row and the UI can warn.
 */
export function amortize(principal, annualRatePct, months, opts = {}) {
  const now = new Date();
  const {
    startYear = now.getFullYear(),
    startMonth = now.getMonth() + 1,
    rateChanges = [],
    stepUps = [],
    prepayments = [],
  } = opts;

  // Index the events by month for O(1) lookup inside the loop.
  const byMonth = (arr) => {
    const map = new Map();
    for (const ev of arr) {
      const m = Number(ev.month);
      if (!m || m < 1) continue;
      if (!map.has(m)) map.set(m, []);
      map.get(m).push(ev);
    }
    return map;
  };
  const rateAt = byMonth(rateChanges);
  const stepAt = byMonth(stepUps);
  const prepayAt = byMonth(prepayments);

  let balance = principal;
  let rate = annualRatePct;
  let emi = emiFor(balance, rate, months);
  const startingEmi = emi;
  let totalInterest = 0;
  let totalPaid = 0;
  let totalPrepaid = 0;
  let closed = false;
  const schedule = [];

  for (let m = 1; m <= MAX_SCHEDULE_MONTHS && balance > 0.5; m++) {
    // 1. Rate changes effective this month — the rate switches but the EMI
    //    stays the same, so more/less of it goes to principal.
    if (rateAt.has(m)) {
      for (const rc of rateAt.get(m)) {
        const newRate = Number(rc.newAnnualRatePct);
        if (Number.isFinite(newRate)) rate = newRate;
      }
    }
    // 2. EMI step-ups effective this month — the only thing that moves EMI.
    if (stepAt.has(m)) {
      for (const s of stepAt.get(m)) {
        const p = Number(s.pct) || 0;
        if (p) emi = emi * (1 + p / 100);
      }
    }

    const monthlyRate = rate / 1200;
    const interest = balance * monthlyRate;

    // Guard: if the EMI can't even cover this month's interest, the loan
    // would never close. Record what we have and stop.
    if (emi <= interest + 0.01) {
      break;
    }

    let principalPart = emi - interest;
    let paidEmi = emi;

    // Cap the last month so we don't over-pay.
    if (principalPart > balance) {
      principalPart = balance;
      paidEmi = principalPart + interest;
    }
    balance -= principalPart;
    totalInterest += interest;
    totalPaid += paidEmi;

    // 3. Prepayments applied after this month's EMI.
    let prepaid = 0;
    if (prepayAt.has(m) && balance > 0.5) {
      for (const pp of prepayAt.get(m)) {
        const amt = Number(pp.amount) || 0;
        const take = Math.min(amt, balance);
        prepaid += take;
        balance -= take;
        totalPaid += take;
        totalPrepaid += take;
        if (balance <= 0.5) break;
      }
    }

    const cal = calendarAt(startYear, startMonth, m);
    schedule.push({
      month: m,
      calendarYear: cal.year,
      calendarMonth: cal.month,
      emi: paidEmi,        // actually paid this month (may be smaller on the final month)
      emiLevel: emi,       // the scheduled EMI level in force this month
      interest,
      principal: principalPart,
      prepaid,
      balance: Math.max(0, balance),
      annualRate: rate,
    });

    if (balance <= 0.5) {
      closed = true;
      break;
    }
  }

  return {
    schedule,
    totalInterest,
    totalPaid,
    totalPrepaid,
    monthsActual: schedule.length,
    startingEmi,
    finalEmi: emi,       // the scheduled EMI level at the end (unaffected by the last-month cap)
    endingBalance: Math.max(0, balance),
    closed,
  };
}

// Given the loan's start calendar month and a 1-indexed offset, return the
// calendar year/month of that offset (month is 1-12).
function calendarAt(startYear, startMonth, offset) {
  const zeroIdx = (startMonth - 1) + (offset - 1); // months since Jan of startYear
  return {
    year: startYear + Math.floor(zeroIdx / 12),
    month: (zeroIdx % 12) + 1,
  };
}

// Roll monthly rows up into per-calendar-year summaries so the UI has
// something manageable to render for long tenures.
export function toYearlySummary(schedule) {
  const groups = new Map();
  for (const row of schedule) {
    const key = row.calendarYear;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  const years = [];
  for (const [year, rows] of groups) {
    const first = rows[0];
    const last = rows[rows.length - 1];
    years.push({
      year,
      fromMonth: first.calendarMonth,
      toMonth: last.calendarMonth,
      months: rows.length,
      totalEmi: rows.reduce((a, r) => a + r.emi, 0),
      totalInterest: rows.reduce((a, r) => a + r.interest, 0),
      totalPrincipal: rows.reduce((a, r) => a + r.principal + r.prepaid, 0),
      totalPrepaid: rows.reduce((a, r) => a + r.prepaid, 0),
      endingBalance: last.balance,
    });
  }
  return years;
}

// ---------------------------------------------------------------- FD / RD
// Fixed deposit: single deposit compounded n times/year for `years`.
export function fdMaturity(principal, annualRatePct, years, compoundsPerYear = 4) {
  const n = compoundsPerYear;
  const t = years;
  const r = annualRatePct / 100;
  const M = principal * Math.pow(1 + r / n, n * t);
  return { maturity: M, interest: M - principal, principal };
}

// Recurring deposit: `monthly` deposited every month for `months`.
// We compound month by month using effective monthly rate derived from the
// compounding frequency, which matches how Indian banks quote RD returns.
export function rdMaturity(monthly, annualRatePct, months, compoundsPerYear = 4) {
  const n = compoundsPerYear;
  const r = annualRatePct / 100;
  // Effective monthly rate for compounding n times/year:
  const monthlyRate = Math.pow(1 + r / n, n / 12) - 1;
  let balance = 0;
  for (let m = 1; m <= months; m++) {
    balance = (balance + monthly) * (1 + monthlyRate);
  }
  const invested = monthly * months;
  return { maturity: balance, invested, interest: balance - invested };
}

// ------------------------------------------------------------------- SIP
// FV of a monthly SIP with optional annual step-up.
export function sipFutureValue(monthly, annualReturnPct, years, stepUpPct = 0) {
  const i = annualReturnPct / 1200;
  const months = years * 12;
  let fv = 0;
  let contrib = monthly;
  let invested = 0;
  for (let m = 1; m <= months; m++) {
    if (m > 1 && (m - 1) % 12 === 0 && stepUpPct > 0) {
      contrib = contrib * (1 + stepUpPct / 100);
    }
    fv = (fv + contrib) * (1 + i);
    invested += contrib;
  }
  return { futureValue: fv, invested, gains: fv - invested };
}

// -------------------------------------------------------- Indian income tax
// Slabs applied progressively: pay `rate` on the amount in each bracket.
function slabTax(taxable, slabs) {
  let tax = 0;
  let last = 0;
  for (const [upto, rate] of slabs) {
    if (taxable <= last) break;
    const top = upto === Infinity ? taxable : Math.min(upto, taxable);
    tax += Math.max(0, top - last) * rate;
    last = upto;
  }
  return tax;
}

// New regime FY 2025-26 (AY 2026-27), individuals.
const NEW_SLABS = [
  [400000, 0],
  [800000, 0.05],
  [1200000, 0.1],
  [1600000, 0.15],
  [2000000, 0.2],
  [2400000, 0.25],
  [Infinity, 0.3],
];

// Old regime, individuals below 60.
const OLD_SLABS = [
  [250000, 0],
  [500000, 0.05],
  [1000000, 0.2],
  [Infinity, 0.3],
];

const CESS = 0.04;
const NEW_STD_DEDUCTION = 75000;
const OLD_STD_DEDUCTION = 50000;

function rebate87A(taxable, regime) {
  // Section 87A: full rebate up to ~12L in the new regime, up to 5L in old.
  if (regime === 'new' && taxable <= 1200000) return Infinity; // rebated to zero
  if (regime === 'old' && taxable <= 500000) return 12500;
  return 0;
}

export function computeIndiaTax(gross, deductions, regime = 'new', salaried = true) {
  const stdDeduction = salaried ? (regime === 'new' ? NEW_STD_DEDUCTION : OLD_STD_DEDUCTION) : 0;
  // In the new regime, section-wise deductions (80C etc.) don't apply.
  const applicableDeductions = regime === 'new' ? 0 : deductions;
  const taxable = Math.max(0, gross - stdDeduction - applicableDeductions);
  const slabs = regime === 'new' ? NEW_SLABS : OLD_SLABS;
  const base = slabTax(taxable, slabs);
  const rebate = rebate87A(taxable, regime);
  const afterRebate = rebate === Infinity ? 0 : Math.max(0, base - rebate);
  const cess = afterRebate * CESS;
  const total = afterRebate + cess;
  return {
    regime,
    taxable,
    stdDeduction,
    deductions: applicableDeductions,
    baseTax: base,
    rebate: rebate === Infinity ? base : rebate,
    cess,
    totalTax: total,
    takeHome: gross - total,
  };
}
