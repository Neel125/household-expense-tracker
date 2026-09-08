import { useState } from 'react';
import { Button, Card, EmptyState, Field, Modal, PageHeader, ProgressBar, Select } from '../components/ui';
import { fmtINR } from '../lib/format';
import { useData } from '../context/DataContext';

const KINDS = [
  { value: 'emergency', label: 'Emergency fund' },
  { value: 'vacation', label: 'Vacation' },
  { value: 'education', label: 'Education' },
  { value: 'home', label: 'Home' },
  { value: 'vehicle', label: 'Vehicle' },
  { value: 'custom', label: 'Custom' },
];
const KIND_ICON = { emergency: '⛑', vacation: '✈', education: '🎓', home: '🏠', vehicle: '🚗', custom: '◎' };
const BLANK = { name: '', kind: 'emergency', targetAmount: '', savedAmount: '', targetDate: '' };

function GoalModal({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    const ok = await onSave({
      name: form.name.trim(),
      kind: form.kind,
      targetAmount: Number(form.targetAmount) || 0,
      savedAmount: Number(form.savedAmount) || 0,
      targetDate: form.targetDate || '',
    });
    if (ok) onClose();
  }

  return (
    <Modal title={initial.id ? 'Edit goal' : 'New goal'} onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Name">
          <input value={form.name} onChange={set('name')} placeholder="e.g. 6-month emergency fund" required autoFocus />
        </Field>
        <Field label="Type">
          <Select value={form.kind} onChange={set('kind')} options={KINDS} />
        </Field>
        <Field label="Target amount (₹)">
          <input type="number" step="100" value={form.targetAmount} onChange={set('targetAmount')} required />
        </Field>
        <Field label="Already saved (₹)">
          <input type="number" step="100" value={form.savedAmount} onChange={set('savedAmount')} placeholder="0" />
        </Field>
        <Field label="Target date" hint="Optional.">
          <input type="date" value={form.targetDate} onChange={set('targetDate')} />
        </Field>
        <div className="form-actions">
          <Button type="submit" variant="primary">
            {initial.id ? 'Save' : 'Create goal'}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ContributeModal({ goal, onContribute, onClose }) {
  const [amount, setAmount] = useState('');
  return (
    <Modal title={`Add to ${goal.name}`} onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const ok = await onContribute(goal.id, Number(amount) || 0);
          if (ok) onClose();
        }}
      >
        <Field label="Contribution (₹)">
          <input type="number" step="100" value={amount} onChange={(e) => setAmount(e.target.value)} required autoFocus />
        </Field>
        <div className="form-actions">
          <Button type="submit" variant="primary">
            Add contribution
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default function GoalsPage() {
  const { goals, addGoal, updateGoal, contributeGoal, removeGoal } = useData();
  const [modal, setModal] = useState(null);
  const [contributing, setContributing] = useState(null);

  function save(payload) {
    return modal.id ? updateGoal(modal.id, payload) : addGoal(payload);
  }

  const totalTarget = goals.reduce((a, g) => a + g.targetAmount, 0);
  const totalSaved = goals.reduce((a, g) => a + g.savedAmount, 0);

  return (
    <section>
      <PageHeader title="Financial goals" subtitle="Emergency funds, vacations, education and more — track progress toward each.">
        <Button variant="primary" size="sm" onClick={() => setModal({ ...BLANK })}>
          + New goal
        </Button>
      </PageHeader>

      {goals.length > 0 && (
        <div className="grid kpi-row">
          <div className="kpi">
            <div className="label">Saved so far</div>
            <div className="value">{fmtINR(totalSaved)}</div>
            <div className="foot">across {goals.length} goal(s)</div>
          </div>
          <div className="kpi">
            <div className="label">Total target</div>
            <div className="value">{fmtINR(totalTarget)}</div>
            <div className="foot">combined goals</div>
          </div>
          <div className="kpi">
            <div className="label">Remaining</div>
            <div className="value">{fmtINR(Math.max(0, totalTarget - totalSaved))}</div>
            <div className="foot">{totalTarget > 0 ? Math.round((totalSaved / totalTarget) * 100) : 0}% funded</div>
          </div>
        </div>
      )}

      {goals.length === 0 ? (
        <Card pad style={{ marginTop: 16 }}>
          <EmptyState>No goals yet — create your first savings goal.</EmptyState>
        </Card>
      ) : (
        <div className="grid card-grid" style={{ marginTop: 16 }}>
          {goals.map((g) => {
            const pct = g.targetAmount > 0 ? (g.savedAmount / g.targetAmount) * 100 : 0;
            const remaining = Math.max(0, g.targetAmount - g.savedAmount);
            return (
              <div className="card card-pad" key={g.id}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="goal-icon">{KIND_ICON[g.kind] || '◎'}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 15 }}>{g.name}</div>
                    <div className="note" style={{ textTransform: 'capitalize' }}>
                      {g.kind}
                      {g.targetDate ? ` · by ${g.targetDate}` : ''}
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: 14 }}>
                  <div className="note" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span className="num">{fmtINR(g.savedAmount)}</span>
                    <span className="num">{fmtINR(g.targetAmount)}</span>
                  </div>
                  <ProgressBar pct={pct} over={false} />
                  <div className="note" style={{ marginTop: 6 }}>
                    {Math.round(pct)}% funded · {fmtINR(remaining)} to go
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
                  <Button size="sm" variant="primary" onClick={() => setContributing(g)}>
                    Add money
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setModal({ ...g, targetAmount: g.targetAmount, savedAmount: g.savedAmount })}>
                    Edit
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => confirm(`Delete ${g.name}?`) && removeGoal(g.id)}>
                    Delete
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modal && <GoalModal initial={modal} onSave={save} onClose={() => setModal(null)} />}
      {contributing && (
        <ContributeModal goal={contributing} onContribute={contributeGoal} onClose={() => setContributing(null)} />
      )}
    </section>
  );
}
