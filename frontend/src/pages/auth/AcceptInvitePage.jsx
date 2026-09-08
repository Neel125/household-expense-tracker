import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import AuthShell from './AuthShell';
import { Button, Field } from '../../components/ui';
import { api } from '../../api';
import { useAuth } from '../../context/AuthContext';

// Landing page for an invite link (/invite/:token). Previews which
// household the token joins, then registers the visitor into it.
export default function AcceptInvitePage() {
  const { token } = useParams();
  const { acceptInvite } = useAuth();
  const navigate = useNavigate();
  const [preview, setPreview] = useState(null);
  const [form, setForm] = useState({ displayName: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  useEffect(() => {
    api.auth
      .previewInvite(token)
      .then(setPreview)
      .catch(() => setPreview({ valid: false, householdName: '' }));
  }, [token]);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await acceptInvite({
        token,
        email: form.email.trim(),
        password: form.password,
        displayName: form.displayName.trim(),
        relation: preview?.relation || '',
      });
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (preview && !preview.valid) {
    return (
      <AuthShell
        title="Invite not valid"
        subtitle="This invite link has expired or has already been used."
        footer={<Link to="/login">Go to sign in</Link>}
      >
        <div className="empty">Ask the household owner for a fresh invite link.</div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={preview ? `Join ${preview.householdName}` : 'Join a household'}
      subtitle="Create your login to share these books."
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
        <Field label="Email">
          <input type="email" value={form.email} onChange={set('email')} required />
        </Field>
        <Field label="Password" hint="At least 6 characters.">
          <input type="password" value={form.password} onChange={set('password')} required minLength={6} />
        </Field>
        {error && <div className="form-error">{error}</div>}
        <Button type="submit" variant="primary" disabled={busy || !preview} className="btn-block">
          {busy ? 'Joining…' : 'Join household'}
        </Button>
      </form>
    </AuthShell>
  );
}
