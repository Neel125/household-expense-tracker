import { useMemo, useState } from 'react';
import BarChart from '../components/charts/BarChart';
import DonutChart from '../components/charts/DonutChart';
import {
  Button,
  Card,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Pill,
  ProgressBar,
  Select,
  StatCard,
} from '../components/ui';
import { fmtINR, shortDate } from '../lib/format';
import { useData } from '../context/DataContext';

// ---------------------------------------------------------- static registries
const INVESTMENT_KINDS = [
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
const INV_META = Object.fromEntries(INVESTMENT_KINDS.map((k) => [k.value, k]));
const INV_COLORS = {
  fd: 'var(--series-1)',
  rd: '#0ea5e9',
  sip: 'var(--series-3)',
  mutual_fund: '#22c55e',
  stock: 'var(--series-2)',
  bond: '#8b5cf6',
  gold: 'var(--series-4)',
  ppf_epf: '#14b8a6',
  other: '#94a3b8',
};

const DEBT_KINDS = [
  { value: 'home_loan', label: 'Home Loan', icon: '🏠' },
  { value: 'car_loan', label: 'Car Loan', icon: '🚗' },
  { value: 'personal_loan', label: 'Personal Loan', icon: '💳' },
  { value: 'consumer_loan', label: 'Consumer / EMI', icon: '📱' },
  { value: 'education_loan', label: 'Education Loan', icon: '🎓' },
  { value: 'business_loan', label: 'Business Loan', icon: '🏢' },
  { value: 'credit_card_debt', label: 'Credit Card Debt', icon: '💳' },
  { value: 'other', label: 'Other', icon: '📦' },
];
const DEBT_META = Object.fromEntries(DEBT_KINDS.map((k) => [k.value, k]));

// ------------------------------------------------------------ blank templates
const BLANK_INVESTMENT = {
  id: null,
  name: '',
  kind: 'fd',
  institution: '',
  amountInvested: '',
  currentValue: '',
  annualReturnPct: '',
  monthlyContribution: '',
  startDate: '',
  maturityDate: '',
  notes: '',
};
const BLANK_DEBT = {
  id: null,
  name: '',
  kind: 'home_loan',
  lender: '',
  principal: '',
  outstanding: '',
  annualRatePct: '',
  emi: '',
  tenureMonths: '',
  monthsPaid: '',
  startDate: '',
  notes: '',
};

// -------------------------------------------------------- shared row helpers
function toPayload(form, numericKeys) {
  const out = { ...form };
  for (const k of numericKeys) out[k] = Number(out[k]) || 0;
  return out;
}

function InvestmentModal({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    const payload = toPayload(form, [
      'amountInvested', 'currentValue', 'annualReturnPct', 'monthlyContribution',
    ]);
    const ok = await onSave(payload);
    setBusy(false);
    if (ok) onClose();
  }

  return (
    <Modal title={form.id ? `Edit ${form.name || 'investment'}` : 'Add investment'} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label="Name">
            <input value={form.name} onChange={set('name')} placeholder="e.g. SBI FD 5Y" required autoFocus />
          </Field>
          <Field label="Kind">
            <Select
              value={form.kind}
              onChange={set('kind')}
              options={INVESTMENT_KINDS.map((k) => ({ value: k.value, label: k.label }))}
            />
          </Field>
          <Field label="Institution">
            <input value={form.institution} onChange={set('institution')} placeholder="Bank / broker / AMC" />
          </Field>
          <Field label="Amount invested (₹)">
            <input type="number" step="1000" value={form.amountInvested} onChange={set('amountInvested')} />
          </Field>
          <Field label="Current value (₹)" hint="Today's value — override the Tools calculators here.">
            <input type="number" step="1000" value={form.currentValue} onChange={set('currentValue')} />
          </Field>
          <Field label="Expected return (% p.a.)">
            <input type="number" step="0.1" value={form.annualReturnPct} onChange={set('annualReturnPct')} />
          </Field>
          <Field label="Monthly contribution (₹)" hint="For SIPs / RDs. Leave 0 for lump-sum products.">
            <input type="number" step="500" value={form.monthlyContribution} onChange={set('monthlyContribution')} />
          </Field>
          <Field label="Start date">
            <input type="date" value={form.startDate} onChange={set('startDate')} />
          </Field>
          <Field label="Maturity date">
            <input type="date" value={form.maturityDate} onChange={set('maturityDate')} />
          </Field>
          <Field label="Notes" className="span-3">
            <input value={form.notes} onChange={set('notes')} placeholder="optional" />
          </Field>
        </div>
        <div className="form-actions">
          <Button type="submit" variant="primary" disabled={busy}>
            {form.id ? 'Save' : 'Add investment'}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Modal>
  );
}

function DebtModal({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    const payload = toPayload(form, [
      'principal', 'outstanding', 'annualRatePct', 'emi', 'tenureMonths', 'monthsPaid',
    ]);
    const ok = await onSave(payload);
    setBusy(false);
    if (ok) onClose();
  }

  return (
    <Modal title={form.id ? `Edit ${form.name || 'debt'}` : 'Add debt'} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label="Name">
            <input value={form.name} onChange={set('name')} placeholder="e.g. SBI Home Loan" required autoFocus />
          </Field>
          <Field label="Kind">
            <Select
              value={form.kind}
              onChange={set('kind')}
              options={DEBT_KINDS.map((k) => ({ value: k.value, label: k.label }))}
            />
          </Field>
          <Field label="Lender">
            <input value={form.lender} onChange={set('lender')} placeholder="Bank / NBFC" />
          </Field>
          <Field label="Original principal (₹)">
            <input type="number" step="10000" value={form.principal} onChange={set('principal')} />
          </Field>
          <Field label="Outstanding (₹)" hint="Current balance. If blank, we assume it equals the principal.">
            <input type="number" step="10000" value={form.outstanding} onChange={set('outstanding')} />
          </Field>
          <Field label="Interest rate (% p.a.)">
            <input type="number" step="0.05" value={form.annualRatePct} onChange={set('annualRatePct')} />
          </Field>
          <Field label="EMI (₹)">
            <input type="number" step="500" value={form.emi} onChange={set('emi')} />
          </Field>
          <Field label="Original tenure (months)">
            <input type="number" step="1" value={form.tenureMonths} onChange={set('tenureMonths')} />
          </Field>
          <Field label="Months paid">
            <input type="number" step="1" value={form.monthsPaid} onChange={set('monthsPaid')} />
          </Field>
          <Field label="Start date">
            <input type="date" value={form.startDate} onChange={set('startDate')} />
          </Field>
          <Field label="Notes" className="span-3">
            <input value={form.notes} onChange={set('notes')} placeholder="optional" />
          </Field>
        </div>
        <div className="form-actions">
          <Button type="submit" variant="primary" disabled={busy}>
            {form.id ? 'Save' : 'Add debt'}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Modal>
  );
}

// -------------------------------------------------------------- list items
function InvestmentRow({ inv, onEdit, onDelete }) {
  const meta = INV_META[inv.kind] || INV_META.other;
  const gain = (inv.currentValue || 0) - (inv.amountInvested || 0);
  const gainPct = inv.amountInvested > 0 ? (gain / inv.amountInvested) * 100 : 0;
  const tone = gain > 0 ? 'up-good' : gain < 0 ? 'up-bad' : '';
  return (
    <div className="asset-row">
      <div className="asset-icon" style={{ background: INV_COLORS[inv.kind] || 'var(--accent-wash)' }}>
        {meta.icon}
      </div>
      <div className="asset-main">
        <div className="asset-title">
          {inv.name}
          <span className="asset-kind"><Pill>{meta.label}</Pill></span>
        </div>
        <div className="note">
          {inv.institution || '—'}
          {inv.startDate && <> · started {shortDate(inv.startDate)}</>}
          {inv.maturityDate && <> · matures {shortDate(inv.maturityDate)}</>}
        </div>
      </div>
      <div className="asset-figures">
        <div className="asset-value">{fmtINR(inv.currentValue)}</div>
        <div className={'note ' + tone}>
          {gain >= 0 ? '+' : '−'}{fmtINR(Math.abs(gain))} ({gainPct >= 0 ? '+' : ''}{gainPct.toFixed(1)}%)
        </div>
        <div className="note">invested {fmtINR(inv.amountInvested)}</div>
      </div>
      <div className="asset-actions">
        <Button size="sm" variant="ghost" onClick={onEdit}>Edit</Button>
        <Button size="sm" variant="danger" onClick={onDelete}>Remove</Button>
      </div>
    </div>
  );
}

function DebtRow({ debt, onEdit, onDelete }) {
  const meta = DEBT_META[debt.kind] || DEBT_META.other;
  const paidPct =
    debt.principal > 0
      ? Math.max(0, Math.min(100, ((debt.principal - debt.outstanding) / debt.principal) * 100))
      : 0;
  const monthsRemaining =
    debt.tenureMonths > 0 ? Math.max(0, debt.tenureMonths - (debt.monthsPaid || 0)) : 0;
  return (
    <div className="asset-row">
      <div className="asset-icon debt-icon">{meta.icon}</div>
      <div className="asset-main">
        <div className="asset-title">
          {debt.name}
          <span className="asset-kind"><Pill tone="warning">{meta.label}</Pill></span>
        </div>
        <div className="note">
          {debt.lender || '—'}
          {debt.emi > 0 && <> · EMI {fmtINR(debt.emi)}</>}
          {debt.annualRatePct > 0 && <> · {debt.annualRatePct}% p.a.</>}
        </div>
        <div style={{ marginTop: 6 }}>
          <div className="note" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span>Paid off</span>
            <span className="num">{fmtINR(debt.principal - debt.outstanding)} of {fmtINR(debt.principal)}</span>
          </div>
          <ProgressBar pct={paidPct} />
        </div>
      </div>
      <div className="asset-figures">
        <div className="asset-value">{fmtINR(debt.outstanding)}</div>
        <div className="note">outstanding</div>
        {monthsRemaining > 0 && (
          <div className="note">{monthsRemaining} EMI{monthsRemaining === 1 ? '' : 's'} left</div>
        )}
      </div>
      <div className="asset-actions">
        <Button size="sm" variant="ghost" onClick={onEdit}>Edit</Button>
        <Button size="sm" variant="danger" onClick={onDelete}>Remove</Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- the page
export default function PortfolioPage() {
  const {
    investments,
    debts,
    addInvestment,
    updateInvestment,
    removeInvestment,
    addDebt,
    updateDebt,
    removeDebt,
  } = useData();
  const [invModal, setInvModal] = useState(null);
  const [debtModal, setDebtModal] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(null); // {kind, id, name}

  const totalInvested = useMemo(
    () => investments.reduce((a, i) => a + (Number(i.amountInvested) || 0), 0),
    [investments]
  );
  const totalValue = useMemo(
    () => investments.reduce((a, i) => a + (Number(i.currentValue) || 0), 0),
    [investments]
  );
  const totalGain = totalValue - totalInvested;
  const totalDebt = useMemo(
    () => debts.reduce((a, d) => a + (Number(d.outstanding) || 0), 0),
    [debts]
  );
  const monthlyEmi = useMemo(
    () => debts.reduce((a, d) => a + (Number(d.emi) || 0), 0),
    [debts]
  );
  const monthlyContribution = useMemo(
    () => investments.reduce((a, i) => a + (Number(i.monthlyContribution) || 0), 0),
    [investments]
  );
  const netWorth = totalValue - totalDebt;

  // Investment mix — donut by kind (aggregated).
  const investmentMix = useMemo(() => {
    const buckets = new Map();
    for (const inv of investments) {
      const v = Number(inv.currentValue) || 0;
      if (v <= 0) continue;
      buckets.set(inv.kind, (buckets.get(inv.kind) || 0) + v);
    }
    return Array.from(buckets, ([kind, value]) => ({
      label: INV_META[kind]?.label || kind,
      value,
      color: INV_COLORS[kind] || '#94a3b8',
    }));
  }, [investments]);

  const debtBars = useMemo(
    () => debts.filter((d) => (Number(d.outstanding) || 0) > 0),
    [debts]
  );

  async function saveInvestment(payload) {
    if (invModal?.id) return updateInvestment(invModal.id, payload);
    return addInvestment(payload);
  }
  async function saveDebt(payload) {
    if (debtModal?.id) return updateDebt(debtModal.id, payload);
    return addDebt(payload);
  }
  async function doRemove() {
    const { kind, id } = confirmRemove;
    const ok = kind === 'investment' ? await removeInvestment(id) : await removeDebt(id);
    if (ok) setConfirmRemove(null);
  }

  return (
    <section>
      <PageHeader
        title="Portfolio"
        subtitle="Household assets and debts. Tracking an investment earns 25 coins; maturity pays 100. Closing a home loan pays 1,000, a car loan 500, and other loans 100."
      />

      <div className="grid kpi-row">
        <StatCard label="Net worth" value={netWorth} tone={netWorth >= 0 ? 'good' : 'warning'} foot="assets − debts" />
        <StatCard label="Investments" value={totalValue} foot={`invested ${fmtINR(totalInvested)}`} />
        <StatCard
          label="Gains"
          value={totalGain}
          tone={totalGain >= 0 ? 'good' : 'warning'}
          foot={totalInvested > 0 ? `${((totalGain / totalInvested) * 100).toFixed(1)}%` : '—'}
        />
        <StatCard label="Debts" value={totalDebt} tone={totalDebt > 0 ? 'warning' : undefined} foot="outstanding" />
        <StatCard label="Monthly EMI" value={monthlyEmi} foot={monthlyContribution > 0 ? `SIP/RD ${fmtINR(monthlyContribution)}` : 'total across debts'} />
      </div>

      {(investmentMix.length > 0 || debtBars.length > 0) && (
        <div className="grid two-col" style={{ marginTop: 16 }}>
          <Card title="Investment mix" hint="current value by kind">
            <div className="card-pad">
              {investmentMix.length ? (
                <DonutChart data={investmentMix} />
              ) : (
                <EmptyState>No investment values yet.</EmptyState>
              )}
            </div>
          </Card>
          <Card title="Debts outstanding" hint="balance remaining per loan">
            <div className="card-pad">
              {debtBars.length ? (
                <BarChart
                  categories={debtBars.map((d) => d.name)}
                  series={[
                    {
                      name: 'Outstanding',
                      color: 'var(--status-critical)',
                      values: debtBars.map((d) => Number(d.outstanding) || 0),
                    },
                    {
                      name: 'Paid off',
                      color: 'var(--status-good)',
                      values: debtBars.map(
                        (d) => Math.max(0, (Number(d.principal) || 0) - (Number(d.outstanding) || 0))
                      ),
                    },
                  ]}
                />
              ) : (
                <EmptyState>No debts yet — nothing to plot.</EmptyState>
              )}
            </div>
          </Card>
        </div>
      )}

      <div className="grid two-col" style={{ marginTop: 16 }}>
        <Card
          title="Investments"
          hint={`${investments.length} item${investments.length === 1 ? '' : 's'}`}
          actions={
            <Button size="sm" variant="primary" onClick={() => setInvModal({ ...BLANK_INVESTMENT })}>
              + Add investment
            </Button>
          }
        >
          <div className="card-pad">
            {investments.length === 0 ? (
              <EmptyState>
                Add your FDs, RDs, SIPs, stocks or gold to track them here.
              </EmptyState>
            ) : (
              <div className="asset-list">
                {investments.map((inv) => (
                  <InvestmentRow
                    key={inv.id}
                    inv={inv}
                    onEdit={() =>
                      setInvModal({
                        id: inv.id,
                        name: inv.name || '',
                        kind: inv.kind || 'other',
                        institution: inv.institution || '',
                        amountInvested: inv.amountInvested || '',
                        currentValue: inv.currentValue || '',
                        annualReturnPct: inv.annualReturnPct || '',
                        monthlyContribution: inv.monthlyContribution || '',
                        startDate: inv.startDate || '',
                        maturityDate: inv.maturityDate || '',
                        notes: inv.notes || '',
                      })
                    }
                    onDelete={() => setConfirmRemove({ kind: 'investment', id: inv.id, name: inv.name })}
                  />
                ))}
              </div>
            )}
          </div>
        </Card>

        <Card
          title="Debts & EMIs"
          hint={`${debts.length} item${debts.length === 1 ? '' : 's'}`}
          actions={
            <Button size="sm" variant="primary" onClick={() => setDebtModal({ ...BLANK_DEBT })}>
              + Add debt
            </Button>
          }
        >
          <div className="card-pad">
            {debts.length === 0 ? (
              <EmptyState>
                Add home / car / personal / consumer loans and any other EMIs
                to see them here.
              </EmptyState>
            ) : (
              <div className="asset-list">
                {debts.map((d) => (
                  <DebtRow
                    key={d.id}
                    debt={d}
                    onEdit={() =>
                      setDebtModal({
                        id: d.id,
                        name: d.name || '',
                        kind: d.kind || 'other',
                        lender: d.lender || '',
                        principal: d.principal || '',
                        outstanding: d.outstanding || '',
                        annualRatePct: d.annualRatePct || '',
                        emi: d.emi || '',
                        tenureMonths: d.tenureMonths || '',
                        monthsPaid: d.monthsPaid || '',
                        startDate: d.startDate || '',
                        notes: d.notes || '',
                      })
                    }
                    onDelete={() => setConfirmRemove({ kind: 'debt', id: d.id, name: d.name })}
                  />
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      {invModal && (
        <InvestmentModal
          initial={invModal}
          onSave={saveInvestment}
          onClose={() => setInvModal(null)}
        />
      )}
      {debtModal && (
        <DebtModal
          initial={debtModal}
          onSave={saveDebt}
          onClose={() => setDebtModal(null)}
        />
      )}
      {confirmRemove && (
        <Modal
          title={`Remove ${confirmRemove.name || confirmRemove.kind}?`}
          onClose={() => setConfirmRemove(null)}
        >
          <p className="note">
            This just removes the entry from your tracker — it doesn't affect any
            transactions or account balances.
          </p>
          <div className="form-actions">
            <Button variant="primary-danger" onClick={doRemove}>Remove</Button>
            <Button variant="ghost" onClick={() => setConfirmRemove(null)}>Cancel</Button>
          </div>
        </Modal>
      )}
    </section>
  );
}
