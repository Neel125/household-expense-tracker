import { useMemo, useState } from 'react';
import { Button, Card, EmptyState, Field, Modal, PageHeader, Pill, Select } from '../components/ui';
import { fmtINR } from '../lib/format';
import { computeAccountBalance, inScope } from '../lib/compute';
import { useData } from '../context/DataContext';

const TYPE_LABELS = {
  bank: 'Bank account',
  debit_card: 'Debit card',
  credit_card: 'Credit card',
  cash: 'Cash',
  loan: 'Loan',
};
const TYPE_OPTIONS = Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label }));
const GROUPS = ['bank', 'debit_card', 'cash', 'credit_card', 'loan'];
const BLANK = { name: '', type: 'bank', institution: '', openingBalance: '', linkedAccountId: '' };

function AccountModal({ initial, banks, onSave, onClose }) {
  const [form, setForm] = useState(initial);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const isDebit = form.type === 'debit_card';

  async function submit(e) {
    e.preventDefault();
    const ok = await onSave({
      name: form.name.trim(),
      type: form.type,
      institution: form.institution.trim(),
      openingBalance: Number(form.openingBalance) || 0,
      linkedAccountId: isDebit && form.linkedAccountId ? Number(form.linkedAccountId) : null,
      archived: false,
    });
    if (ok) onClose();
  }

  return (
    <Modal title={initial.id ? 'Edit account' : 'Add account'} onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Type">
          <Select value={form.type} onChange={set('type')} options={TYPE_OPTIONS} />
        </Field>
        <Field label="Name">
          <input value={form.name} onChange={set('name')} placeholder="e.g. HDFC Bank, OneCard, Wallet" required autoFocus />
        </Field>
        <Field label="Institution" hint="Optional bank/issuer name.">
          <input value={form.institution} onChange={set('institution')} placeholder="e.g. HDFC Bank" />
        </Field>
        {isDebit && (
          <Field label="Linked bank">
            <Select value={form.linkedAccountId} onChange={set('linkedAccountId')} placeholder="—">
              {banks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label={form.type === 'credit_card' ? 'Opening outstanding (₹)' : 'Opening balance (₹)'}>
          <input type="number" step="0.01" value={form.openingBalance} onChange={set('openingBalance')} placeholder="0" />
        </Field>
        <div className="form-actions">
          <Button type="submit" variant="primary">
            {initial.id ? 'Save' : 'Add account'}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default function AccountsPage() {
  const { accounts, transactions, scope, profile, addAccount, updateAccount, removeAccount } = useData();
  const [modal, setModal] = useState(null); // BLANK-shaped or existing account

  const scopedTxns = useMemo(() => inScope(transactions, scope, profile), [transactions, scope, profile]);
  const banks = accounts.filter((a) => a.type === 'bank');

  const liquid = accounts
    .filter((a) => ['bank', 'debit_card', 'cash'].includes(a.type))
    .reduce((acc, a) => acc + computeAccountBalance(scopedTxns, a).balance, 0);
  const owed = accounts
    .filter((a) => a.type === 'credit_card')
    .reduce((acc, a) => acc + (computeAccountBalance(scopedTxns, a).outstanding || 0), 0);

  function save(payload) {
    return modal.id ? updateAccount(modal.id, payload) : addAccount(payload);
  }

  return (
    <section>
      <PageHeader title="Accounts & cards" subtitle="Banks, debit cards, cash, credit cards and loans — with live balances.">
        <Button variant="primary" size="sm" onClick={() => setModal({ ...BLANK })}>
          + Add account
        </Button>
      </PageHeader>

      <div className="grid kpi-row">
        <div className="kpi">
          <div className="label">Liquid balance</div>
          <div className="value">{fmtINR(liquid)}</div>
          <div className="foot">banks + debit + cash</div>
        </div>
        <div className="kpi">
          <div className="label">Owed on cards</div>
          <div className="value">{fmtINR(owed)}</div>
          <div className="foot">credit card outstanding</div>
        </div>
        <div className="kpi">
          <div className="label">Net position</div>
          <div className="value">{fmtINR(liquid - owed)}</div>
          <div className="foot">liquid − owed</div>
        </div>
      </div>

      {GROUPS.map((group) => {
        const list = accounts.filter((a) => a.type === group);
        if (!list.length) return null;
        return (
          <div key={group} style={{ marginTop: 20 }}>
            <div className="section-label">{TYPE_LABELS[group]}s</div>
            <div className="grid card-grid">
              {list.map((a) => {
                const bal = computeAccountBalance(scopedTxns, a);
                return (
                  <div className="card card-pad" key={a.id}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 15, overflowWrap: 'anywhere' }}>{a.name}</div>
                        <div className="note">{a.institution || TYPE_LABELS[a.type]}</div>
                      </div>
                    </div>
                    <hr className="divider" style={{ margin: '12px 0' }} />
                    {a.type === 'credit_card' ? (
                      <>
                        <div className="mini-stats">
                          <div>
                            <div className="note">Spent</div>
                            <div className="num">{fmtINR(bal.spend)}</div>
                          </div>
                          <div>
                            <div className="note">Repaid</div>
                            <div className="num">{fmtINR(bal.repaid)}</div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
                          <div className="note">Outstanding</div>
                          <div className="num" style={{ fontWeight: 700, fontSize: 16 }}>{fmtINR(bal.outstanding)}</div>
                        </div>
                        <div style={{ marginTop: 8 }}>
                          <Pill tone={bal.outstanding > 0 ? 'warning' : 'good'}>
                            {bal.outstanding > 0 ? 'You owe' : 'Paid off / in credit'}
                          </Pill>
                        </div>
                      </>
                    ) : a.type === 'loan' ? (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div className="note">Paid to date</div>
                        <div className="num" style={{ fontWeight: 700, fontSize: 16 }}>{fmtINR(bal.paid)}</div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div className="note">Current balance</div>
                        <div className="num" style={{ fontWeight: 700, fontSize: 16 }}>{fmtINR(bal.balance)}</div>
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                      <Button size="sm" variant="ghost" onClick={() => setModal({ ...BLANK, ...a, openingBalance: a.openingBalance, linkedAccountId: a.linkedAccountId || '' })}>
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => confirm(`Remove ${a.name}?`) && removeAccount(a.id)}
                      >
                        Remove
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {accounts.length === 0 && (
        <Card pad style={{ marginTop: 16 }}>
          <EmptyState>No accounts yet — add your first bank, card or cash wallet.</EmptyState>
        </Card>
      )}

      {modal && <AccountModal initial={modal} banks={banks} onSave={save} onClose={() => setModal(null)} />}
    </section>
  );
}
