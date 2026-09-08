import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Field, PageHeader, Pill } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useData } from '../context/DataContext';

export default function SettingsPage() {
  const { user, household, isOwner } = useAuth();
  const { categories, addCategory, updateCategory, removeCategory } = useData();
  const navigate = useNavigate();
  const [newCat, setNewCat] = useState('');

  const active = categories.filter((c) => !c.archived);
  const archived = categories.filter((c) => c.archived);

  async function add(e) {
    e.preventDefault();
    const name = newCat.trim();
    if (!name) return;
    const ok = await addCategory({ name });
    if (ok) setNewCat('');
  }

  return (
    <section>
      <PageHeader title="Settings" subtitle="Your household, categories and account." />

      <Card title="Household" style={{ marginBottom: 16 }}>
        <div className="card-pad">
          <div className="setting-row">
            <span className="note">Household</span>
            <strong>{household?.name}</strong>
          </div>
          <div className="setting-row">
            <span className="note">Signed in as</span>
            <span>{user?.email} <Pill tone={isOwner ? 'good' : 'need'}>{user?.role}</Pill></span>
          </div>
          <div className="note" style={{ marginTop: 8 }}>
            Manage people and invites on the <a onClick={() => navigate('/family')} style={{ cursor: 'pointer' }}>Family</a> page,
            and accounts on the <a onClick={() => navigate('/accounts')} style={{ cursor: 'pointer' }}>Accounts</a> page.
          </div>
        </div>
      </Card>

      <Card title="Spending categories" hint="predefined + your own">
        <div className="card-pad">
          <form className="inline-form" onSubmit={add} style={{ marginBottom: 14 }}>
            <Field label="Add a category">
              <input value={newCat} onChange={(e) => setNewCat(e.target.value)} placeholder="e.g. Pets, Gym" />
            </Field>
            <Button type="submit" size="sm" variant="primary">
              Add
            </Button>
          </form>

          <div className="cat-list">
            {active.map((c) => (
              <div className="cat-chip" key={c.id}>
                <span className="sw" style={{ background: c.color }} />
                <span>{c.name}</span>
                {c.isCustom && <span className="cat-badge">custom</span>}
                <button title="Archive" onClick={() => updateCategory(c.id, { name: c.name, color: c.color, archived: true })}>
                  ⌫
                </button>
                {c.isCustom && (
                  <button title="Delete" onClick={() => confirm(`Delete ${c.name}?`) && removeCategory(c.id)}>
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>

          {archived.length > 0 && (
            <>
              <div className="section-label" style={{ marginTop: 16 }}>Archived</div>
              <div className="cat-list">
                {archived.map((c) => (
                  <div className="cat-chip archived" key={c.id}>
                    <span>{c.name}</span>
                    <button title="Restore" onClick={() => updateCategory(c.id, { name: c.name, color: c.color, archived: false })}>
                      ↺
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </Card>
    </section>
  );
}
