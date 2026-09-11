import { useEffect, useMemo, useState } from 'react';
import BarChart from '../components/charts/BarChart';
import DonutChart from '../components/charts/DonutChart';
import LineChart from '../components/charts/LineChart';
import {
  Card,
  EmptyState,
  MonthSelect,
  PageHeader,
  Pill,
  ProgressBar,
  SegmentedControl,
  StackedBar,
  StatCard,
} from '../components/ui';
import { fmtINR, monthLabel } from '../lib/format';
import {
  availableMonths,
  categoryBreakdown,
  computeAccountBalance,
  computeMonth,
  computeMonthUpTo,
  inScope,
  merchantBreakdown,
  monthTxns,
  monthTxnsUpTo,
  monthlyIncome,
  outflowSplit,
  prevMonthKey,
  thisMonthKey,
} from '../lib/compute';
import { buildInsights } from '../lib/insights';
import { INV_COLORS, INV_META, DEBT_META } from '../lib/portfolioMeta';
import { useData } from '../context/DataContext';

// Colours for the outflow split. Consistent across the stacked bar, the
// trend chart and the donut so the same idea is always the same hue.
const FLOW = {
  expense: 'var(--series-2)',
  investment: 'var(--series-3)',
  emi: 'var(--series-4)',
  unspent: 'var(--accent)',
};

function Delta({ now, prev, invert = false }) {
  if (!prev && !now) return <span className="delta">—</span>;
  const diff = now - prev;
  const pct = prev ? Math.round((diff / Math.abs(prev)) * 100) : null;
  const good = invert ? diff < 0 : diff > 0;
  const cls = diff === 0 ? '' : good ? ' up-good' : ' up-bad';
  const arrow = diff === 0 ? '→' : diff > 0 ? '▲' : '▼';
  return (
    <span className={'delta' + cls}>
      {arrow} {pct === null ? fmtINR(Math.abs(diff)) : `${Math.abs(pct)}%`}
    </span>
  );
}

function SectionHead({ title, hint }) {
  return (
    <div className="section-head">
      <div className="card-title">{title}</div>
      {hint && <span className="note">{hint}</span>}
    </div>
  );
}

