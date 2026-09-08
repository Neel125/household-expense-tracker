import { fmtINR, shortDate } from '../../lib/format';
import Pill from '../ui/Pill';

const TYPE_TONE = { Income: 'good', 'CC Repayment': 'debt' };

// Shared by the Transactions and Family views. showMember=false drops the
// "Who" column. A categories map (id -> {name,color}) renders category
// names; pass it from the page.
export default function TransactionTable({
  transactions,
  categoriesById = {},
  onEdit,
  onDelete,
  showMember = true,
  emptyText = 'Nothing here yet.',
}) {
  if (!transactions.length) {
    return (
      <div className="table-wrap">
        <table>
          <tbody>
            <tr>
              <td className="empty">{emptyText}</td>
            </tr>
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Entry</th>
            <th className="col-3">Category</th>
            <th className="col-2">Mode</th>
            <th className="col-3">Provider</th>
            <th className="col-1">Necessity</th>
            {showMember && <th className="col-2">Who</th>}
            <th className="num">Amount</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((t) => {
            const cat = t.categoryId ? categoriesById[t.categoryId] : null;
            const isIncome = t.type === 'Income';
            return (
              <tr key={t.id}>
                <td className="mono cell-date">
                  <span className="date-full">{t.date}</span>
                  <span className="date-short">{shortDate(t.date)}</span>
                </td>
                <td>
                  {t.name}
                  {t.merchant && <span className="note"> · {t.merchant}</span>}
                  <span className="row-tag">
                    {isIncome ? (
                      <Pill tone="good">Income</Pill>
                    ) : (
                      <Pill necessity={t.necessity} />
                    )}
                  </span>
                </td>
                <td className="col-3">{cat ? cat.name : isIncome ? '—' : <span className="note">Uncategorized</span>}</td>
                <td className="col-2">{t.paymentMode}</td>
                <td className="col-3">{t.providerType}</td>
                <td className="col-1">
                  {isIncome ? <Pill tone="good">Income</Pill> : <Pill necessity={t.necessity} />}
                </td>
                {showMember && <td className="col-2">{t.member || <span className="note">untagged</span>}</td>}
                <td className={'num' + (isIncome ? ' amount-income' : '')}>
                  {isIncome ? '+' : ''}
                  {fmtINR(t.amount)}
                </td>
                <td className="cell-actions">
                  <button className="btn btn-sm btn-ghost" onClick={() => onEdit(t)} title="Edit" aria-label="Edit">
                    <span className="act-text">Edit</span>
                    <span className="act-icon" aria-hidden="true">✎</span>
                  </button>{' '}
                  <button
                    className="btn btn-sm btn-ghost btn-danger"
                    title="Delete"
                    aria-label="Delete"
                    onClick={() => {
                      if (confirm('Delete this transaction?')) onDelete(t.id);
                    }}
                  >
                    <span className="act-text">Delete</span>
                    <span className="act-icon" aria-hidden="true">✕</span>
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
