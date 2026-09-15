import { useState } from 'react';
import { Button, Card, EmptyState, Pill, ProgressBar } from '../ui';

const fmtCoins = (n) => (Math.round(Number(n) || 0)).toLocaleString('en-IN');

// Refer a friend. Lives on the Profile page, next to the other things
// that are about *you and your household* rather than about the money —
// and a share code is something you reach for when you're already
// looking at your own account.
//
// The copy leads with what has to happen before anyone is paid: a
// referral programme that pays on sign-up is one people try to game, and
// one that says so up front is one they don't.
function ReferCard({ referrals }) {
  const [copied, setCopied] = useState('');

  if (!referrals) {
    return (
      <Card title="Refer a friend" pad>
        <EmptyState>Referrals are unavailable right now.</EmptyState>
      </Card>
    );
  }

  const link = `${window.location.origin}${referrals.sharePath}?ref=${referrals.code}`;

  async function copy(what, value) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(what);
      setTimeout(() => setCopied(''), 1800);
    } catch {
      setCopied('');
    }
  }

  return (
    <Card
      title="Refer a friend"
      hint={`+${fmtCoins(referrals.rewardCoins)} each`}
      actions={referrals.qualifiedCount > 0 ? <Pill tone="good">{referrals.qualifiedCount} joined</Pill> : null}
      pad
    >
      <p className="note" style={{ margin: '0 0 12px' }}>
        They must log {referrals.neededExpenses} expenses on {referrals.neededDays} days.
        Sign-up itself pays nothing. Cap {referrals.monthlyCap}/month.
      </p>
      <div className="refer-code">
        <span className="num">{referrals.code}</span>
        <Button size="sm" variant="ghost" onClick={() => copy('code', referrals.code)}>
          {copied === 'code' ? 'Copied' : 'Copy code'}
        </Button>
        <Button size="sm" variant="primary" onClick={() => copy('link', link)}>
          {copied === 'link' ? 'Link copied' : 'Copy link'}
        </Button>
      </div>
      <div className="mini-stats mini-stats-3" style={{ marginTop: 14, marginBottom: 0 }}>
        <div>
          <div className="note">Joined</div>
          <div className="num mom-val">{referrals.qualifiedCount}</div>
        </div>
        <div>
          <div className="note">Settling in</div>
          <div className="num mom-val">{referrals.pendingCount}</div>
        </div>
        <div>
          <div className="note">Earned</div>
          <div className="num mom-val up-good">{fmtCoins(referrals.coinsEarned)}</div>
        </div>
      </div>
      {referrals.referrals.length > 0 && (
        <div className="rank-list" style={{ marginTop: 14 }}>
          {referrals.referrals.map((r) => (
            <div key={r.id} className="refer-row">
              <div className="refer-row-head">
                <span>{r.name}</span>
                {r.status === 'qualified' ? (
                  <Pill tone="good">+{fmtCoins(referrals.rewardCoins)}</Pill>
                ) : (
                  <span className="note">
                    {r.expenses}/{r.neededExpenses} · {r.activeDays}/{r.neededDays}d
                  </span>
                )}
              </div>
              <ProgressBar pct={r.pct} over={false} />
            </div>
          ))}
        </div>
      )}
      {referrals.joinedThrough && (
        <div className="takeaway">
          You joined through <strong>{referrals.joinedThrough.referrerName}</strong>.
          {referrals.joinedThrough.status === 'qualified'
            ? ` Welcome bonus of ${fmtCoins(referrals.joinedThrough.welcomeCoins)} is in the ledger.`
            : ` ${referrals.joinedThrough.expenses}/${referrals.joinedThrough.neededExpenses} expenses so far.`}
        </div>
      )}
    </Card>
  );
}

export default ReferCard;
