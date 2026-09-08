import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
} from '../components/ui';
import MonthSelect from '../components/ui/MonthSelect';
import { fmtINR, monthLabel, sum } from '../lib/format';
import {
  availableMonths,
  computeMember,
  memberTotals,
  memberTxns,
} from '../lib/compute';
import { useData } from '../context/DataContext';

const RELATIONS = ['Self', 'Spouse', 'Parent', 'Child', 'Sibling', 'Other'];
const BLANK = { name: '', relation: '', monthlyBudget: '' };

// Rotating palette for family members. `var(--series-N)` is limited to 4;
// we fall back to a couple of extras so bigger households still get
// distinct colours.
const MEMBER_PALETTE = [
  'var(--series-1)',
  'var(--series-2)',
  'var(--series-3)',
  'var(--series-4)',
  '#8b5cf6',
  '#ec4899',
  '#0ea5e9',
  '#f97316',
];
const memberColor = (i) => MEMBER_PALETTE[i % MEMBER_PALETTE.length];

function MemberModal({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  async function submit(e) {
    e.preventDefault();
    const ok = await onSave({
      name: form.name.trim(),
      relation: form.relation,
      monthlyBudget: Number(form.monthlyBudget) || 0,
    });
    if (ok) onClose();
  }
  return (
    <Modal title={initial.id ? `Edit ${initial.name}` : 'Add family member'} onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Name">
          <input value={form.name} onChange={set('name')} placeholder="e.g. Priya" required autoFocus />
        </Field>
        <Field label="Relation">
          <Select value={form.relation} onChange={set('relation')} placeholder="—" options={RELATIONS} />
        </Field>
        <Field label="Monthly budget (₹)" hint="Optional personal cap.">
          <input type="number" min="0" value={form.monthlyBudget} onChange={set('monthlyBudget')} placeholder="optional" />
        </Field>
        <div className="form-actions">
          <Button type="submit" variant="primary">
            {initial.id ? 'Save' : 'Add member'}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function RemoveModal({ member, count, others, onConfirm, onClose }) {
  const [target, setTarget] = useState(others[0]?.name ?? '');
  return (
    <Modal title={`Remove ${member.name}?`} onClose={onClose}>
      <p className="note">
        {count
          ? `${member.name} has ${count} transaction(s). Where should they go?`
          : `${member.name} has no transactions — this just removes them.`}
      </p>
      {count > 0 && (
        <Field label="Move their transactions to">
          <Select value={target} onChange={(e) => setTarget(e.target.value)}>
            {others.map((o) => (
              <option key={o.id} value={o.name}>
                {o.name}
              </option>
            ))}
            <option value="">Leave them untagged</option>
          </Select>
        </Field>
      )}
      <div className="form-actions">
        <Button variant="primary-danger" onClick={() => onConfirm(count ? target : '')}>
          Remove {member.name}
        </Button>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </Modal>
  );
}

export default function FamilyPage() {
  const {
    transactions,
    members,
    profile,
    addMember,
    updateMember,
    removeMember,
  } = useData();
  const navigate = useNavigate();
  const [month, setMonth] = useState(null);
  const [modal, setModal] = useState(null);
  const [removing, setRemoving] = useState(null);

  const months = useMemo(() => availableMonths(transactions), [transactions]);

  useEffect(() => {
    if (month === null || (month && !months.includes(month))) {
      setMonth(months.length ? months[months.length - 1] : '');
    }
  }, [months]); // eslint-disable-line react-hooks/exhaustive-deps

  const mk = month || '';
  const names = useMemo(() => members.map((m) => m.name), [members]);
  const stats = useMemo(() => memberTotals(transactions, names, mk), [transactions, names, mk]);
  const byName = useMemo(() => Object.fromEntries(stats.map((s) => [s.name, s])), [stats]);
  const householdAccrual = sum(stats, (s) => s.accrual);
  const allTimeCounts = useMemo(
    () => Object.fromEntries(names.map((n) => [n, memberTxns(transactions, n, '').length])),
    [transactions, names]
  );
  const periodLabel = mk ? monthLabel(mk) : 'all time';

  // Last 6 months of accrual for each member (trend chart).
  const trendMonths = useMemo(() => months.slice(-6), [months]);
  const memberTrend = useMemo(
    () =>
      members.map((m, i) => ({
        name: m.name,
        color: memberColor(i),
        values: trendMonths.map((tm) => computeMember(transactions, m.name, tm).accrual),
      })),
    [members, trendMonths, transactions]
  );

  const donutData = useMemo(
    () =>
      stats
        .map((s, i) => ({ label: s.name, value: s.accrual, color: memberColor(i) }))
        .filter((d) => d.value > 0),
    [stats]
  );

  const membersWithBudget = useMemo(
    () => members.filter((m) => Number(m.monthlyBudget) > 0),
    [members]
  );

  async function confirmRemove(reassignTo) {
    const ok = await removeMember(removing.id, reassignTo);
    if (ok) setRemoving(null);
  }

  function save(payload) {
    return modal.id ? updateMember(modal.id, payload) : addMember(payload);
  }

  const anySpendThisPeriod = householdAccrual > 0;
  const canCompare = members.length > 1 && anySpendThisPeriod;

  return (
    <section>
      <PageHeader
        title="Family members"
        subtitle={`${members.length} member(s) · ${periodLabel} · who spent what`}
      >
        <MonthSelect months={months} value={mk} onChange={setMonth} includeAll allLabel="All time" />
        <Button variant="primary" size="sm" onClick={() => setModal({ ...BLANK })}>
          + Add member
        </Button>
      </PageHeader>

      {members.length === 0 ? (
        <Card pad>
          <EmptyState>No family members yet — add the first one.</EmptyState>
        </Card>
      ) : (
        <div className="grid member-grid">
          {members.map((m, i) => {
            const s = byName[m.name] || computeMember([], m.name, mk);
            const budget = Number(m.monthlyBudget) || 0;
            const pct = budget > 0 ? (s.accrual / budget) * 100 : 0;
            const share = householdAccrual > 0 ? Math.round((s.accrual / householdAccrual) * 100) : 0;
            return (
              <div className="card card-pad member-card" key={m.id}>
                <div className="member-head">
                  <div
                    className="avatar avatar-lg"
                    style={{ background: memberColor(i), color: '#fff' }}
                  >
                    {(m.name || '?').slice(0, 1).toUpperCase()}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 15 }}>
                      {m.name}
                      {m.name === profile && (
                        <span style={{ marginLeft: 8 }}>
                          <Pill tone="good">you</Pill>
                        </span>
                      )}
                    </div>
                    <div className="note">
                      {m.relation || 'Household member'} · {s.count} txn{s.count === 1 ? '' : 's'}
                      {householdAccrual > 0 ? ` · ${share}% of household` : ''}
                    </div>
                  </div>
                </div>
                <hr className="divider" style={{ margin: '12px 0' }} />
                <div className="mini-stats">
                  <div>
                    <div className="note">Accrual expense</div>
                    <div className="num" style={{ fontWeight: 600, fontSize: 16 }}>{fmtINR(s.accrual)}</div>
                  </div>
                  <div>
                    <div className="note">Cash out</div>
                    <div className="num" style={{ fontWeight: 600, fontSize: 16 }}>{fmtINR(s.cashOutflow)}</div>
                  </div>
                  <div>
                    <div className="note">Need / Want</div>
                    <div className="num">{fmtINR(s.necessity.Need)} / {fmtINR(s.necessity.Want)}</div>
                  </div>
                  <div>
                    <div className="note">Invested</div>
                    <div className="num">{fmtINR(s.necessity.Investment)}</div>
                  </div>
                </div>
                {budget > 0 && mk && (
                  <div style={{ marginTop: 12 }}>
                    <div className="note" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span>Monthly budget</span>
                      <span className="num">{fmtINR(s.accrual)} of {fmtINR(budget)} · {Math.round(pct)}%</span>
                    </div>
                    <ProgressBar pct={pct} />
                    {pct > 100 && (
                      <div className="note" style={{ color: 'var(--status-critical)', marginTop: 4 }}>
                        Over budget by {fmtINR(s.accrual - budget)}
                      </div>
                    )}
                  </div>
                )}
                <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
                  <Button size="sm" onClick={() => navigate('/add', { state: { member: m.name } })}>
                    Add txn
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => navigate('/transactions', { state: { member: m.name } })}
                  >
                    View transactions
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setModal({ ...m, monthlyBudget: m.monthlyBudget || '' })}>
                    Edit
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => setRemoving(m)}>
                    Remove
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ============================ COMPARISON CHARTS ==================== */}
      {canCompare ? (
        <>
          <div className="grid two-col" style={{ marginTop: 16 }}>
            <Card title="Household share" hint={`${periodLabel} · accrual expense`}>
              <div className="card-pad">
                {donutData.length ? (
                  <DonutChart data={donutData} />
                ) : (
                  <EmptyState>No expenses tagged to a member this period.</EmptyState>
                )}
              </div>
            </Card>

            <Card title="Spend by member" hint={`${periodLabel} · accrual vs cash out`}>
              <div className="card-pad">
                <BarChart
                  categories={stats.map((s) => s.name)}
                  series={[
                    { name: 'Accrual expense', color: 'var(--series-1)', values: stats.map((s) => s.accrual) },
                    { name: 'Cash out of bank', color: 'var(--series-2)', values: stats.map((s) => s.cashOutflow) },
                  ]}
                />
              </div>
            </Card>
          </div>

          <div className="grid two-col" style={{ marginTop: 16 }}>
            <Card title="Need vs Want vs Investment" hint={`${periodLabel} · per member`}>
              <div className="card-pad">
                <BarChart
                  categories={stats.map((s) => s.name)}
                  series={[
                    { name: 'Need', color: 'var(--series-1)', values: stats.map((s) => s.necessity.Need || 0) },
                    { name: 'Want', color: 'var(--series-2)', values: stats.map((s) => s.necessity.Want || 0) },
                    { name: 'Investment', color: 'var(--series-3)', values: stats.map((s) => s.necessity.Investment || 0) },
                  ]}
                />
              </div>
            </Card>

            <Card
              title="Spend trend"
              hint={
                trendMonths.length > 1
                  ? `last ${trendMonths.length} months · accrual`
                  : 'need more months to compare'
              }
            >
              <div className="card-pad">
                {trendMonths.length > 1 ? (
                  <BarChart
                    categories={trendMonths.map(monthLabel)}
                    series={memberTrend}
                  />
                ) : (
                  <EmptyState>
                    Not enough history yet — add transactions across a few months to see the trend.
                  </EmptyState>
                )}
              </div>
            </Card>
          </div>

          {membersWithBudget.length > 0 && (
            <Card
              title="Budget usage"
              hint={`${periodLabel} · accrual vs their monthly cap`}
              style={{ marginTop: 16 }}
            >
              <div className="card-pad">
                <BarChart
                  categories={membersWithBudget.map((m) => m.name)}
                  series={[
                    {
                      name: 'Spent',
                      color: 'var(--series-2)',
                      values: membersWithBudget.map((m) => byName[m.name]?.accrual || 0),
                    },
                    {
                      name: 'Budget',
                      color: 'var(--series-3)',
                      values: membersWithBudget.map((m) => Number(m.monthlyBudget) || 0),
                    },
                  ]}
                />
              </div>
            </Card>
          )}
        </>
      ) : members.length > 0 && (
        <Card style={{ marginTop: 16 }} pad>
          <EmptyState>
            {members.length < 2
              ? 'Add a second family member to compare spending.'
              : `No spend tagged to members in ${periodLabel} yet — comparisons will appear here.`}
          </EmptyState>
        </Card>
      )}

      {modal && <MemberModal initial={modal} onSave={save} onClose={() => setModal(null)} />}
      {removing && (
        <RemoveModal
          member={removing}
          count={allTimeCounts[removing.name] || 0}
          others={members.filter((o) => o.id !== removing.id)}
          onConfirm={confirmRemove}
          onClose={() => setRemoving(null)}
        />
      )}
    </section>
  );
}
