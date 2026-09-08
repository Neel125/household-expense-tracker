import { useEffect, useMemo, useState } from 'react';
import { Button, Field, Select } from '../ui';

const TYPES = ['Expense', 'Income', 'Investment', 'Loan', 'CC Repayment'];
const PAYMENT_MODES = ['UPI', 'Credit Card', 'Cash', 'Auto Debit', 'Debit Card', 'Net Banking'];
const NECESSITIES = ['Need', 'Want', 'Investment', 'Debt'];
const TYPE_TO_NECESSITY = { Investment: 'Investment', Loan: 'Debt', 'CC Repayment': 'Debt' };
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
  };
}

// The one form for adding and editing. `editingTxn` switches it to edit
// mode. Providers and settle-targets come from the household's accounts,
// categories from its category list — no hardcoded bank names.
export default function TransactionForm({
  editingTxn,
  accounts,
  categories,
  members,
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
  const showSettle = form.type === 'CC Repayment' || form.type === 'Loan';

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

  async function submit(e) {
    e.preventDefault();
    if (!form.date || !form.name.trim() || !Number(form.amount)) {
      alert('Fill in date, name and amount');
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
      necessity: isIncome ? '' : form.necessity,
      account: showSettle ? form.account : '',
      member: form.member || defaultMember || '',
      categoryId: form.categoryId ? Number(form.categoryId) : null,
      merchant: form.merchant.trim(),
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
            placeholder={isIncome ? 'e.g. Salary, Bonus' : 'e.g. Bike fuel'}
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
        <Field label={isIncome ? 'Deposited to' : 'Paid from / provider'}>
          <Select value={form.providerType} onChange={(e) => set('providerType', e.target.value)} placeholder="—" options={providerOptions} />
        </Field>

        {!isIncome && (
          <Field label="Necessity">
            <Select value={form.necessity} onChange={(e) => set('necessity', e.target.value)} options={NECESSITIES} />
          </Field>
        )}
        {!isIncome && (
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
