import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AuthShell from './AuthShell';
import { Button, Field } from '../../components/ui';
import { useAuth } from '../../context/AuthContext';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ displayName: '', householdName: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await register({
        email: form.email.trim(),
        password: form.password,
        displayName: form.displayName.trim(),
        householdName: form.householdName.trim(),
      });
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your household"
      subtitle="You'll be the owner and can invite family later."
      footer={
        <span className="note">
          Already have an account? <Link to="/login">Sign in</Link>
        </span>
      }
    >
      <form onSubmit={submit}>
        <Field label="Your name">
          <input type="text" value={form.displayName} onChange={set('displayName')} required autoFocus />
        </Field>
        <Field label="Household name" hint="e.g. The Sharma family. Leave blank for a default.">
          <input type="text" value={form.householdName} onChange={set('householdName')} placeholder="optional" />
        </Field>
        <Field label="Email">
          <input type="email" value={form.email} onChange={set('email')} required />
        </Field>
        <Field label="Password" hint="At least 6 characters.">
          <input type="password" value={form.password} onChange={set('password')} required minLength={6} />
        </Field>
        {error && <div className="form-error">{error}</div>}
        <Button type="submit" variant="primary" disabled={busy} className="btn-block">
          {busy ? 'Creating…' : 'Create household'}
        </Button>
      </form>
    </AuthShell>
  );
}
