import { useEffect, useMemo, useState } from 'react';
import DonutChart from '../components/charts/DonutChart';
import BarChart from '../components/charts/BarChart';
import { Card, EmptyState, MonthSelect, PageHeader, SegmentedControl, StatCard } from '../components/ui';
import { fmtINR, monthLabel } from '../lib/format';
import {
  availableMonths,
  categoryBreakdown,
  computeMonth,
  inScope,
  merchantBreakdown,
  monthTxns,
  monthlyIncome,
  prevMonthKey,
} from '../lib/compute';
import { computeAccountBalance } from '../lib/compute';
import { useData } from '../context/DataContext';

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

export default function DashboardPage() {
  const { transactions, categories, accounts, incomeSources, scope, setScope, profile } = useData();
  const months = useMemo(() => availableMonths(transactions), [transactions]);
  const [selectedMonth, setSelectedMonth] = useState('');

  useEffect(() => {
    if (!selectedMonth || !months.includes(selectedMonth)) {
      setSelectedMonth(months.length ? months[months.length - 1] : '');
    }
  }, [months]); // eslint-disable-line react-hooks/exhaustive-deps

  const mk = selectedMonth || months[months.length - 1] || '';
  const m = useMemo(() => computeMonth(transactions, scope, profile, mk), [transactions, scope, profile, mk]);
  const prevMk = prevMonthKey(mk);
  const prev = useMemo(() => computeMonth(transactions, scope, profile, prevMk), [transactions, scope, profile, prevMk]);

  const income = monthlyIncome(m, incomeSources);
  const prevIncome = monthlyIncome(prev, incomeSources);
  const savings = income - m.consumption;
  const savingsRate = income > 0 ? Math.round((savings / income) * 100) : 0;

  const scopedTxns = useMemo(() => inScope(transactions, scope, profile), [transactions, scope, profile]);
  const creditCards = accounts.filter((a) => a.type === 'credit_card');
  const totalOutstanding = creditCards.reduce(
    (acc, c) => acc + (computeAccountBalance(scopedTxns, c).outstanding || 0),
    0
  );

  const monthList = monthTxns(transactions, scope, profile, mk);
  const catData = useMemo(() => categoryBreakdown(monthList, categories), [monthList, categories]);
  const topCategories = catData.slice(0, 6);
  const merchants = useMemo(() => merchantBreakdown(monthList, 8), [monthList]);
  const totalExpense = catData.reduce((a, c) => a + c.value, 0);

  const trendMonths = months.slice(-6);
  const trend = useMemo(
    () => trendMonths.map((tm) => ({ mk: tm, ...computeMonth(transactions, scope, profile, tm) })),
    [transactions, scope, profile, trendMonths.join(',')] // eslint-disable-line react-hooks/exhaustive-deps
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
        <StatCard label="Income" value={income} foot="salary + other" />
        <StatCard label="Expenses" value={m.accrual} foot="what you truly spent" />
        <StatCard label="Savings rate" value={`${savingsRate}%`} raw tone={savingsRate >= 20 ? 'good' : 'warning'} foot={`saved ${fmtINR(savings)}`} />
        <StatCard label="Invested" value={m.investments} foot="SIPs, RDs, insurance" />
        <StatCard label="CC outstanding" value={totalOutstanding} foot={totalOutstanding > 0 ? 'across all cards' : 'in credit'} />
      </div>

      <Card title="Month over month" hint={prevMk ? `vs ${monthLabel(prevMk)}` : 'no prior month'} className="mom-card" style={{ marginTop: 16 }}>
        <div className="card-pad">
          <div className="mom-grid">
            <div className="mom-item">
              <div className="note">Income</div>
              <div className="num mom-val">{fmtINR(income)}</div>
              <Delta now={income} prev={prevIncome} />
            </div>
            <div className="mom-item">
              <div className="note">Expenses</div>
              <div className="num mom-val">{fmtINR(m.accrual)}</div>
              <Delta now={m.accrual} prev={prev.accrual} invert />
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

      <div className="grid two-col" style={{ marginTop: 16 }}>
        <Card title="Category breakdown" hint="expenses this month">
          <div className="card-pad">
            {catData.length ? (
              <DonutChart data={catData.map((c) => ({ label: c.label, value: c.value, color: c.color }))} />
            ) : (
              <EmptyState>No expenses categorised this month.</EmptyState>
            )}
          </div>
        </Card>
        <Card title="Income vs expenses" hint="last 6 months">
          <div className="card-pad">
            <BarChart
              categories={trend.map((t) => monthLabel(t.mk))}
              series={[
                { name: 'Income', color: 'var(--status-good)', values: trend.map((t) => monthlyIncome(t, incomeSources)) },
                { name: 'Expenses', color: 'var(--series-1)', values: trend.map((t) => t.accrual) },
              ]}
            />
          </div>
        </Card>
      </div>

      <div className="grid two-col" style={{ marginTop: 16 }}>
        <Card title="Spending trend" hint="accrual vs cash out, 6 months">
          <div className="card-pad">
            <BarChart
              categories={trend.map((t) => monthLabel(t.mk))}
              series={[
                { name: 'Accrual expense', color: 'var(--series-1)', values: trend.map((t) => t.accrual) },
                { name: 'Cash outflow', color: 'var(--series-2)', values: trend.map((t) => t.cashOutflow) },
              ]}
            />
          </div>
        </Card>
        <Card title="Highest spending categories" hint="this month">
          <div className="card-pad">
            {topCategories.length ? (
              <div className="rank-list">
                {topCategories.map((c) => {
                  const pct = totalExpense > 0 ? Math.round((c.value / totalExpense) * 100) : 0;
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
                    </tr>
                  </thead>
                  <tbody>
                    {merchants.map((mrow) => (
                      <tr key={mrow.merchant}>
                        <td>{mrow.merchant}</td>
                        <td className="num">{mrow.count}</td>
                        <td className="num">{fmtINR(mrow.value)}</td>
                        <td className="num col-2">{fmtINR(mrow.value / mrow.count)}</td>
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
