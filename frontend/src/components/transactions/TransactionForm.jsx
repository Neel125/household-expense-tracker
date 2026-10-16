import { useEffect, useMemo, useState } from 'react';
import { Button, Field, Select } from '../ui';
import { fmtINR } from '../../lib/format';

const fmtPct = (n) => (Number(n) > 0 ? `${Number(n)}% p.a.` : 'no rate set');

const TYPES = [
  { value: 'Expense', label: 'Expense' },
  { value: 'Income', label: 'Income' },
  { value: 'Investment', label: 'Investment' },
  { value: 'Investment Withdrawal', label: 'Investment withdrawal' },
  { value: 'Loan', label: 'Loan EMI' },
  { value: 'Loan Partial', label: 'Loan partial payment' },
  { value: 'CC Repayment', label: 'CC Repayment' },
];
const PAYMENT_MODES = ['UPI', 'Credit Card', 'Cash', 'Auto Debit', 'Debit Card', 'Net Banking'];
const NECESSITIES = ['Need', 'Want', 'Investment', 'Debt'];
const TYPE_TO_NECESSITY = {
  Investment: 'Investment',
  Loan: 'Debt',
  'Loan Partial': 'Debt',
  'CC Repayment': 'Debt',
};
const TODAY = () => new Date().toISOString().slice(0, 10);

const BLANK = {
  date: TODAY(),
  name: '',
  type: 'Expense',
  amount: '',
  paymentMode: 'UPI',
  providerType: '',
  necessity: 'Need',
  account: '',
  member: '',
  categoryId: '',
  merchant: '',
  investmentId: '',
  debtId: '',
};

function fromTxn(t, defaultMember) {
  if (!t) return { ...BLANK, member: defaultMember || '' };
  return {
    date: t.date || TODAY(),
    name: t.name || '',
    type: t.type || 'Expense',
    amount: t.amount ?? '',
    paymentMode: t.paymentMode || 'UPI',
    providerType: t.providerType || '',
    necessity: t.necessity || 'Need',
    account: t.account || '',
    member: t.member || defaultMember || '',
    categoryId: t.categoryId ?? '',
    merchant: t.merchant || '',
    investmentId: t.investmentId ?? '',
    debtId: t.debtId ?? '',
  };
}

