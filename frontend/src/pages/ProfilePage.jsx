import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import {
  Avatar,
  Button,
  Card,
  Field,
  PageHeader,
  Pill,
  Select,
} from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useData } from '../context/DataContext';
import { useToast } from '../context/ToastContext';

const RELATIONS = ['Self', 'Spouse', 'Parent', 'Child', 'Sibling', 'Other'];
const AVATAR_MAX_MB = 1;

// Read a File as a data URL — the whole point of doing avatars this way is
// so we can round-trip the picture as a JSON string.
function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function ProfileForm() {
  const { user, updateProfile } = useAuth();
  const toast = useToast();
  const fileRef = useRef(null);
  const [form, setForm] = useState({
    displayName: user?.displayName || '',
    contactNumber: user?.contactNumber || '',
    avatarUrl: user?.avatarUrl || '',
  });
  const [busy, setBusy] = useState(false);

  // Re-hydrate when the user context updates (e.g. after saving).
  useEffect(() => {
    setForm({
      displayName: user?.displayName || '',
      contactNumber: user?.contactNumber || '',
      avatarUrl: user?.avatarUrl || '',
    });
  }, [user?.displayName, user?.contactNumber, user?.avatarUrl]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const dirty =
    form.displayName !== (user?.displayName || '') ||
    form.contactNumber !== (user?.contactNumber || '') ||
    form.avatarUrl !== (user?.avatarUrl || '');

  async function pickAvatar(e) {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-picking the same file
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast('Please pick an image file');
      return;
    }
    if (file.size > AVATAR_MAX_MB * 1024 * 1024) {
      toast(`Image is over ${AVATAR_MAX_MB} MB — please pick a smaller one`);
      return;
    }
    const dataUrl = await readAsDataUrl(file);
    setForm((f) => ({ ...f, avatarUrl: dataUrl }));
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await updateProfile({
        displayName: form.displayName.trim(),
        contactNumber: form.contactNumber.trim(),
        avatarUrl: form.avatarUrl || '',
      });
      toast('Profile saved');
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Your profile" pad>
      <form onSubmit={submit}>
        <div className="profile-avatar-row">
          <Avatar src={form.avatarUrl} name={form.displayName || user?.email} size="xl" />
          <div className="profile-avatar-actions">
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              onChange={pickAvatar}
              style={{ display: 'none' }}
            />
            <Button size="sm" onClick={() => fileRef.current?.click()}>
              {form.avatarUrl ? 'Change photo' : 'Upload photo'}
            </Button>
            {form.avatarUrl && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setForm((f) => ({ ...f, avatarUrl: '' }))}
              >
                Remove
              </Button>
            )}
            <div className="note">PNG or JPG, up to {AVATAR_MAX_MB} MB.</div>
          </div>
        </div>

        <div className="form-grid" style={{ marginTop: 16 }}>
          <Field label="Full name">
            <input
              value={form.displayName}
              onChange={set('displayName')}
              placeholder="e.g. Priya Sharma"
              required
            />
          </Field>
          <Field label="Email" hint="Login email — can't be changed here.">
            <input value={user?.email || ''} readOnly disabled />
          </Field>
          <Field label="Contact number">
            <input
              value={form.contactNumber}
              onChange={set('contactNumber')}
              placeholder="e.g. +91 98xxxxxx90"
              inputMode="tel"
            />
          </Field>
        </div>

        <div className="form-actions">
          <Button type="submit" variant="primary" disabled={busy || !dirty}>
            {busy ? 'Saving…' : 'Save changes'}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function InvitePanel() {
  const toast = useToast();
  const [invites, setInvites] = useState([]);
  const [relation, setRelation] = useState('');
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => api.auth.listInvites().then(setInvites).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  const linkFor = (token) => `${window.location.origin}/invite/${token}`;
  const pending = invites.filter((i) => !i.acceptedAt);

  async function create() {
    setBusy(true);
    try {
      const invite = await api.auth.createInvite({ email, relation });
      setEmail('');
      setRelation('');
      await load();
      await navigator.clipboard?.writeText(linkFor(invite.token)).catch(() => {});
      toast('Invite link created & copied');
    } catch (e) {
      toast(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Invite a family member" hint="they get their own login, same books">
      <div className="card-pad">
        <div className="form-grid">
          <Field label="Email (optional)">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="them@example.com"
            />
          </Field>
          <Field label="Suggested relation">
            <Select
              value={relation}
              onChange={(e) => setRelation(e.target.value)}
              placeholder="—"
              options={RELATIONS}
            />
          </Field>
        </div>
        <div className="form-actions">
          <Button variant="primary" size="sm" onClick={create} disabled={busy}>
            Create invite link
          </Button>
        </div>

        {pending.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <div className="section-label">Pending invites</div>
            {pending.map((i) => (
              <div key={i.id} className="invite-row">
                <input readOnly value={linkFor(i.token)} onFocus={(e) => e.target.select()} />
                <Button
                  size="sm"
                  onClick={() => {
                    navigator.clipboard?.writeText(linkFor(i.token));
                    toast('Copied');
                  }}
                >
                  Copy
                </Button>
              </div>
            ))}
          </div>
        )}

        <div className="note" style={{ marginTop: 10 }}>
          Share the link with a family member. Anyone who opens it can create a
          login that joins this household.
        </div>
      </div>
    </Card>
  );
}

function FamilyList() {
  const { members, profile } = useData();
  return (
    <Card title="Family members" hint={`${members.length} member${members.length === 1 ? '' : 's'}`}>
      <div className="card-pad">
        {members.length === 0 ? (
          <div className="empty">No members yet.</div>
        ) : (
          <ul className="member-mini-list">
            {members.map((m) => (
              <li key={m.id}>
                <Avatar name={m.name} size="md" />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="member-mini-name">
                    {m.name}
                    {m.name === profile && (
                      <span style={{ marginLeft: 8 }}>
                        <Pill tone="good">you</Pill>
                      </span>
                    )}
                  </div>
                  <div className="note">{m.relation || 'Household member'}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

export default function ProfilePage() {
  const { user, household, isOwner } = useAuth();

  return (
    <section>
      <PageHeader
        title="Profile"
        subtitle={`${user?.email} · ${household?.name || 'household'} · ${
          isOwner ? 'owner' : 'member'
        }`}
      />

      <div className="grid two-col">
        <ProfileForm />
        <div className="stacked">
          <FamilyList />
          {isOwner && <InvitePanel />}
        </div>
      </div>
    </section>
  );
}
