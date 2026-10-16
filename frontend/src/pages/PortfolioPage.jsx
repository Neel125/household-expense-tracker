import { useEffect, useMemo, useState } from 'react';
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
import { api } from '../api';
import { fmtINR, shortDate } from '../lib/format';
import {
  DEBT_KINDS,
  DEBT_META,
  INVESTMENT_KINDS,
  INV_COLORS,
  INV_META,
} from '../lib/portfolioMeta';
import { useData } from '../context/DataContext';

const TODAY = () => new Date().toISOString().slice(0, 10);

function depositAccounts(accounts) {
  return (accounts || []).filter(
    (a) => !a.archived && ['bank', 'debit_card', 'cash'].includes(a.type)
  );
}

function isMatured(inv) {
  const d = (inv.maturityDate || '').slice(0, 10);
  return Boolean(d && d <= TODAY());
}

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
    <Modal title={form.id ? `Edit ${form.name || 'investment'}` : 'Add investment'} onClose={onClose} size="form">
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
          <Field
            label="Opening invested (₹)"
            hint="What went in before you started logging transactions. Linked Investment transactions add on top of this."
          >
            <input type="number" step="1000" value={form.amountInvested} onChange={set('amountInvested')} />
          </Field>
          <Field label="Current value (₹)" hint="Leave 0 to let the expected return project it from your contributions.">
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
    <Modal title={form.id ? `Edit ${form.name || 'debt'}` : 'Add debt'} onClose={onClose} size="form">
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
          <Field
            label="Opening outstanding (₹)"
            hint="The balance when you started logging EMIs here. Linked Loan transactions pay it down from this figure."
          >
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
          <Field label="EMIs paid before tracking">
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

