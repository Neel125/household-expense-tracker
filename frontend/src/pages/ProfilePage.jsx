import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import {
  Avatar,
  Button,
  Card,
  Field,
  Modal,
  PageHeader,
  Pill,
  Select,
} from '../components/ui';
import ReferCard from '../components/rewards/ReferCard';
import { useAuth } from '../context/AuthContext';
import { useData } from '../context/DataContext';
import { useToast } from '../context/ToastContext';

const RELATIONS = ['Self', 'Spouse', 'Parent', 'Child', 'Sibling', 'Other'];

const inviteLink = (token) => `${window.location.origin}/invite/${token}`;
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

// Creating an invite is a one-off act, so it belongs in a dialog rather
// than a form sitting open on the page. The freshly minted link is shown
// *inside* the dialog: the whole point of the interaction is to walk away
// holding a link, and a clipboard write can silently fail (insecure
// origin, denied permission) — so the link is always on screen to copy by
// hand as well.
function InviteDialog({ onClose, onCreated }) {
  const toast = useToast();
  const [email, setEmail] = useState('');
  const [relation, setRelation] = useState('');
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState('');
  const [copied, setCopied] = useState(false);

  async function create(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const invite = await api.auth.createInvite({ email, relation });
      const url = inviteLink(invite.token);
      setLink(url);
      onCreated?.();
      try {
        await navigator.clipboard.writeText(url);
        setCopied(true);
      } catch {
        setCopied(false);
      }
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Invite a family member" onClose={onClose}>
      <p className="note">
        They get their own login and see the same household books. The link works once, for
        whoever opens it — share it with the person you mean.
      </p>

      {link ? (
        <>
          <div className="invite-row" style={{ marginTop: 4 }}>
            <input readOnly value={link} onFocus={(e) => e.target.select()} />
            <Button
              size="sm"
              onClick={() => {
                navigator.clipboard?.writeText(link);
                setCopied(true);
              }}
            >
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
          <div className="note" style={{ marginTop: 8 }}>
            {copied ? 'Copied to your clipboard.' : 'Select the link above to copy it.'}
          </div>
          <div className="form-actions">
            <Button variant="primary" onClick={onClose}>
              Done
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setLink('');
                setCopied(false);
                setEmail('');
                setRelation('');
              }}
            >
              Create another
            </Button>
          </div>
        </>
      ) : (
        <form onSubmit={create}>
          <Field label="Email" hint="Optional — just a reminder of who the link is for.">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="them@example.com"
              autoFocus
            />
          </Field>
          <Field label="Suggested relation" hint="They can change it when they join.">
            <Select
              value={relation}
              onChange={(e) => setRelation(e.target.value)}
              placeholder="—"
              options={RELATIONS}
            />
          </Field>
          <div className="form-actions">
            <Button type="submit" variant="primary" disabled={busy}>
              {busy ? 'Creating…' : 'Create invite link'}
            </Button>
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

// The household section: who is in it, who has been invited but hasn't
// joined yet, and the button that adds to either list. Pending invites
// live here rather than in the dialog because they are part of the
// picture of the household, not part of the act of creating one.
function FamilySection({ isOwner }) {
  const { members, profile } = useData();
  const toast = useToast();
  const [invites, setInvites] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);

  const load = useCallback(() => {
    if (!isOwner) return;
    api.auth.listInvites().then(setInvites).catch(() => {});
  }, [isOwner]);

  useEffect(() => {
    load();
  }, [load]);

  const pending = invites.filter((i) => !i.acceptedAt);

  return (
    <>
      <Card
        title="Family members"
        hint={`${members.length} member${members.length === 1 ? '' : 's'}`}
        actions={
          isOwner ? (
            <Button size="sm" variant="primary" onClick={() => setDialogOpen(true)}>
              + Invite member
            </Button>
          ) : null
        }
        pad
      >
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

        {isOwner && pending.length > 0 && (
          <div style={{ marginTop: 18 }}>
            <div className="section-label">
              Invited · {pending.length} link{pending.length === 1 ? '' : 's'} not used yet
            </div>
            {pending.map((i) => (
              <div key={i.id} className="invite-row">
                <input
                  readOnly
                  value={inviteLink(i.token)}
                  onFocus={(e) => e.target.select()}
                  aria-label={i.email ? `Invite link for ${i.email}` : 'Invite link'}
                />
                <Button
                  size="sm"
                  onClick={() => {
                    navigator.clipboard?.writeText(inviteLink(i.token));
                    toast('Copied');
                  }}
                >
                  Copy
                </Button>
              </div>
            ))}
          </div>
        )}

        {isOwner && (
          <div className="note" style={{ marginTop: 12 }}>
            Anyone who opens an invite link can create a login that joins this household and sees
            the same books.
          </div>
        )}
      </Card>

      {dialogOpen && (
        <InviteDialog onClose={() => setDialogOpen(false)} onCreated={load} />
      )}
    </>
  );
}

// Two sections: you, and your household. The refer card sits beside the
// profile form because both are about your own account — and a share
// code is something you reach for while already looking at it.
export default function ProfilePage() {
  const { user, household, isOwner } = useAuth();
  const { referrals } = useData();

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
        <ReferCard referrals={referrals} />
      </div>

      <div className="section-head">
        <div className="card-title">Your household</div>
        <span className="note">Everyone here shares the same books.</span>
      </div>
      <FamilySection isOwner={isOwner} />
    </section>
  );
}
