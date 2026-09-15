import { useState } from 'react';
import { GameCard, PuzzleModal, QuizModal, SpinModal } from '../components/games/GamesPanel';
import { Button, Card, EmptyState, PageHeader, Pill, ProgressBar, SegmentedControl } from '../components/ui';
import { useData } from '../context/DataContext';
import { monthLabel, shortDate } from '../lib/format';

const fmtCoins = (n) => Math.round(Number(n) || 0).toLocaleString('en-IN');

const TABS = [
  { value: 'play', label: 'Play' },
  { value: 'challenges', label: 'Challenges' },
  { value: 'health', label: 'Health' },
  { value: 'ledger', label: 'Ledger' },
];

function scoreTone(score) {
  if (score >= 75) return 'good';
  if (score >= 50) return 'warning';
  return 'debt';
}

function CoinBadge({ coins }) {
  return (
    <span className="coin-badge">
      <span aria-hidden="true">🪙</span>
      {fmtCoins(coins)}
    </span>
  );
}

function ScoreRing({ score }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, Number(score) || 0));
  const off = c * (1 - pct / 100);
  return (
    <svg className={'score-ring tone-' + scoreTone(pct)} viewBox="0 0 72 72" aria-hidden="true" fill="none">
      <circle className="score-ring-track" cx="36" cy="36" r={r} fill="none" strokeWidth="7" />
      <circle
        className="score-ring-fill"
        cx="36"
        cy="36"
        r={r}
        fill="none"
        strokeWidth="7"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={off}
        transform="rotate(-90 36 36)"
      />
      <text x="36" y="41" textAnchor="middle">{Math.round(pct)}</text>
    </svg>
  );
}

