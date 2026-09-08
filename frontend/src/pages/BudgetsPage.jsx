import { useEffect, useMemo, useState } from 'react';
import { Button, Card, MonthSelect, PageHeader, ProgressBar } from '../components/ui';
import { fmtINR } from '../lib/format';
import { availableMonths, categoryBreakdown, monthTxns } from '../lib/compute';
import { useData } from '../context/DataContext';

export default function BudgetsPage() {
  const { budget, categories, transactions, scope, profile, saveBudget } = useData();
  const [monthlyBudget, setMonthlyBudget] = useState(0);
  const [pct, setPct] = useState({}); // categoryId -> percentage
  const [month, setMonth] = useState('');

  const months = useMemo(() => availableMonths(transactions), [transactions]);
  const activeCategories = useMemo(() => categories.filter((c) => !c.archived), [categories]);

  // Seed the editable form from the saved budget.
  useEffect(() => {
    setMonthlyBudget(budget.monthlyBudget || 0);
    setPct(Object.fromEntries(budget.categories.map((c) => [c.categoryId, c.percentage])));
  }, [budget]);

  useEffect(() => {
    if (!month || !months.includes(month)) setMonth(months.length ? months[months.length - 1] : '');
  }, [months]); // eslint-disable-line react-hooks/exhaustive-deps

  const spentByCat = useMemo(() => {
    const rows = categoryBreakdown(monthTxns(transactions, scope, profile, month), categories);
    return Object.fromEntries(rows.map((r) => [r.id, r.value]));
  }, [transactions, scope, profile, month, categories]);

  const totalPct = Object.values(pct).reduce((a, v) => a + (Number(v) || 0), 0);
  const over = totalPct > 100;

  function setCatPct(id, value) {
    setPct((p) => ({ ...p, [id]: value }));
  }

  function save() {
    const payload = {
      monthlyBudget: Number(monthlyBudget) || 0,
      categories: activeCategories
        .filter((c) => Number(pct[c.id]) > 0)
        .map((c) => ({ categoryId: c.id, percentage: Number(pct[c.id]) })),
    };
    saveBudget(payload);
  }

  return (
    <section>
      <PageHeader title="Budgets" subtitle="Set a monthly envelope, then split it across categories by percentage.">
        <MonthSelect months={months} value={month} onChange={setMonth} />
      </PageHeader>

      <Card pad style={{ marginBottom: 16 }}>
        <div className="budget-head">
          <div className="field" style={{ maxWidth: 220 }}>
            <label>Monthly budget (₹)</label>
            <input type="number" step="100" value={monthlyBudget} onChange={(e) => setMonthlyBudget(e.target.value)} />
          </div>
          <div className="budget-alloc">
            <div className="note">Allocated</div>
            <div className={'num' + (over ? ' amount-over' : '')} style={{ fontWeight: 700, fontSize: 18 }}>
              {Math.round(totalPct)}%
            </div>
            <div className="note">
              {over ? `${Math.round(totalPct - 100)}% over` : `${Math.round(100 - totalPct)}% unallocated`}
            </div>
          </div>
          <Button variant="primary" onClick={save}>
            Save budget
          </Button>
        </div>
        {over && <div className="form-error" style={{ marginTop: 10 }}>Category percentages add up to more than 100%.</div>}
      </Card>

      <Card title="Category budgets" hint="allocation vs this month's spend">
        <div className="card-pad">
          <div className="budget-list">
            {activeCategories.map((c) => {
              const percentage = Number(pct[c.id]) || 0;
              const allocated = ((Number(monthlyBudget) || 0) * percentage) / 100;
              const spent = spentByCat[c.id] || 0;
              const usedPct = allocated > 0 ? (spent / allocated) * 100 : spent > 0 ? 100 : 0;
              return (
                <div className="budget-row" key={c.id}>
                  <div className="budget-cat">
                    <span className="sw" style={{ background: c.color }} /> {c.name}
                  </div>
                  <div className="budget-pct">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={pct[c.id] ?? ''}
                      placeholder="0"
                      onChange={(e) => setCatPct(c.id, e.target.value)}
                    />
                    <span className="note">%</span>
                  </div>
                  <div className="budget-meter">
                    <ProgressBar pct={usedPct} over={allocated > 0 && spent > allocated} />
                    <div className="note">
                      {fmtINR(spent)} of {fmtINR(allocated)}
                      {allocated > 0 && spent > allocated && (
                        <span style={{ color: 'var(--status-critical)' }}> · over by {fmtINR(spent - allocated)}</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Card>
    </section>
  );
}
