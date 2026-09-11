import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import TransactionTable from '../components/transactions/TransactionTable';
import { Card, PageHeader, Select } from '../components/ui';
import MonthSelect from '../components/ui/MonthSelect';
import { monthKey } from '../lib/format';
import { availableMonths, inScope } from '../lib/compute';
import { useData } from '../context/DataContext';

export default function TransactionsPage() {
  const { transactions, members, categories, scope, profile, deleteTransaction } = useData();
  const navigate = useNavigate();
  const location = useLocation();
  const [filterMonth, setFilterMonth] = useState('');
  const [filterMember, setFilterMember] = useState('');
  const [filterKind, setFilterKind] = useState('');
  const [search, setSearch] = useState('');

  // Allow other pages (Family) to pre-focus a filter by passing it in
  // location state. We consume it once, then wipe the state so a browser
  // back/forward doesn't re-apply it.
  useEffect(() => {
    const s = location.state;
    if (!s) return;
    if (s.member) setFilterMember(s.member);
    if (s.month) setFilterMonth(s.month);
    navigate(location.pathname, { replace: true, state: null });
  }, [location, navigate]);

  const months = useMemo(() => availableMonths(transactions), [transactions]);
  const categoriesById = useMemo(() => Object.fromEntries(categories.map((c) => [c.id, c])), [categories]);

  const list = useMemo(() => {
    let l = inScope(transactions, scope, profile)
      .slice()
      .sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    if (filterMonth) l = l.filter((t) => monthKey(t.date) === filterMonth);
    if (filterMember) l = l.filter((t) => t.member === filterMember);
    if (filterKind === 'Income') l = l.filter((t) => t.type === 'Income');
    else if (filterKind) l = l.filter((t) => t.necessity === filterKind && t.type !== 'Income');
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      l = l.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          (t.merchant || '').toLowerCase().includes(q) ||
          (t.providerType || '').toLowerCase().includes(q)
      );
    }
    return l;
  }, [transactions, scope, profile, filterMonth, filterMember, filterKind, search]);

  function onEdit(txn) {
    navigate('/add', { state: { txn } });
  }

  return (
    <section>
      <PageHeader title="Transactions" subtitle={`${list.length} transaction${list.length === 1 ? '' : 's'}`}>
        <input
          type="search"
          placeholder="Search name, merchant…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <MonthSelect months={months} value={filterMonth} onChange={setFilterMonth} includeAll />
        <Select value={filterMember} onChange={(e) => setFilterMember(e.target.value)} placeholder="Everyone">
          {members.map((m) => (
            <option key={m.id}>{m.name}</option>
          ))}
        </Select>
        <Select
          value={filterKind}
          onChange={(e) => setFilterKind(e.target.value)}
          placeholder="All kinds"
          options={['Need', 'Want', 'Investment', 'Debt', 'Income']}
        />
      </PageHeader>
      <Card>
        <TransactionTable
          transactions={list}
          categoriesById={categoriesById}
          onEdit={onEdit}
          onDelete={deleteTransaction}
          emptyText="No transactions match these filters."
        />
      </Card>
    </section>
  );
}