function Hero({ balance, earnedThisMonth, level, nextLevel, streak, health }) {
  const span = nextLevel ? nextLevel.minCoins - level.minCoins : 0;
  const pct = span > 0 ? ((balance - level.minCoins) / span) * 100 : 100;
  return (
    <div className="rewards-hero">
      <div className="rewards-hero-main">
        <div className="rewards-kicker">Finance coins</div>
        <div className="rewards-balance num">{fmtCoins(balance)}</div>
        <div className="note">+{fmtCoins(earnedThisMonth)} earned this month</div>
        <div className="rewards-level">
          <div className="level-icon" aria-hidden="true">{level.icon}</div>
          <div className="rewards-level-copy">
            <div className="level-name">{level.name}</div>
            <ProgressBar pct={pct} over={false} />
            <div className="note">
              {nextLevel
                ? `${fmtCoins(nextLevel.coinsToGo)} to ${nextLevel.name}`
                : 'Top level reached'}
            </div>
          </div>
        </div>
        <ul className="perk-list">
          {level.perks.slice(0, 3).map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </div>
      <div className="rewards-hero-aside">
        <div className="rewards-aside-stat">
          <ScoreRing score={health.score} />
          <div>
            <div className="label">Health</div>
            <div className="aside-val">{health.score}/100</div>
            <div className="note">{monthLabel(health.month)}</div>
          </div>
        </div>
        <div className="rewards-aside-stat">
          <div className="streak-mark" aria-hidden="true">🔥</div>
          <div>
            <div className="label">Streak</div>
            <div className="aside-val">{streak.days} day{streak.days === 1 ? '' : 's'}</div>
            <div className="note">
              best {streak.best}
              {streak.loggedToday ? ' · logged today' : ' · nothing today'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function HealthPanel({ health }) {
  const judged = health.components.filter((c) => c.score !== null);
  const unjudged = health.components.filter((c) => c.score === null);
  return (
    <Card title="Score breakdown" hint={monthLabel(health.month)} pad>
      <div className="health-list">
        {judged.map((c) => (
          <div className="health-row" key={c.key}>
            <div className="health-label">
              {c.label}
              <div className="note">{c.detail}</div>
            </div>
            <ProgressBar pct={c.score} over={c.score < 50} />
            <div className="health-score num">{c.score}</div>
          </div>
        ))}
      </div>
      {unjudged.length > 0 && (
        <div className="note" style={{ marginTop: 12 }}>
          Not scored yet: {unjudged.map((c) => c.label.toLowerCase()).join(', ')}.
        </div>
      )}
    </Card>
  );
}

const CHALLENGE_TONE = { completed: 'good', missed: 'debt', active: 'need' };

function ChallengeCard({ challenge, onJoin, onLeave }) {
  const { key, title, description, icon, coins, status, pct, caption, eligible, period } = challenge;
  return (
    <div className={'card card-pad challenge-card' + (status === 'completed' ? ' won' : '')}>
      <div className="challenge-head">
        <div className="challenge-icon" aria-hidden="true">{icon}</div>
        <div className="challenge-copy">
          <div className="challenge-title">{title}</div>
          <div className="note">{period === 'week' ? 'This week' : 'This month'}</div>
        </div>
        <CoinBadge coins={coins} />
      </div>
      <p className="challenge-desc">{description}</p>
      <ProgressBar pct={pct} over={false} />
      <div className="challenge-foot">
        <span className="note">{caption}</span>
        {status !== 'available' && <Pill tone={CHALLENGE_TONE[status]}>{status}</Pill>}
      </div>
      {!eligible && (
        <div className="note">Needs a category or a previous month before it can be scored.</div>
      )}
      <div className="challenge-actions">
        {status === 'available' ? (
          <Button size="sm" variant="primary" onClick={() => onJoin(key, title)} disabled={!eligible}>
            Join
          </Button>
        ) : status === 'active' ? (
          <Button size="sm" variant="ghost" onClick={() => onLeave(key)}>
            Leave
          </Button>
        ) : (
          <span className="note">Settled — a new round opens next {period}.</span>
        )}
      </div>
    </div>
  );
}

function EarnPanel({ catalog, capRemaining, reviewMonth, reviewClaimed, onReview }) {
  return (
    <Card title="How coins are earned" hint="never by spending more" pad>
      <div className="earn-grid">
        {catalog.map((r) => (
          <div className="earn-chip" key={r.kind}>
            <span>
              {r.label}
              {r.dailyCap ? <span className="note"> · max {r.dailyCap}/day</span> : null}
            </span>
            <span className="num earn-coins">+{fmtCoins(r.coins)}</span>
          </div>
        ))}
        <div className="earn-chip">
          <span>Daily quiz, puzzle or wheel<span className="note"> · once a day each</span></span>
          <span className="num earn-coins">+10–100</span>
        </div>
        <div className="earn-chip">
          <span>Challenge completed</span>
          <span className="num earn-coins">+80–200</span>
        </div>
        <div className="earn-chip">
          <span>Health improved<span className="note"> · 25/pt, max 200</span></span>
          <span className="num earn-coins">+25–200</span>
        </div>
      </div>
      <div className="review-row">
        <div>
          <div className="review-title">Review {monthLabel(reviewMonth)}</div>
          <div className="note">
            {capRemaining > 0
              ? `${capRemaining} logging coin(s) left today.`
              : 'Daily logging cap is used up.'}
          </div>
        </div>
        <Button size="sm" variant={reviewClaimed ? 'ghost' : 'primary'} disabled={reviewClaimed} onClick={() => onReview(reviewMonth)}>
          {reviewClaimed ? 'Logged' : 'Mark reviewed +25'}
        </Button>
      </div>
    </Card>
  );
}

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

function LedgerCard({ history, breakdown }) {
  return (
    <Card title="Coin ledger" hint="balance is the sum of these rows" pad>
      {breakdown.length > 0 && (
        <div className="ledger-breakdown">
          {breakdown.map((b) => (
            <div className="ledger-pill" key={b.kind}>
              <span className="note">{b.label}</span>
              <span className={'num ' + (b.coins < 0 ? 'amount-over' : 'earn-coins')}>
                {b.coins > 0 ? '+' : ''}
                {fmtCoins(b.coins)}
              </span>
            </div>
          ))}
        </div>
      )}
      {history.length === 0 ? (
        <EmptyState>No coins yet — log an expense to start.</EmptyState>
      ) : (
        <div className="table-wrap rewards-ledger-table">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>What</th>
                <th style={{ textAlign: 'right' }}>Coins</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={row.id}>
                  <td className="cell-date note">{shortDate(row.createdAt.slice(0, 10))}</td>
                  <td>{row.note || row.label}</td>
                  <td
                    className={
                      'num cell-actions ' +
                      (row.amount > 0 ? 'amount-income' : row.amount < 0 ? 'amount-over' : 'note')
                    }
                  >
                    {row.amount > 0 ? '+' : ''}
                    {row.amount === 0 ? '—' : fmtCoins(row.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export default function RewardsPage() {
  const { rewards, referrals, loading, joinChallenge, leaveChallenge, recordReview, playQuiz, playPuzzle, spinWheel } =
    useData();
  const [game, setGame] = useState(null);
  const [tab, setTab] = useState('play');

  if (!rewards) {
    return (
      <section>
        <PageHeader title="Rewards" subtitle="Coins for financial discipline." />
        <Card pad>
          <EmptyState>{loading ? 'Loading your coins…' : 'Rewards are unavailable right now.'}</EmptyState>
        </Card>
      </section>
    );
  }

  const { balance, earnedThisMonth, level, nextLevel, streak, health, challenges, games, catalog } = rewards;

  return (
    <section className="rewards-page">
      <PageHeader
        title="Rewards"
        subtitle="Coins for staying in budget, saving, and finishing goals — never for spending more."
      />

      <Hero
        balance={balance}
        earnedThisMonth={earnedThisMonth}
        level={level}
        nextLevel={nextLevel}
        streak={streak}
        health={health}
      />

      <div className="rewards-tabs">
        <SegmentedControl value={tab} onChange={setTab} options={TABS} />
      </div>

      {tab === 'play' && (
        <div className="grid card-grid challenge-grid">
          {(games || []).map((g) => (
            <GameCard key={g.key} game={g} onPlay={() => setGame(g.key)} />
          ))}
        </div>
      )}

      {tab === 'challenges' && (
        <div className="grid card-grid challenge-grid">
          {challenges.map((c) => (
            <ChallengeCard key={c.key} challenge={c} onJoin={joinChallenge} onLeave={leaveChallenge} />
          ))}
        </div>
      )}

      {tab === 'health' && (
        <div className="grid two-col-even">
          <HealthPanel health={health} />
          <EarnPanel
            catalog={catalog}
            capRemaining={rewards.dailyCapRemaining}
            reviewMonth={rewards.reviewMonth}
            reviewClaimed={rewards.reviewClaimed}
            onReview={recordReview}
          />
        </div>
      )}

      {tab === 'ledger' && (
        <div className="grid two-col-even">
          <LedgerCard history={rewards.history} breakdown={rewards.breakdown} />
          <ReferCard referrals={referrals} />
        </div>
      )}

      {game === 'GAME_QUIZ' && (
        <QuizModal onClose={() => setGame(null)} onSubmit={playQuiz} />
      )}
      {game === 'GAME_PUZZLE' && (
        <PuzzleModal onClose={() => setGame(null)} onSubmit={playPuzzle} />
      )}
      {game === 'GAME_SPIN' && (
        <SpinModal onClose={() => setGame(null)} onSpin={spinWheel} />
      )}
    </section>
  );
}