// ------------------------------------------------------------ detail modals
// Both fetch on open rather than riding along in the list response: a
// full instalment history per holding would bloat every page load, and
// this is a click-to-inspect view.
function useDetail(fetcher, dep) {
  const [state, setState] = useState({ loading: true, error: '', data: null });
  useEffect(() => {
    let live = true;
    fetcher()
      .then((data) => live && setState({ loading: false, error: '', data }))
      .catch((e) => live && setState({ loading: false, error: e.message, data: null }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dep]);
  return state;
}

function DebtScheduleModal({ debt, onClose }) {
  const { loading, error, data } = useDetail(() => api.debts.schedule(debt.id), debt.id);
  const rows = data?.instalments || [];
  return (
    <Modal title={`${debt.name} — where each payment went`} onClose={onClose} wide>
      <p className="note">
        An EMI is split into interest (on the balance at the time) and principal. A{' '}
        <strong>partial payment</strong> skips that split — the whole amount comes off the
        principal, which is what you see on the loan’s outstanding.
      </p>
      {loading ? (
        <EmptyState>Loading the schedule…</EmptyState>
      ) : error ? (
        <EmptyState>{error}</EmptyState>
      ) : rows.length === 0 ? (
        <EmptyState>No EMIs linked to this loan yet.</EmptyState>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th style={{ textAlign: 'right' }}>Paid</th>
                  <th style={{ textAlign: 'right' }}>Interest</th>
                  <th style={{ textAlign: 'right' }}>Principal</th>
                  <th style={{ textAlign: 'right' }}>Balance</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.transactionId}>
                    <td className="cell-date note">
                      {shortDate(r.date)}
                      {r.kind === 'prepay' ? ' · partial' : ''}
                    </td>
                    <td className="num" style={{ textAlign: 'right' }}>{fmtINR(r.paid)}</td>
                    <td className="num up-bad" style={{ textAlign: 'right' }}>{fmtINR(r.interest)}</td>
                    <td className="num up-good" style={{ textAlign: 'right' }}>{fmtINR(r.principal)}</td>
                    <td className="num" style={{ textAlign: 'right' }}>{fmtINR(r.balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="earn-row" style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
            <span className="note">
              {rows.length} payment{rows.length === 1 ? '' : 's'} ·{' '}
              {fmtINR(data.debt.totalPaid)} paid
            </span>
            <span className="num">
              <span className="up-good">{fmtINR(data.debt.principalRepaid)}</span> principal +{' '}
              <span className="up-bad">{fmtINR(data.debt.interestPaid)}</span> interest
            </span>
          </div>
        </>
      )}
    </Modal>
  );
}

function WithdrawModal({ investment, accounts, members, defaultMember, onSave, onClose }) {
  const banks = depositAccounts(accounts);
  const [form, setForm] = useState({
    date: TODAY(),
    amount: investment.effectiveValue || '',
    accountName: banks[0]?.name || '',
    member: defaultMember || '',
  });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    if (!form.accountName) {
      alert('Pick the bank account that receives the money');
      return;
    }
    setBusy(true);
    const ok = await onSave({
      date: form.date,
      amount: Number(form.amount) || 0,
      accountName: form.accountName,
      member: form.member,
    });
    setBusy(false);
    if (ok) onClose();
  }

  return (
    <Modal title={`Withdraw ${investment.name}`} onClose={onClose} size="form">
      <form onSubmit={submit}>
        <p className="note" style={{ marginTop: 0 }}>
          Closes this holding and logs an <strong>Investment Withdrawal</strong> on
          Transactions, crediting the selected account. That is not income — it is money
          coming back from the investment.
        </p>
        <div className="form-grid">
          <Field label="Date">
            <input type="date" value={form.date} onChange={set('date')} required />
          </Field>
          <Field label="Amount (₹)" hint="Defaults to today’s value. Change it for a penalty or extra interest.">
            <input type="number" min="0" step="0.01" value={form.amount} onChange={set('amount')} required />
          </Field>
          <Field label="Transfer to">
            <Select
              value={form.accountName}
              onChange={set('accountName')}
              placeholder={banks.length ? 'Select account' : 'Add a bank account first'}
              options={banks.map((a) => ({ value: a.name, label: a.name }))}
            />
          </Field>
          <Field label="Logged by">
            <Select
              value={form.member}
              onChange={set('member')}
              placeholder="—"
              options={members.map((m) => m.name)}
            />
          </Field>
        </div>
        <div className="form-actions">
          <Button type="submit" variant="primary" disabled={busy || !banks.length}>
            Withdraw and close
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Modal>
  );
}

function ReinvestModal({ investment, accounts, members, defaultMember, onSave, onClose }) {
  const banks = depositAccounts(accounts);
  const [form, setForm] = useState({
    date: TODAY(),
    amount: investment.effectiveValue || '',
    addOnAmount: '',
    accountName: banks[0]?.name || '',
    newName: `${investment.name} (renewed)`,
    newMaturityDate: '',
    annualReturnPct: investment.annualReturnPct || '',
    member: defaultMember || '',
    notes: '',
  });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const proceeds = Number(form.amount) || 0;
  const addOn = Number(form.addOnAmount) || 0;
  const total = proceeds + addOn;

  async function submit(e) {
    e.preventDefault();
    if (addOn > 0 && !form.accountName) {
      alert('Pick the bank account the add-on is paid from');
      return;
    }
    if (total <= 0) {
      alert('Reinvest needs the matured value or an add-on amount');
      return;
    }
    setBusy(true);
    const ok = await onSave({
      date: form.date,
      amount: proceeds,
      addOnAmount: addOn,
      accountName: form.accountName,
      newName: form.newName.trim(),
      newMaturityDate: form.newMaturityDate,
      annualReturnPct: form.annualReturnPct === '' ? undefined : Number(form.annualReturnPct) || 0,
      member: form.member,
      notes: form.notes.trim(),
    });
    setBusy(false);
    if (ok) onClose();
  }

  return (
    <Modal title={`Reinvest ${investment.name}`} onClose={onClose} size="form">
      <form onSubmit={submit}>
        <p className="note" style={{ marginTop: 0 }}>
          The matured amount stays invested as the new holding’s opening — no transaction
          for that rollover. Only an add-on is logged on Transactions, as extra money
          leaving the selected account.
        </p>
        <div className="form-grid">
          <Field label="Date">
            <input type="date" value={form.date} onChange={set('date')} required />
          </Field>
          <Field label="Matured proceeds (₹)">
            <input type="number" min="0" step="0.01" value={form.amount} onChange={set('amount')} required />
          </Field>
          <Field label="Add-on from bank (₹)" hint="Extra money invested on renewal. Leave 0 to roll the proceeds only.">
            <input type="number" min="0" step="0.01" value={form.addOnAmount} onChange={set('addOnAmount')} />
          </Field>
          <Field label="New principal">
            <input value={fmtINR(total)} readOnly />
          </Field>
          <Field
            label="Add-on paid from"
            hint={addOn > 0 ? 'Required. Only this extra amount is debited from the account.' : 'Needed only if you add extra money.'}
          >
            <Select
              value={form.accountName}
              onChange={set('accountName')}
              placeholder={banks.length ? 'Select account' : 'Add a bank account first'}
              options={banks.map((a) => ({ value: a.name, label: a.name }))}
            />
          </Field>
          <Field label="New name">
            <input value={form.newName} onChange={set('newName')} required />
          </Field>
          <Field label="New maturity date">
            <input type="date" value={form.newMaturityDate} onChange={set('newMaturityDate')} />
          </Field>
          <Field label="Expected return (% p.a.)">
            <input type="number" step="0.1" value={form.annualReturnPct} onChange={set('annualReturnPct')} />
          </Field>
          <Field label="Logged by">
            <Select
              value={form.member}
              onChange={set('member')}
              placeholder="—"
              options={members.map((m) => m.name)}
            />
          </Field>
          <Field label="Notes" className="span-3">
            <input value={form.notes} onChange={set('notes')} placeholder="optional" />
          </Field>
        </div>
        <div className="form-actions">
          <Button type="submit" variant="primary" disabled={busy || (addOn > 0 && !banks.length)}>
            Reinvest {addOn > 0 ? `with ${fmtINR(addOn)} add-on` : 'and close'}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Modal>
  );
}

function ContributionsModal({ investment, onClose }) {
  const { loading, error, data } = useDetail(
    () => api.investments.get(investment.id),
    investment.id
  );
  const ledger = data?.ledger?.length ? data.ledger : (data?.contributions || []).map((r) => ({
    ...r,
    kind: 'contribution',
    providerType: '',
  }));
  const inv = data?.investment;
  const withdrawn = ledger.filter((r) => r.kind === 'withdrawal').reduce((a, r) => a + (Number(r.amount) || 0), 0);
  const paidIn = ledger.filter((r) => r.kind !== 'withdrawal').reduce((a, r) => a + (Number(r.amount) || 0), 0);
  return (
    <Modal title={`${investment.name} — history`} onClose={onClose} wide>
      <p className="note">
        Every transaction logged against this holding — contributions in, withdrawals out,
        and any add-on at renewal. These also appear on the Transactions page.
      </p>
      {loading ? (
        <EmptyState>Loading history…</EmptyState>
      ) : error ? (
        <EmptyState>{error}</EmptyState>
      ) : ledger.length === 0 ? (
        <EmptyState>Nothing linked to this holding yet.</EmptyState>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>What</th>
                  <th>Account</th>
                  <th style={{ textAlign: 'right' }}>In</th>
                  <th style={{ textAlign: 'right' }}>Out</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((r) => {
                  const out = r.kind === 'withdrawal';
                  return (
                    <tr key={r.transactionId}>
                      <td className="cell-date note">{shortDate(r.date)}</td>
                      <td>
                        {r.name}
                        <span className="note"> · {out ? 'withdrawal' : r.name?.includes('add-on') ? 'add-on' : 'contribution'}</span>
                      </td>
                      <td className="note">{r.providerType || '—'}</td>
                      <td className="num" style={{ textAlign: 'right' }}>{out ? '' : fmtINR(r.amount)}</td>
                      <td className={'num' + (out ? ' amount-income' : '')} style={{ textAlign: 'right' }}>
                        {out ? `+${fmtINR(r.amount)}` : ''}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="earn-row" style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
            <span className="note">
              {ledger.length} transaction{ledger.length === 1 ? '' : 's'}
              {inv?.amountInvested > 0 && <> · {fmtINR(inv.amountInvested)} opening</>}
            </span>
            <span className="num">
              {paidIn > 0 && <>in {fmtINR(paidIn)}</>}
              {paidIn > 0 && withdrawn > 0 && ' · '}
              {withdrawn > 0 && <span className="amount-income">out {fmtINR(withdrawn)}</span>}
            </span>
          </div>
        </>
      )}
    </Modal>
  );
}

// -------------------------------------------------------------- list items
// Every figure below `invested` comes from the backend, which sums the
// linked Investment transactions and grows each one from its own date.
function InvestmentRow({ inv, onEdit, onDelete, onHistory, onWithdraw, onReinvest }) {
  const meta = INV_META[inv.kind] || INV_META.other;
  const tone = inv.gain > 0 ? 'up-good' : inv.gain < 0 ? 'up-bad' : '';
  const linked = inv.contributionCount > 0;
  const closed = inv.isClosed;
  const matured = !closed && isMatured(inv);
  return (
    <div className={'asset-row' + (closed ? ' is-closed' : '')}>
      <div className="asset-icon" style={{ background: INV_COLORS[inv.kind] || 'var(--accent-wash)' }}>
        {meta.icon}
      </div>
      <div className="asset-main">
        <div className="asset-title">
          {inv.name}
          <span className="asset-kind"><Pill>{meta.label}</Pill></span>
          {closed && (
            <span className="asset-kind">
              <Pill tone="good">{inv.successorId ? 'reinvested' : 'closed'}</Pill>
            </span>
          )}
          {matured && (
            <span className="asset-kind"><Pill tone="warning">matured</Pill></span>
          )}
          {linked && !closed && <span className="asset-kind"><Pill tone="good">auto</Pill></span>}
        </div>
        <div className="note">
          {inv.institution || '—'}
          {inv.startDate && <> · started {shortDate(inv.startDate)}</>}
          {closed
            ? inv.closedAt && <> · closed {shortDate(inv.closedAt)}</>
            : inv.maturityDate && <> · matures {shortDate(inv.maturityDate)}</>}
        </div>
        {closed && (
          <div className="note" style={{ marginTop: 4 }}>
            {fmtINR(inv.closedValue)} transferred
            {inv.closedToAccount ? <> to {inv.closedToAccount}</> : ''}
            {inv.successorId ? ' and rolled into a new holding' : ''}
          </div>
        )}
        {matured && (
          <div className="note" style={{ marginTop: 4 }}>
            Matured — withdraw to a bank or reinvest with an add-on.
          </div>
        )}
        {linked && (
          <div className="note" style={{ marginTop: 4 }}>
            {inv.contributionCount} logged contribution{inv.contributionCount === 1 ? '' : 's'} ·{' '}
            {fmtINR(inv.contributed)}
            {inv.amountInvested > 0 && <> on top of {fmtINR(inv.amountInvested)} opening</>}
            {inv.lastContributionDate && <> · last {shortDate(inv.lastContributionDate)}</>}
          </div>
        )}
      </div>
      <div className="asset-figures">
        <div className="asset-value">{fmtINR(closed ? inv.closedValue : inv.effectiveValue)}</div>
        <div className={'note ' + tone}>
          {inv.gain >= 0 ? '+' : '−'}{fmtINR(Math.abs(inv.gain))} (
          {inv.gainPct >= 0 ? '+' : ''}{Number(inv.gainPct).toFixed(1)}%)
        </div>
        <div className="note">invested {fmtINR(inv.totalInvested)}</div>
        <div className="note">
          {closed ? 'closed' : inv.valueIsManual ? 'your valuation' : 'projected'}
        </div>
      </div>
      <div className="asset-actions">
        {!closed && (
          <>
            <Button size="sm" variant="ghost" onClick={onWithdraw}>Withdraw</Button>
            <Button size="sm" variant="ghost" onClick={onReinvest}>Reinvest</Button>
          </>
        )}
        {(linked || closed) && (
          <Button size="sm" variant="ghost" onClick={onHistory}>History</Button>
        )}
        {!closed && <Button size="sm" variant="ghost" onClick={onEdit}>Edit</Button>}
        <Button size="sm" variant="danger" onClick={onDelete}>Remove</Button>
      </div>
    </div>
  );
}

// `outstandingNow`, `principalRepaid` and `interestPaid` are amortised by
// the backend over the EMIs linked to this loan — see the schedule modal
// for the per-payment split.
function DebtRow({ debt, onEdit, onDelete, onSchedule }) {
  const meta = DEBT_META[debt.kind] || DEBT_META.other;
  const monthsRemaining =
    debt.tenureMonths > 0 ? Math.max(0, debt.tenureMonths - (debt.emisPaid || 0)) : 0;
  const linked = debt.paymentCount > 0;
  return (
    <div className="asset-row">
      <div className="asset-icon debt-icon">{meta.icon}</div>
      <div className="asset-main">
        <div className="asset-title">
          {debt.name}
          <span className="asset-kind"><Pill tone="warning">{meta.label}</Pill></span>
          {debt.isClosed && <span className="asset-kind"><Pill tone="good">closed</Pill></span>}
          {linked && !debt.isClosed && <span className="asset-kind"><Pill tone="good">auto</Pill></span>}
        </div>
        <div className="note">
          {debt.lender || '—'}
          {debt.emi > 0 && <> · EMI {fmtINR(debt.emi)}</>}
          {debt.annualRatePct > 0 && <> · {debt.annualRatePct}% p.a.</>}
        </div>
        <div className="asset-progress">
          <div className="note" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span>Paid off</span>
            <span className="num">
              {fmtINR(Math.max(0, (debt.principal || 0) - debt.outstandingNow))} of{' '}
              {fmtINR(debt.principal)}
            </span>
          </div>
          <ProgressBar pct={debt.payoffPct} />
        </div>
        {linked && (
          <div className="note" style={{ marginTop: 6 }}>
            {debt.paymentCount} logged EMI{debt.paymentCount === 1 ? '' : 's'} ·{' '}
            <span className="up-good">{fmtINR(debt.principalRepaid)} principal</span> ·{' '}
            <span className="up-bad">{fmtINR(debt.interestPaid)} interest</span>
            {debt.lastPaymentDate && <> · last {shortDate(debt.lastPaymentDate)}</>}
          </div>
        )}
      </div>
      <div className="asset-figures">
        <div className="asset-value">{fmtINR(debt.outstandingNow)}</div>
        <div className="note">outstanding</div>
        {monthsRemaining > 0 && (
          <div className="note">{monthsRemaining} EMI{monthsRemaining === 1 ? '' : 's'} left</div>
        )}
      </div>
      <div className="asset-actions">
        {linked && (
          <Button size="sm" variant="ghost" onClick={onSchedule}>EMI split</Button>
        )}
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
    accounts,
    members,
    profile,
    addInvestment,
    updateInvestment,
    removeInvestment,
    withdrawInvestment,
    reinvestInvestment,
    addDebt,
    updateDebt,
    removeDebt,
  } = useData();
  const [invModal, setInvModal] = useState(null);
  const [debtModal, setDebtModal] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(null); // {kind, id, name}
  const [schedule, setSchedule] = useState(null); // a debt, for the EMI split
  const [contributions, setContributions] = useState(null); // an investment
  const [withdrawInv, setWithdrawInv] = useState(null);
  const [reinvestInv, setReinvestInv] = useState(null);

  const openInvestments = useMemo(
    () => investments.filter((i) => !i.isClosed),
    [investments]
  );
  const listedInvestments = useMemo(
    () => [...openInvestments, ...investments.filter((i) => i.isClosed)],
    [investments, openInvestments]
  );

  // `totalInvested` and `effectiveValue` already fold in every linked
  // transaction, so these totals move the moment an SIP or EMI is logged.
  // Closed holdings are excluded: their value now sits in a bank (or in
  // the successor holding), and counting both would double net worth.
  const totalInvested = useMemo(
    () => openInvestments.reduce((a, i) => a + (Number(i.totalInvested) || 0), 0),
    [openInvestments]
  );
  const totalValue = useMemo(
    () => openInvestments.reduce((a, i) => a + (Number(i.effectiveValue) || 0), 0),
    [openInvestments]
  );
  const totalGain = totalValue - totalInvested;
  const totalDebt = useMemo(
    () => debts.reduce((a, d) => a + (Number(d.outstandingNow) || 0), 0),
    [debts]
  );
  const autoContributed = useMemo(
    () => openInvestments.reduce((a, i) => a + (Number(i.contributed) || 0), 0),
    [openInvestments]
  );
  const principalRepaid = useMemo(
    () => debts.reduce((a, d) => a + (Number(d.principalRepaid) || 0), 0),
    [debts]
  );
  const interestPaid = useMemo(
    () => debts.reduce((a, d) => a + (Number(d.interestPaid) || 0), 0),
    [debts]
  );
  const monthlyEmi = useMemo(
    () => debts.reduce((a, d) => a + (Number(d.emi) || 0), 0),
    [debts]
  );
  const monthlyContribution = useMemo(
    () => openInvestments.reduce((a, i) => a + (Number(i.monthlyContribution) || 0), 0),
    [openInvestments]
  );
  const netWorth = totalValue - totalDebt;

  // Investment mix — donut by kind (aggregated).
  const investmentMix = useMemo(() => {
    const buckets = new Map();
    for (const inv of openInvestments) {
      const v = Number(inv.effectiveValue) || 0;
      if (v <= 0) continue;
      buckets.set(inv.kind, (buckets.get(inv.kind) || 0) + v);
    }
    return Array.from(buckets, ([kind, value]) => ({
      label: INV_META[kind]?.label || kind,
      value,
      color: INV_COLORS[kind] || '#94a3b8',
    }));
  }, [openInvestments]);

  const debtBars = useMemo(
    () => debts.filter((d) => (Number(d.outstandingNow) || 0) > 0),
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
        subtitle="Household assets and debts. Log an Investment transaction against a holding and it adds to the invested total. At maturity, withdraw the proceeds to a bank or reinvest with an add-on. Log a Loan EMI against a debt to split interest and principal, or a Loan partial payment to cut principal in full."
      />

      <div className="grid kpi-row">
        <StatCard label="Net worth" value={netWorth} tone={netWorth >= 0 ? 'good' : 'warning'} foot="assets − debts" />
        <StatCard
          label="Investments"
          value={totalValue}
          foot={
            autoContributed > 0
              ? `invested ${fmtINR(totalInvested)} · ${fmtINR(autoContributed)} from transactions`
              : `invested ${fmtINR(totalInvested)}`
          }
        />
        <StatCard
          label="Gains"
          value={totalGain}
          tone={totalGain >= 0 ? 'good' : 'warning'}
          foot={totalInvested > 0 ? `${((totalGain / totalInvested) * 100).toFixed(1)}%` : '—'}
        />
        <StatCard
          label="Debts"
          value={totalDebt}
          tone={totalDebt > 0 ? 'warning' : undefined}
          foot={
            principalRepaid > 0
              ? `${fmtINR(principalRepaid)} principal repaid · ${fmtINR(interestPaid)} interest`
              : 'outstanding'
          }
        />
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
                      values: debtBars.map((d) => Number(d.outstandingNow) || 0),
                    },
                    {
                      name: 'Paid off',
                      color: 'var(--status-good)',
                      values: debtBars.map(
                        (d) => Math.max(0, (Number(d.principal) || 0) - (Number(d.outstandingNow) || 0))
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

      <div className="grid two-col-even" style={{ marginTop: 16 }}>
        <Card
          title="Investments"
          hint={`${openInvestments.length} open · ${investments.length} total`}
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
                {listedInvestments.map((inv) => (
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
                    onHistory={() => setContributions(inv)}
                    onWithdraw={() => setWithdrawInv(inv)}
                    onReinvest={() => setReinvestInv(inv)}
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
                    onSchedule={() => setSchedule(d)}
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
      {schedule && <DebtScheduleModal debt={schedule} onClose={() => setSchedule(null)} />}
      {contributions && (
        <ContributionsModal investment={contributions} onClose={() => setContributions(null)} />
      )}
      {withdrawInv && (
        <WithdrawModal
          investment={withdrawInv}
          accounts={accounts}
          members={members}
          defaultMember={profile}
          onSave={(payload) => withdrawInvestment(withdrawInv.id, payload)}
          onClose={() => setWithdrawInv(null)}
        />
      )}
      {reinvestInv && (
        <ReinvestModal
          investment={reinvestInv}
          accounts={accounts}
          members={members}
          defaultMember={profile}
          onSave={(payload) => reinvestInvestment(reinvestInv.id, payload)}
          onClose={() => setReinvestInv(null)}
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
