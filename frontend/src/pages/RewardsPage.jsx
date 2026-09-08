import { Button, Card, EmptyState, PageHeader, Pill, ProgressBar } from '../components/ui';
import { monthLabel, shortDate } from '../lib/format';
import { useData } from '../context/DataContext';

const fmtCoins = (n) => (Math.round(Number(n) || 0)).toLocaleString('en-IN');

// Health components read better with a tone than a bare number.
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

function HealthCard({ health }) {
  const judged = health.components.filter((c) => c.score !== null);
  const unjudged = health.components.filter((c) => c.score === null);
  return (
    <div className="card card-pad">
      <div className="card-head">
        <div className="card-title">
          Financial health <span className="hint">· {monthLabel(health.month)}</span>
        </div>
        <Pill tone={scoreTone(health.score)}>{health.score}/100</Pill>
      </div>
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
          Not scored yet: {unjudged.map((c) => c.label.toLowerCase()).join(', ')} —{' '}
          {unjudged[0].detail.toLowerCase()}.
        </div>
      )}
      <div className="note" style={{ marginTop: 12 }}>
        Coins are paid for <strong>improving</strong> this score, not for its level — so a
        smaller income is never a disadvantage.
      </div>
    </div>
  );
}

function LevelCard({ level, nextLevel, balance }) {
  const span = nextLevel ? nextLevel.minCoins - level.minCoins : 0;
  const pct = span > 0 ? ((balance - level.minCoins) / span) * 100 : 100;
  return (
    <div className="card card-pad">
      <div className="card-head">
        <div className="card-title">Level</div>
        <span className="note">Level {level.number} of 4</span>
      </div>
      <div className="level-head">
        <div className="level-icon" aria-hidden="true">
          {level.icon}
        </div>
        <div>
          <div className="level-name">{level.name}</div>
          <div className="note">{fmtCoins(balance)} coins earned</div>
        </div>
      </div>
      <div style={{ marginTop: 14 }}>
        <ProgressBar pct={pct} over={false} />
        <div className="note" style={{ marginTop: 6 }}>
          {nextLevel
            ? `${fmtCoins(nextLevel.coinsToGo)} coins to ${nextLevel.name} ${nextLevel.icon}`
            : 'Top level reached.'}
        </div>
      </div>
      <div className="level-perks">
        <div className="note" style={{ fontWeight: 600, marginBottom: 6 }}>
          Unlocked
        </div>
        <ul className="perk-list">
          {level.perks.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
        {nextLevel && (
          <>
            <div className="note" style={{ fontWeight: 600, margin: '10px 0 6px' }}>
              Unlocks at {nextLevel.name}
            </div>
            <ul className="perk-list locked">
              {nextLevel.perks.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

const CHALLENGE_TONE = { completed: 'good', missed: 'debt', active: 'need' };

function ChallengeCard({ challenge, onJoin, onLeave }) {
  const { key, title, description, icon, coins, status, pct, caption, eligible, period } = challenge;
  return (
    <div className={'card card-pad challenge-card' + (status === 'completed' ? ' won' : '')}>
      <div className="challenge-head">
        <div className="challenge-icon" aria-hidden="true">
          {icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="challenge-title">{title}</div>
          <div className="note">{period === 'week' ? 'This week' : 'This month'}</div>
        </div>
        <CoinBadge coins={coins} />
      </div>
      <div className="note" style={{ marginTop: 10 }}>
        {description}
      </div>
      <div style={{ marginTop: 12 }}>
        <ProgressBar pct={pct} over={false} />
        <div className="challenge-foot">
          <span className="note">{caption}</span>
          {status !== 'available' && <Pill tone={CHALLENGE_TONE[status]}>{status}</Pill>}
        </div>
      </div>
      {!eligible && (
        <div className="note" style={{ marginTop: 8 }}>
          Can't be scored yet — this one needs a category or a previous month to compare with.
        </div>
      )}
      <div className="challenge-actions">
        {status === 'available' ? (
          <Button size="sm" variant="primary" onClick={() => onJoin(key, title)} disabled={!eligible}>
            Join challenge
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

function EarnCard({ catalog, capRemaining, reviewMonth, reviewClaimed, onReview }) {
  return (
    <div className="card card-pad">
      <div className="card-head">
        <div className="card-title">
          How coins are earned <span className="hint">· never by spending more</span>
        </div>
      </div>
      <div className="earn-list">
        {catalog.map((r) => (
          <div className="earn-row" key={r.kind}>
            <span>
              {r.label}
              {r.dailyCap ? <span className="note"> · max {r.dailyCap}/day</span> : null}
            </span>
            <span className="num earn-coins">+{fmtCoins(r.coins)}</span>
          </div>
        ))}
        <div className="earn-row">
          <span>
            Challenge completed<span className="note"> · varies</span>
          </span>
          <span className="num earn-coins">+100–200</span>
        </div>
        <div className="earn-row">
          <span>
            Financial health improved<span className="note"> · 25 per point, max 200</span>
          </span>
          <span className="num earn-coins">+25–200</span>
        </div>
      </div>
      <div className="note" style={{ marginTop: 12 }}>
        {capRemaining > 0
          ? `${capRemaining} more logging coin(s) available today.`
          : "Today's logging allowance is used up — the bigger rewards are for budget and savings behaviour."}
      </div>
      <div className="review-row">
        <div>
          <div style={{ fontWeight: 600, fontSize: 13.5 }}>Review {monthLabel(reviewMonth)}</div>
          <div className="note">Read last month's numbers on the dashboard, then log it here.</div>
        </div>
        <Button size="sm" variant={reviewClaimed ? 'ghost' : 'primary'} disabled={reviewClaimed} onClick={() => onReview(reviewMonth)}>
          {reviewClaimed ? 'Already logged' : 'Mark reviewed +25'}
        </Button>
      </div>
    </div>
  );
}

function LedgerCard({ history, breakdown }) {
  return (
    <div className="card card-pad">
      <div className="card-head">
        <div className="card-title">
          Coin ledger <span className="hint">· the balance is the sum of these rows</span>
        </div>
      </div>
      {breakdown.length > 0 && (
        <div className="earn-list" style={{ marginBottom: 14 }}>
          {breakdown.map((b) => (
            <div className="earn-row" key={b.kind}>
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
        <div className="table-wrap">
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
      <div className="note" style={{ marginTop: 12 }}>
        Rows are never edited or deleted. Deleting a rewarded expense writes a matching
        negative row, so the history always explains the balance.
      </div>
    </div>
  );
}

export default function RewardsPage() {
  const { rewards, loading, joinChallenge, leaveChallenge, recordReview } = useData();

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

  const { balance, earnedThisMonth, level, nextLevel, streak, health, challenges, catalog } = rewards;

  return (
    <section>
      <PageHeader
        title="Rewards"
        subtitle="Coins reward financial discipline — staying in budget, saving more, finishing goals. Never spending more."
      >
        <CoinBadge coins={balance} />
      </PageHeader>

      <div className="grid kpi-row">
        <div className="kpi">
          <div className="label">Coin balance</div>
          <div className="value">🪙 {fmtCoins(balance)}</div>
          <div className="foot">+{fmtCoins(earnedThisMonth)} earned this month</div>
        </div>
        <div className="kpi">
          <div className="label">Level</div>
          <div className="value">
            {level.icon} {level.name}
          </div>
          <div className="foot">
            {nextLevel ? `${fmtCoins(nextLevel.coinsToGo)} to ${nextLevel.name}` : 'Top level'}
          </div>
        </div>
        <div className="kpi">
          <div className="label">Tracking streak</div>
          <div className="value">{streak.days} day{streak.days === 1 ? '' : 's'}</div>
          <div className="foot">
            best {streak.best} · {streak.loggedToday ? 'logged today' : 'nothing logged today'}
          </div>
        </div>
        <div className="kpi">
          <div className="label">Financial health</div>
          <div className={'value tone-' + (health.score >= 75 ? 'good' : 'warning')}>
            {health.score}/100
          </div>
          <div className="foot">{monthLabel(health.month)}</div>
        </div>
      </div>

      <div className="grid two-col">
        <HealthCard health={health} />
        <LevelCard level={level} nextLevel={nextLevel} balance={balance} />
      </div>

      <div className="section-head">
        <div className="card-title">Challenges</div>
        <span className="note">Short commitments, settled once the window closes.</span>
      </div>
      <div className="grid card-grid challenge-grid">
        {challenges.map((c) => (
          <ChallengeCard key={c.key} challenge={c} onJoin={joinChallenge} onLeave={leaveChallenge} />
        ))}
      </div>

      <div className="grid two-col" style={{ marginTop: 22 }}>
        <EarnCard
          catalog={catalog}
          capRemaining={rewards.dailyCapRemaining}
          reviewMonth={rewards.reviewMonth}
          reviewClaimed={rewards.reviewClaimed}
          onReview={recordReview}
        />
        <LedgerCard history={rewards.history} breakdown={rewards.breakdown} />
      </div>
    </section>
  );
}
