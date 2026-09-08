import { useMemo, useState } from 'react';
import { Button, Card, EmptyState, Field, Modal, PageHeader, Select } from '../components/ui';
import { fmtINR, monthKey, sum } from '../lib/format';
import { availableMonths } from '../lib/compute';
import { useData } from '../context/DataContext';

const KINDS = [
  { value: 'salary', label: 'Salary' },
  { value: 'other', label: 'Other' },
];
const BLANK = { name: '', kind: 'salary', monthlyAmount: '', member: '', active: true };

function IncomeModal({ initial, members, onSave, onClose }) {
  const [form, setForm] = useState(initial);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    const ok = await onSave({
      name: form.name.trim(),
      kind: form.kind,
      monthlyAmount: Number(form.monthlyAmount) || 0,
      member: form.member,
      active: form.active,
    });
    if (ok) onClose();
  }

  return (
    <Modal title={initial.id ? 'Edit income source' : 'Add income source'} onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Name">
          <input value={form.name} onChange={set('name')} placeholder="e.g. Salary, Freelance, Rent" required autoFocus />
        </Field>
        <Field label="Kind">
          <Select value={form.kind} onChange={set('kind')} options={KINDS} />
        </Field>
        <Field label="Monthly amount (₹)">
          <input type="number" step="0.01" value={form.monthlyAmount} onChange={set('monthlyAmount')} placeholder="0" required />
        </Field>
        <Field label="Earned by" hint="Optional.">
          <Select value={form.member} onChange={set('member')} placeholder="—">
            {members.map((m) => (
              <option key={m.id}>{m.name}</option>
            ))}
          </Select>
        </Field>
        <div className="form-actions">
          <Button type="submit" variant="primary">
            {initial.id ? 'Save' : 'Add source'}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default function IncomePage() {
  const { incomeSources, members, transactions, addIncome, updateIncome, removeIncome } = useData();
  const [modal, setModal] = useState(null);

  const months = useMemo(() => availableMonths(transactions), [transactions]);
  const latest = months[months.length - 1] || '';
  const recurring = sum(incomeSources.filter((s) => s.active), (s) => Number(s.monthlyAmount) || 0);
  const adhocThisMonth = sum(
    transactions.filter((t) => t.type === 'Income' && monthKey(t.date) === latest)
  );

  function save(payload) {
    return modal.id ? updateIncome(modal.id, payload) : addIncome(payload);
  }

  return (
    <section>
      <PageHeader title="Income" subtitle="Recurring salary and other income. One-off income is logged as a transaction of type Income.">
        <Button variant="primary" size="sm" onClick={() => setModal({ ...BLANK })}>
          + Add source
        </Button>
      </PageHeader>

      <div className="grid kpi-row">
        <div className="kpi">
          <div className="label">Recurring monthly</div>
          <div className="value">{fmtINR(recurring)}</div>
          <div className="foot">{incomeSources.filter((s) => s.active).length} active source(s)</div>
        </div>
        <div className="kpi">
          <div className="label">Ad-hoc this month</div>
          <div className="value">{fmtINR(adhocThisMonth)}</div>
          <div className="foot">logged as Income transactions</div>
        </div>
        <div className="kpi">
          <div className="label">Expected total</div>
          <div className="value">{fmtINR(recurring + adhocThisMonth)}</div>
          <div className="foot">recurring + ad-hoc</div>
        </div>
      </div>

      <Card title="Income sources" style={{ marginTop: 16 }}>
        <div className="table-wrap">
          <table>
            {incomeSources.length ? (
              <>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th className="col-2">Kind</th>
                    <th className="col-2">Earned by</th>
                    <th className="num">Monthly</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {incomeSources.map((s) => (
                    <tr key={s.id}>
                      <td>{s.name}</td>
                      <td className="col-2" style={{ textTransform: 'capitalize' }}>{s.kind}</td>
                      <td className="col-2">{s.member || <span className="note">—</span>}</td>
                      <td className="num">{fmtINR(s.monthlyAmount)}</td>
                      <td className="cell-actions">
                        <Button size="sm" variant="ghost" onClick={() => setModal({ ...s, monthlyAmount: s.monthlyAmount })}>
                          Edit
                        </Button>{' '}
                        <Button size="sm" variant="danger" onClick={() => confirm(`Remove ${s.name}?`) && removeIncome(s.id)}>
                          Remove
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </>
            ) : (
              <tbody>
                <tr>
                  <td className="empty">No income sources yet — add your salary to start.</td>
                </tr>
              </tbody>
            )}
          </table>
        </div>
      </Card>

      {modal && <IncomeModal initial={modal} members={members} onSave={save} onClose={() => setModal(null)} />}
    </section>
  );
}