// The one form for adding and editing. `editingTxn` switches it to edit
// mode. Providers and settle-targets come from the household's accounts,
// categories from its category list — no hardcoded bank names.
//
// An Investment row can name the holding it pays into and a Loan row the
// debt it pays down. That link is what makes the Portfolio page's figures
// move on their own: the backend amortises linked EMIs and sums linked
// contributions rather than asking the user to keep two numbers in step.
export default function TransactionForm({
  editingTxn,
  accounts,
  categories,
  members,
  investments = [],
  debts = [],
  defaultMember,
  onSave,
  onCancel,
}) {
  const [form, setForm] = useState(() => fromTxn(editingTxn, defaultMember));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setForm(fromTxn(editingTxn, defaultMember));
  }, [editingTxn, defaultMember]);

  function set(key, value) {
    setForm((f) => {
      const next = { ...f, [key]: value };
      if (key === 'type' && TYPE_TO_NECESSITY[value]) next.necessity = TYPE_TO_NECESSITY[value];
      return next;
    });
  }

  const isIncome = form.type === 'Income';
  const isWithdrawal = form.type === 'Investment Withdrawal';
  const isCredit = isIncome || isWithdrawal;
  const isLoanPartial = form.type === 'Loan Partial';
  const showSettle = form.type === 'CC Repayment' || form.type === 'Loan' || isLoanPartial;
  const showInvestmentLink = form.type === 'Investment' || isWithdrawal;
  const showDebtLink = form.type === 'Loan' || isLoanPartial;

  const providerOptions = useMemo(
    () => accounts.filter((a) => !a.archived).map((a) => a.name),
    [accounts]
  );
  const settleOptions = useMemo(
    () => accounts.filter((a) => a.type === 'credit_card' || a.type === 'loan').map((a) => a.name),
    [accounts]
  );
  const memberOptions = useMemo(() => {
    const names = members.map((m) => m.name);
    return form.member && !names.includes(form.member) ? [form.member, ...names] : names;
  }, [members, form.member]);
  const activeCategories = useMemo(() => categories.filter((c) => !c.archived), [categories]);
  // Loans already paid off stay selectable while editing an old EMI, but
  // are not offered for a new one.
  const openDebts = useMemo(
    () => debts.filter((d) => !d.isClosed || String(d.id) === String(form.debtId)),
    [debts, form.debtId]
  );
  const linkableInvestments = useMemo(
    () =>
      investments.filter(
        (i) =>
          !i.isClosed || isWithdrawal || String(i.id) === String(form.investmentId)
      ),
    [investments, isWithdrawal, form.investmentId]
  );
  const selectedDebt = useMemo(
    () => debts.find((d) => String(d.id) === String(form.debtId)),
    [debts, form.debtId]
  );

  async function submit(e) {
    e.preventDefault();
    if (!form.date || !form.name.trim() || !Number(form.amount)) {
      alert('Fill in date, name and amount');
      return;
    }
    if (form.type === 'Loan Partial' && !form.debtId) {
      alert('Pick the loan this partial payment pays down');
      return;
    }
    setBusy(true);
    const payload = {
      date: form.date,
      name: form.name.trim(),
      type: form.type,
      amount: Number(form.amount) || 0,
      paymentMode: form.paymentMode,
      providerType: form.providerType || '',
      necessity: isCredit ? '' : form.necessity,
      account: showSettle ? form.account : '',
      member: form.member || defaultMember || '',
      categoryId: form.categoryId ? Number(form.categoryId) : null,
      merchant: form.merchant.trim(),
      // Sent only for the type each link belongs to. The backend drops a
      // mismatched link anyway; not sending it keeps the payload honest.
      investmentId: showInvestmentLink && form.investmentId ? Number(form.investmentId) : null,
      debtId: showDebtLink && form.debtId ? Number(form.debtId) : null,
    };
    const ok = await onSave(payload);
    setBusy(false);
    if (ok && !editingTxn) setForm({ ...BLANK, member: defaultMember || '' });
  }

  return (
    <form onSubmit={submit}>
      <div className="form-grid">
        <Field label="Date">
          <input type="date" value={form.date} onChange={(e) => set('date', e.target.value)} required />
        </Field>
        <Field label={isIncome ? 'Income name' : 'Name'}>
          <input
            type="text"
            placeholder={
              isIncome
                ? 'e.g. Salary, Bonus'
                : isWithdrawal
                  ? 'e.g. SBI FD — withdrawn'
                  : 'e.g. Bike fuel'
            }
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            required
          />
        </Field>
        <Field label="Amount (₹)">
          <input
            type="number"
            min="0"
            step="0.01"
            placeholder="0"
            value={form.amount}
            onChange={(e) => set('amount', e.target.value)}
            required
          />
        </Field>

        <Field label="Type">
          <Select value={form.type} onChange={(e) => set('type', e.target.value)} options={TYPES} />
        </Field>
        <Field label="Payment mode">
          <Select value={form.paymentMode} onChange={(e) => set('paymentMode', e.target.value)} options={PAYMENT_MODES} />
        </Field>
        <Field label={isCredit ? 'Deposited to' : 'Paid from / provider'}>
          <Select value={form.providerType} onChange={(e) => set('providerType', e.target.value)} placeholder="—" options={providerOptions} />
        </Field>

        {!isCredit && (
          <Field label="Necessity">
            <Select value={form.necessity} onChange={(e) => set('necessity', e.target.value)} options={NECESSITIES} />
          </Field>
        )}
        {!isCredit && (
          <Field label="Category">
            <Select value={form.categoryId} onChange={(e) => set('categoryId', e.target.value)} placeholder="Uncategorized">
              {activeCategories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label="Merchant">
          <input
            type="text"
            placeholder="e.g. Amazon, Local Bakery"
            value={form.merchant}
            onChange={(e) => set('merchant', e.target.value)}
          />
        </Field>

        {showSettle && (
          <Field label={form.type === 'CC Repayment' ? 'Settles card' : 'Loan account'}>
            <Select value={form.account} onChange={(e) => set('account', e.target.value)} placeholder="—" options={settleOptions} />
          </Field>
        )}
        {showInvestmentLink && (
          <Field
            label="Adds to investment"
            hint={
              isWithdrawal
                ? 'The holding this money came out of.'
                : investments.length
                  ? 'Optional. Linking adds this amount to the holding on the Portfolio page.'
                  : 'Add a holding on the Portfolio page first.'
            }
          >
            <Select
              value={form.investmentId}
              onChange={(e) => set('investmentId', e.target.value)}
              placeholder="— not linked —"
            >
              {linkableInvestments.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name}
                  {i.isClosed ? ' · closed' : ''}
                </option>
              ))}
            </Select>
          </Field>
        )}
        {showDebtLink && (
          <Field
            label={isLoanPartial ? 'Pays down loan' : 'Pays down loan'}
            hint={
              isLoanPartial
                ? selectedDebt
                  ? `The full ₹ amount reduces principal on “${selectedDebt.name}” (${fmtINR(selectedDebt.outstandingNow)} left).`
                  : 'Required. The whole payment comes off the selected loan’s principal.'
                : selectedDebt
                  ? `${fmtPct(selectedDebt.annualRatePct)} — interest is worked out on the balance and the rest reduces the principal.`
                  : debts.length
                    ? 'Optional. Linking splits this EMI into interest and principal.'
                    : 'Add a loan on the Portfolio page first.'
            }
          >
            <Select
              value={form.debtId}
              onChange={(e) => set('debtId', e.target.value)}
              placeholder={isLoanPartial ? 'Select loan' : '— not linked —'}
              required={isLoanPartial}
            >
              {openDebts.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                  {d.outstandingNow > 0 ? ` · ${fmtINR(d.outstandingNow)} left` : ''}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label="Logged by">
          <Select value={form.member} onChange={(e) => set('member', e.target.value)} placeholder="—" options={memberOptions} />
        </Field>
      </div>

      <div className="form-actions">
        <Button type="submit" variant="primary" disabled={busy}>
          {editingTxn ? 'Save changes' : 'Add transaction'}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
