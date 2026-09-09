import { useLocation, useNavigate } from 'react-router-dom';
import TransactionForm from '../components/transactions/TransactionForm';
import { Card, PageHeader } from '../components/ui';
import { useData } from '../context/DataContext';

// Add or edit. Edit mode is entered by navigating here with a transaction
// (and optionally a member to prefill) in the router location state.
export default function AddTransactionPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const editingTxn = state?.txn || null;
  const prefillMember = state?.member || '';

  const { accounts, categories, members, investments, debts, profile, saveTransaction } = useData();

  async function onSave(payload) {
    const ok = await saveTransaction(editingTxn?.id, payload);
    if (ok) navigate('/transactions');
    return ok;
  }

  return (
    <section>
      <PageHeader
        title={editingTxn ? 'Edit transaction' : 'Add a transaction'}
        subtitle="A card purchase is logged the day you spend it — repayments are logged separately and reconciled automatically."
      />
      <Card pad>
        <TransactionForm
          editingTxn={editingTxn}
          accounts={accounts}
          categories={categories}
          members={members}
          investments={investments}
          debts={debts}
          defaultMember={prefillMember || profile}
          onSave={onSave}
          onCancel={editingTxn ? () => navigate('/transactions') : undefined}
        />
      </Card>
    </section>
  );
}