// The insight strip. Each tile is one observation from lib/insights —
// which returns only the ones that actually apply, so an empty tile is
// never rendered.
function InsightStrip({ insights }) {
  if (!insights.length) return null;
  return (
    <div className="grid insight-row">
      {insights.map((i) => (
        <div className={'insight tone-' + i.tone} key={i.key}>
          <div className="insight-title">{i.title}</div>
          <div className="insight-detail">{i.detail}</div>
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const {
    transactions,
    categories,
    accounts,
    incomeSources,
    investments,
    debts,
    budget,
    rewards,
    scope,
    setScope,
    profile,
  } = useData();
  const months = useMemo(() => availableMonths(transactions), [transactions]);
  const [selectedMonth, setSelectedMonth] = useState('');

  useEffect(() => {
    if (!selectedMonth || !months.includes(selectedMonth)) {
      setSelectedMonth(months.length ? months[months.length - 1] : '');
    }
  }, [months]); // eslint-disable-line react-hooks/exhaustive-deps

  const mk = selectedMonth || months[months.length - 1] || '';
  const prevMk = prevMonthKey(mk);
  const m = useMemo(() => computeMonth(transactions, scope, profile, mk), [transactions, scope, profile, mk]);

  // A month still in progress is compared against the same day-range of
  // the month before. Without this, on the 9th every category reads as a
  // collapse and every insight built on the comparison is misleading.
  const today = new Date();
  const partialDay = mk === thisMonthKey(today) ? today.getDate() : 0;
  const prev = useMemo(
    () => computeMonthUpTo(transactions, scope, profile, prevMk, partialDay),
    [transactions, scope, profile, prevMk, partialDay]
  );
  const comparisonLabel = partialDay
    ? `1–${partialDay} ${monthLabel(prevMk).split(' ')[0]}`
    : monthLabel(prevMk);

  const income = monthlyIncome(m, incomeSources);
  const prevIncome = monthlyIncome(prev, incomeSources);
  const savings = income - m.consumption;
  const savingsRate = income > 0 ? Math.round((savings / income) * 100) : 0;

  // accrual = expense + investments + EMIs, so these three plus whatever
  // is left of income account for the month exactly.
  const split = outflowSplit(m);
  const prevSplit = outflowSplit(prev);
  const unspent = Math.max(0, income - split.total);

  const scopedTxns = useMemo(() => inScope(transactions, scope, profile), [transactions, scope, profile]);
  const creditCards = accounts.filter((a) => a.type === 'credit_card');
  const ccOutstanding = creditCards.reduce(
    (acc, c) => acc + (computeAccountBalance(scopedTxns, c).outstanding || 0),
    0
  );
  const liquid = useMemo(
    () =>
      accounts
        .filter((a) => !a.archived && ['bank', 'cash', 'debit_card'].includes(a.type))
        .reduce((acc, a) => acc + (computeAccountBalance(scopedTxns, a).balance || 0), 0),
    [accounts, scopedTxns]
  );

  // ------------------------------------------------------------- portfolio
  const portfolioValue = investments.reduce((a, i) => a + (i.effectiveValue || 0), 0);
  const portfolioInvested = investments.reduce((a, i) => a + (i.totalInvested || 0), 0);
  const portfolioGain = portfolioValue - portfolioInvested;
  const allocation = useMemo(() => {
    const buckets = new Map();
    for (const inv of investments) {
      const v = Number(inv.effectiveValue) || 0;
      if (v <= 0) continue;
      buckets.set(inv.kind, (buckets.get(inv.kind) || 0) + v);
    }
    return Array.from(buckets, ([kind, value]) => ({
      label: INV_META[kind]?.label || kind,
      value,
      color: INV_COLORS[kind] || '#94a3b8',
    })).sort((a, b) => b.value - a.value);
  }, [investments]);

  // ------------------------------------------------------------------ debt
  const openDebts = debts.filter((d) => (d.outstandingNow || 0) > 0);
  const debtOutstanding = debts.reduce((a, d) => a + (d.outstandingNow || 0), 0);
  const debtPrincipalPaid = debts.reduce((a, d) => a + (d.principalRepaid || 0), 0);
  const debtInterestPaid = debts.reduce((a, d) => a + (d.interestPaid || 0), 0);

  const netWorth = liquid + portfolioValue - debtOutstanding - ccOutstanding;

  // -------------------------------------------------------------- spending
  const monthList = monthTxns(transactions, scope, profile, mk);
  const catData = useMemo(() => categoryBreakdown(monthList, categories), [monthList, categories]);
  const prevList = useMemo(
    () => monthTxnsUpTo(transactions, scope, profile, prevMk, partialDay),
    [transactions, scope, profile, prevMk, partialDay]
  );
  const prevCatData = useMemo(() => categoryBreakdown(prevList, categories), [prevList, categories]);
  const topCategories = catData.slice(0, 6);
  const merchants = useMemo(() => merchantBreakdown(monthList, 8), [monthList]);
  const totalExpense = catData.reduce((a, c) => a + c.value, 0);

  const necessity = [
    { label: 'Need', value: m.necessity?.Need || 0, color: 'var(--series-1)' },
    { label: 'Want', value: m.necessity?.Want || 0, color: 'var(--series-2)' },
  ].filter((n) => n.value > 0);
  const necessityTotal = necessity.reduce((a, n) => a + n.value, 0);
  const wantShare =
    necessityTotal > 0 ? Math.round(((m.necessity?.Want || 0) / necessityTotal) * 100) : 0;

  // ----------------------------------------------------------------- trends
  const trendMonths = months.slice(-6);
  const trend = useMemo(
    () =>
      trendMonths.map((tm) => {
        const agg = computeMonth(transactions, scope, profile, tm);
        return { mk: tm, agg, income: monthlyIncome(agg, incomeSources), split: outflowSplit(agg) };
      }),
    [transactions, scope, profile, incomeSources, trendMonths.join(',')] // eslint-disable-line react-hooks/exhaustive-deps
  );

  // Cumulative curves over up to a year. Both are running totals, so the
  // shape — not the month-to-month noise — is the point: is the household
  // putting money away faster than it used to?
  const longMonths = months.slice(-12);
  const cumulative = useMemo(() => {
    let invested = 0;
    let saved = 0;
    return longMonths.map((tm) => {
      const agg = computeMonth(transactions, scope, profile, tm);
      invested += agg.investments || 0;
      saved += monthlyIncome(agg, incomeSources) - (agg.consumption || 0);
      return { mk: tm, invested, saved };
    });
  }, [transactions, scope, profile, incomeSources, longMonths.join(',')]); // eslint-disable-line react-hooks/exhaustive-deps

  const insights = useMemo(
    () =>
      buildInsights({
        m,
        prev,
        income,
        prevIncome,
        savings,
        catData,
        prevCatData,
        prevMk,
        comparisonLabel,
        budget,
        investments,
        debts,
        merchants,
        rewards,
      }).slice(0, 6),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [m, prev, income, prevIncome, savings, catData, prevCatData, prevMk, comparisonLabel, budget, investments, debts, merchants, rewards]
  );

  if (!months.length) {
    return (
      <section>
        <PageHeader title="Dashboard" subtitle="No data yet" />
        <Card pad>
          <EmptyState>Add your first transaction to see your dashboard come to life.</EmptyState>
        </Card>
      </section>
    );
  }

  const investRatio = split.expense > 0 ? split.investments / split.expense : 0;

  return (
    <section>
      <PageHeader
        title="Dashboard"
        subtitle={`${monthLabel(mk)} · ${scope === 'mine' ? profile || 'you' : 'household'} · ${m.list.length} transactions`}
      >
        <MonthSelect months={months} value={mk} onChange={setSelectedMonth} />
        <SegmentedControl
          value={scope}
          onChange={setScope}
          options={[
            { value: 'household', label: 'Household' },
            { value: 'mine', label: 'Just me' },
          ]}
        />
      </PageHeader>

      <div className="grid kpi-row">
        <StatCard
          label="Net worth"
          value={netWorth}
          tone={netWorth >= 0 ? 'good' : 'warning'}
          foot="cash + investments − debts"
        />
        <StatCard label="Income" value={income} foot="salary + other" />
        <StatCard label="Spent" value={split.expense} foot="day-to-day expenses" />
        <StatCard
          label="Invested"
          value={split.investments}
          foot={income > 0 ? `${Math.round((split.investments / income) * 100)}% of income` : 'this month'}
        />
        <StatCard
          label="Savings rate"
          value={`${savingsRate}%`}
          raw
          tone={savingsRate >= 20 ? 'good' : 'warning'}
          foot={`saved ${fmtINR(savings)}`}
        />
      </div>

      <InsightStrip insights={insights} />

      {/* ------------------------------------------- expense vs investment */}
      <SectionHead title="Where the money went" hint={`${monthLabel(mk)} · every rupee that left, and what it bought`} />
      <div className="grid two-col">
        <Card title="Outflow split" hint="expenses vs assets vs debt">
          <div className="card-pad">
            <StackedBar
              segments={[
                { label: 'Expenses', value: split.expense, color: FLOW.expense, hint: 'living costs' },
                { label: 'Investments', value: split.investments, color: FLOW.investment, hint: 'buys you an asset' },
                {
                  label: 'Loan payments',
                  value: split.loanPaid,
                  color: FLOW.emi,
                  hint: 'EMIs and prepayments — part interest, part principal',
                },
                { label: 'Left over', value: unspent, color: FLOW.unspent, hint: 'income not yet allocated' },
              ]}
            />
            <div className="takeaway">
              {split.investments > 0 ? (
                <>
                  For every <strong>₹100</strong> spent on living, <strong>{fmtINR(Math.round(investRatio * 100))}</strong>{' '}
                  went into building assets.
                </>
              ) : (
                <>Nothing went into investments this month — all outflow was spending or debt.</>
              )}
            </div>
          </div>
        </Card>

        <Card title="Expense vs investment" hint="last 6 months">
          <div className="card-pad">
            <BarChart
              categories={trend.map((t) => monthLabel(t.mk))}
              series={[
                { name: 'Expenses', color: FLOW.expense, values: trend.map((t) => t.split.expense) },
                { name: 'Investments', color: FLOW.investment, values: trend.map((t) => t.split.investments) },
                { name: 'Loan payments', color: FLOW.emi, values: trend.map((t) => t.split.loanPaid) },
              ]}
            />
          </div>
        </Card>
      </div>

      {/* --------------------------------------------------- building wealth */}
      {(investments.length > 0 || cumulative.length > 1) && (
        <>
          <SectionHead title="Building wealth" hint="what the money has turned into" />
          <div className="grid two-col">
            {investments.length > 0 ? (
              <Card title="Portfolio" hint={`${investments.length} holding${investments.length === 1 ? '' : 's'}`}>
                <div className="card-pad">
                  <div className="mini-stats mini-stats-3">
                    <div>
                      <div className="note">Value</div>
                      <div className="num mom-val">{fmtINR(portfolioValue)}</div>
                    </div>
                    <div>
                      <div className="note">Invested</div>
                      <div className="num mom-val">{fmtINR(portfolioInvested)}</div>
                    </div>
                    <div>
                      <div className="note">Gain</div>
                      <div className={'num mom-val ' + (portfolioGain >= 0 ? 'up-good' : 'up-bad')}>
                        {portfolioGain >= 0 ? '+' : '−'}
                        {fmtINR(Math.abs(portfolioGain))}
                      </div>
                    </div>
                  </div>
                  {allocation.length ? (
                    <DonutChart data={allocation} />
                  ) : (
                    <EmptyState>No holding has a value yet.</EmptyState>
                  )}
                </div>
              </Card>
            ) : (
              <Card title="Portfolio" hint="nothing tracked yet">
                <div className="card-pad">
                  <EmptyState>
                    Add your FDs, RDs, SIPs and stocks on the Portfolio page, then link your
                    Investment transactions to them — the invested total keeps itself up to date.
                  </EmptyState>
                </div>
              </Card>
            )}

            <Card title="Saved and invested, cumulative" hint={`running total, last ${cumulative.length} month${cumulative.length === 1 ? '' : 's'}`}>
              <div className="card-pad">
                {cumulative.length > 1 ? (
                  <>
                    <LineChart
                      categories={cumulative.map((c) => monthLabel(c.mk))}
                      series={[
                        { name: 'Net saved', color: 'var(--status-good)', values: cumulative.map((c) => c.saved), area: true },
                        { name: 'Invested', color: FLOW.investment, values: cumulative.map((c) => c.invested), area: true },
                      ]}
                    />
                    <div className="takeaway">
                      Over {cumulative.length} months you kept back{' '}
                      <strong>{fmtINR(cumulative[cumulative.length - 1].saved)}</strong> and moved{' '}
                      <strong>{fmtINR(cumulative[cumulative.length - 1].invested)}</strong> of it into
                      investments.
                    </div>
                  </>
                ) : (
                  <EmptyState>A second month of data will start this curve.</EmptyState>
                )}
              </div>
            </Card>
          </div>
        </>
      )}

      {/* ------------------------------------------------------------- debt */}
      {(openDebts.length > 0 || ccOutstanding > 0) && (
        <>
          <SectionHead title="What you owe" hint="loans, EMIs and cards" />
          <div className="grid two-col">
            <Card title="Debt outstanding" hint={`${openDebts.length} open loan${openDebts.length === 1 ? '' : 's'}`}>
              <div className="card-pad">
                <div className="mini-stats mini-stats-3">
                  <div>
                    <div className="note">Loans</div>
                    <div className="num mom-val">{fmtINR(debtOutstanding)}</div>
                  </div>
                  <div>
                    <div className="note">{ccOutstanding < 0 ? 'Cards (in credit)' : 'Cards'}</div>
                    <div className="num mom-val">{fmtINR(Math.abs(ccOutstanding))}</div>
                  </div>
                  <div>
                    <div className="note">EMIs this month</div>
                    <div className="num mom-val">{fmtINR(split.loanPaid)}</div>
                  </div>
                </div>
                {openDebts.length ? (
                  <div className="rank-list" style={{ marginTop: 14 }}>
                    {openDebts.map((d) => (
                      <div key={d.id} className="debt-line">
                        <div className="debt-line-head">
                          <span>
                            {DEBT_META[d.kind]?.icon || '📦'} {d.name}
                          </span>
                          <span className="num">{fmtINR(d.outstandingNow)}</span>
                        </div>
                        <ProgressBar pct={d.payoffPct} />
                        <div className="note">
                          {Math.round(d.payoffPct)}% paid off
                          {d.annualRatePct > 0 && <> · {d.annualRatePct}% p.a.</>}
                          {d.emi > 0 && <> · EMI {fmtINR(d.emi)}</>}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState>No loans tracked — the balance above is card spend awaiting repayment.</EmptyState>
                )}
              </div>
            </Card>

            <Card title="What your EMIs bought" hint="principal vs interest, all logged EMIs">
              <div className="card-pad">
                {debtPrincipalPaid + debtInterestPaid > 0 ? (
                  <>
                    <StackedBar
                      segments={[
                        {
                          label: 'Principal',
                          value: debtPrincipalPaid,
                          color: 'var(--status-good)',
                          hint: 'actually reduced the loan',
                        },
                        {
                          label: 'Interest',
                          value: debtInterestPaid,
                          color: 'var(--status-critical)',
                          hint: 'the cost of borrowing',
                        },
                      ]}
                    />
                    <div className="takeaway">
                      Of the {fmtINR(debtPrincipalPaid + debtInterestPaid)} of EMIs you've logged,{' '}
                      <strong>{fmtINR(debtInterestPaid)}</strong> was interest. Paying early is what
                      shrinks that share.
                    </div>
                  </>
                ) : (
                  <EmptyState>
                    Link a Loan EMI or Loan partial payment to a debt on the Add Transaction form.
                  </EmptyState>
                )}
              </div>
            </Card>
          </div>
        </>
      )}

      {/* --------------------------------------------------------- spending */}
      <SectionHead
        title="Spending detail"
        hint={partialDay ? `${monthLabel(mk)} so far · changes vs ${comparisonLabel}` : monthLabel(mk)}
      />
      <div className="grid two-col">
        <Card title="Category breakdown" hint="expenses this month">
          <div className="card-pad">
            {catData.length ? (
              <DonutChart data={catData.map((c) => ({ label: c.label, value: c.value, color: c.color }))} />
            ) : (
              <EmptyState>No expenses categorised this month.</EmptyState>
            )}
          </div>
        </Card>
        <Card title="Highest spending categories" hint="this month">
          <div className="card-pad">
            {topCategories.length ? (
              <div className="rank-list">
                {topCategories.map((c) => {
                  const pct = totalExpense > 0 ? Math.round((c.value / totalExpense) * 100) : 0;
                  const was = prevCatData.find((p) => p.label === c.label)?.value || 0;
                  return (
                    <div className="rank-row" key={c.id}>
                      <div className="rank-label">
                        <span className="sw" style={{ background: c.color }} /> {c.label}
                      </div>
                      <div className="rank-bar">
                        <span style={{ width: pct + '%', background: c.color }} />
                      </div>
                      <div className="rank-val num">
                        {fmtINR(c.value)} <span className="note">{pct}%</span>
                        {was > 0 && (
                          <>
                            {' '}
                            <Delta now={c.value} prev={was} invert />
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState>Nothing spent this month.</EmptyState>
            )}
          </div>
        </Card>
      </div>

      <div className="grid two-col" style={{ marginTop: 16 }}>
        <Card title="Needs vs wants" hint="day-to-day spending only">
          <div className="card-pad">
            {necessity.length ? (
              <>
                <DonutChart data={necessity} />
                <div className="takeaway">
                  <strong>{wantShare}%</strong> of what you spent on living was discretionary —
                  the part you could still choose differently next month.
                </div>
              </>
            ) : (
              <EmptyState>Tag transactions Need / Want to see this split.</EmptyState>
            )}
          </div>
        </Card>
        <Card title="Income vs expenses" hint="last 6 months">
          <div className="card-pad">
            <BarChart
              categories={trend.map((t) => monthLabel(t.mk))}
              series={[
                { name: 'Income', color: 'var(--status-good)', values: trend.map((t) => t.income) },
                { name: 'Outflow', color: 'var(--series-1)', values: trend.map((t) => t.split.total) },
              ]}
            />
          </div>
        </Card>
      </div>

      <Card
        title="Month over month"
        hint={prevMk ? `vs ${comparisonLabel}` : 'no prior month'}
        className="mom-card"
        style={{ marginTop: 16 }}
      >
        <div className="card-pad">
          <div className="mom-grid">
            <div className="mom-item">
              <div className="note">Income</div>
              <div className="num mom-val">{fmtINR(income)}</div>
              <Delta now={income} prev={prevIncome} />
            </div>
            <div className="mom-item">
              <div className="note">Expenses</div>
              <div className="num mom-val">{fmtINR(split.expense)}</div>
              <Delta now={split.expense} prev={prevSplit.expense} invert />
            </div>
            <div className="mom-item">
              <div className="note">Invested</div>
              <div className="num mom-val">{fmtINR(split.investments)}</div>
              <Delta now={split.investments} prev={prevSplit.investments} />
            </div>
            <div className="mom-item">
              <div className="note">Savings</div>
              <div className="num mom-val">{fmtINR(savings)}</div>
              <Delta now={savings} prev={prevIncome - prev.consumption} />
            </div>
            <div className="mom-item">
              <div className="note">Cash out of bank</div>
              <div className="num mom-val">{fmtINR(m.cashOutflow)}</div>
              <Delta now={m.cashOutflow} prev={prev.cashOutflow} invert />
            </div>
          </div>
        </div>
      </Card>

      <Card title="Merchant-wise analysis" hint="top merchants this month" style={{ marginTop: 16 }}>
        <div className="card-pad">
          <div className="table-wrap">
            <table>
              {merchants.length ? (
                <>
                  <thead>
                    <tr>
                      <th>Merchant</th>
                      <th className="num">Visits</th>
                      <th className="num">Spent</th>
                      <th className="num col-2">Avg</th>
                      <th className="num col-2">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {merchants.map((mrow) => (
                      <tr key={mrow.merchant}>
                        <td>{mrow.merchant}</td>
                        <td className="num">{mrow.count}</td>
                        <td className="num">{fmtINR(mrow.value)}</td>
                        <td className="num col-2">{fmtINR(mrow.value / mrow.count)}</td>
                        <td className="num col-2">
                          {totalExpense > 0 ? Math.round((mrow.value / totalExpense) * 100) : 0}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </>
              ) : (
                <tbody>
                  <tr>
                    <td className="empty">No merchant spending logged this month.</td>
                  </tr>
                </tbody>
              )}
            </table>
          </div>
        </div>
      </Card>
    </section>
  );
}
