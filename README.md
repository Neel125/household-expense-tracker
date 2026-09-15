# Ledger & Card

A family finance tracker: sign in, log day-to-day spending and income,
reconcile credit-card purchases against their repayments (so nothing gets
double-counted), categorise spending and budget it, track bank / debit /
cash / card balances, set savings goals, invite family to share the same
books, and see a dashboard of where the money's going.

Built as a **React (multi-page, React Router) frontend** + a **Python
FastAPI backend in an MVC layout** (controllers → services →
repositories → models), backed by **PostgreSQL** (SQLite for local dev).

## What you can do

- **Accounts & auth** — email/password login, one household per owner,
  and shareable **invite links** so family members get their own login on
  the same books.
- **Income** — recurring salary/other sources, plus one-off Income
  transactions.
- **Categories & budgets** — predefined + custom categories, a household
  monthly budget split across categories by percentage, with progress vs
  actual spend.
- **Accounts** — banks, debit cards, cash and credit cards (with the
  existing accrual/repayment reconciliation) and loans, each with a live
  balance.
- **Goals** — emergency fund, vacation, education, etc., with progress
  and manual contributions.
- **Portfolio** — FDs, RDs, SIPs, stocks and gold on one side; home, car,
  personal and consumer loans on the other. Log an SIP instalment or a
  loan EMI as a transaction and **link it to the holding**: contributions
  add themselves up, and each EMI is split into interest and principal so
  the outstanding balance comes down on its own. See
  [Portfolio](#portfolio-investments-loans-and-the-transactions-that-move-them).
- **Rewards** — Finance Coins earned for financial discipline (never for
  spending), a tracking streak, short-term challenges, levels and a
  Financial Health Score. See [Rewards and Finance Coins](#rewards-and-finance-coins).
- **Dashboard** — a plain-language insight strip, where every rupee of
  the month went (expenses vs investments vs loan payments), expense-vs-
  investment trends, a portfolio and debt snapshot, cumulative
  saved-and-invested curves, category and needs/wants breakdowns, and
  merchant-wise analysis. See [The dashboard](#the-dashboard).

## How it's put together

```
expense-tracker/
├── backend/                  FastAPI (MVC) + PostgreSQL/SQLite
│   ├── main.py                thin uvicorn entrypoint -> app.main:app
│   ├── app/
│   │   ├── main.py            application factory (middleware, routers, errors)
│   │   ├── core/              config, database engine, security (JWT/bcrypt), deps
│   │   ├── models/            SQLModel tables (Household, User, Invite, Member,
│   │   │                      Account, Category, CategoryBudget, IncomeSource,
│   │   │                      Goal, Transaction, CoinTransaction,
│   │   │                      ChallengeEnrollment, HealthSnapshot, Referral)
│   │   ├── schemas/           Pydantic request/response DTOs (camelCase on the wire)
│   │   ├── repositories/      data access (household-scoped, generic base)
│   │   ├── services/          business logic + invariants
│   │   │   ├── events.py        in-process domain event bus
│   │   │   ├── portfolio_math.py    amortisation + contribution growth
│   │   │   ├── referral_service.py  refer-a-friend codes + qualification
│   │   │   ├── portfolio_service.py holdings joined with their transactions
│   │   │   ├── reward_rules.py  the reward catalogue (coins, levels, challenges)
│   │   │   ├── coin_ledger.py   the only writer of coins
│   │   │   ├── rewards_service.py   the reward engine
│   │   │   ├── challenge_service.py challenge progress
│   │   │   ├── health_service.py    Financial Health Score
│   │   │   └── month_math.py    server-side month totals for the rules
│   │   ├── controllers/       HTTP routers (thin: parse -> service -> schema)
│   │   └── migrate_legacy.py  folds any old single-tenant data into a household
│   ├── seed.py                sample data + demo login
│   └── requirements.txt
└── frontend/                 React + Vite + React Router (multi-page)
    └── src/
        ├── main.jsx           Router + Auth/Toast providers
        ├── App.jsx            route table (public auth routes + protected app)
        ├── api/               fetch client (Bearer token) + endpoint map
        ├── context/           AuthContext, DataContext, ToastContext
        ├── components/ui/      reusable kit (Button, Card, Field, Modal, StatCard,
        │                       ProgressBar, Pill, MonthSelect, …)
        ├── components/layout/  AppLayout, Sidebar, ProtectedRoute
        ├── components/transactions/  TransactionTable, TransactionForm
        ├── components/charts/  dependency-free SVG Donut/Bar/Line charts
        ├── lib/compute.js     accrual/necessity/analytics formulas
        ├── lib/insights.js    the dashboard's plain-language observations
        ├── lib/portfolioMeta.js  investment/debt kind labels, icons, colours
        └── pages/             Dashboard, Add, Transactions, Accounts, Income,
                               Budgets, Goals, Rewards, Family, Settings, auth/
```

Authentication is real now: passwords are bcrypt-hashed, a JWT is issued
on login and required on every `/api/*` route except health, register,
login and invite-accept. The first person to register creates a
**household** and becomes its **owner**; the owner generates invite links
so family members create their own logins that join the same household.
All financial data is scoped to a household, so two households can't see
each other's books.

## Family members and their transactions

**Family Members** in the sidebar is where the household lives. Add
someone with a name, a relation (Self / Spouse / Parent / Child /
Sibling / Other) and an optional **monthly budget**, and you get a card
per person showing, for the month you pick (or all time):

- accrual expense and cash out of bank, computed with the same
  credit-card rules as the dashboard — a card purchase counts on the day
  it's made, the repayment doesn't count twice
- their Need / Want split and what they invested
- how much of their monthly budget is used, and by how much they're over
- their share of the household's spend for that month
- **Transactions** — every row they logged, editable in place — and
  **Add transaction**, which opens the form already tagged to them

Transactions reference a member by name, and the backend keeps that
honest:

- **Renaming** a member moves all of their transactions to the new name
  (and re-points your picked profile if that was you).
- **Removing** a member who has history makes you say where it goes —
  move it to another member, or leave it untagged. Untagged rows get
  their own section on the Family page so they never go missing.
- Names are unique case-insensitively, so "neel" can't quietly become a
  second person alongside "Neel".

The API behind it is `GET/POST /api/members`, `PUT /api/members/{id}`
and `DELETE /api/members/{id}?reassign_to=<name>` (omit `reassign_to` and
a delete with history is refused; pass it empty to untag). Members are a
household-scoped table; the old settings row that once held cards/loans
has been replaced by first-class **Account** records, and any pre-existing
single-tenant database is folded into one default household on first
startup (`app/migrate_legacy.py`).

## Rewards and Finance Coins

The **Rewards** page turns the tracker into something with a habit loop.
The whole design rests on one rule:

> **Reward healthy financial behaviour, never spending.**

Nothing in the catalogue scales with an amount spent. Logging an expense
is worth a single coin and is capped at 10 a day, because tracking is the
habit worth building; the real money is in behaviour:

| Behaviour | Coins |
| --- | --- |
| Log an expense | +1 (max 10/day) |
| 7 consecutive days of tracking | +20 |
| Review last month's spending | +25 |
| Stay within the monthly budget | +100 |
| Cancel an unused subscription | +100 |
| Save more than last month | +150 |
| Hold the emergency fund at target | +200 |
| Improve the health score | +25 per point, max 200 |
| Complete a challenge | +100…200 |
| Complete a financial goal | +500 |
| Refer a friend who starts tracking | +500 (they get +100) |

Coins drive a level — 🌱 Beginner, 🌿 Saver (500), 🌳 Smart Saver (2,000),
💎 Financial Pro (5,000) — and each level lists what it unlocks. There is
deliberately **nothing to redeem coins for yet**: levels, streaks and
progress are the reward, which is the right MVP for a self-hosted app
with no partners and no float to underwrite gift cards. The ledger
already carries a `REWARD_REDEMPTION` rule and supports negative rows, so
adding redemption later needs no schema change.

### The coin ledger

Coins are **never** stored as a running total on a row. `CoinTransaction`
is an append-only ledger and the balance is `SUM(amount)`:

```
kind                      amount   event_key
EXPENSE_TRACKED               +1   EXPENSE_TRACKED:txn:412
BUDGET_KEPT                 +100   BUDGET_KEPT:2026-08
SUBSCRIPTION_DROPPED        +100   SUBSCRIPTION_DROPPED:netflix:2026-08
EXPENSE_REVERSED              -1   EXPENSE_REVERSED:EXPENSE_TRACKED:txn:412
```

That buys auditability (every coin traces to the behaviour that earned
it), idempotency and reconciliation. `app/services/coin_ledger.py` is the
only module allowed to write coins, and it holds three invariants: the
ledger is the source of truth, every event pays at most once, and nothing
is ever edited or deleted. Coins belong to the **household** — the app's
tenancy boundary, one shared set of books — with the acting login
recorded on each row for attribution.

### Preventing reward farming

The obvious attack is to create and delete a ₹1 expense in a loop. Four
things close it:

- **Idempotency.** Every award carries an `event_key` with a unique index
  behind it. A retried request, a double-click or two workers all collapse
  onto the same key.
- **Reversal.** Deleting a rewarded expense writes a compensating
  negative row, so the loop nets zero. Reversals are their own rule, so
  they don't refund the daily allowance either — the loop burns through
  the cap *and* earns nothing.
- **Daily caps.** Expense logging pays at most 10 coins a day. A withheld
  award still writes a zero-coin row, so there is a record of it.
- **Burst detection.** More than 60 entries in five minutes is a script,
  not a person; awards stop and the attempt is flagged in the ledger.

A ₹0 entry earns nothing either, and editing an expense into an income
row moves the coin with it.

### Financial Health Score

A separate 0–100 score over five components — budget discipline, savings,
expense tracking, debt management, emergency fund. Every component is a
ratio the household controls (spend against *its own* budget, savings
against *its own* income), so a small income can score 90 and a big
spender can score 40. Coins are paid for **improving** the score, not for
its level. A component that can't be judged yet (no budget set, no income
recorded) is left out of the average instead of scoring zero.

### How it hangs together

The expense, goal and budget services don't know rewards exist. They
publish domain facts on an in-process event bus
(`app/services/events.py`) and the engine subscribes:

```
TransactionService ──EXPENSE_TRACKED──┐
GoalService ────────GOAL_COMPLETED────┼──▶ event bus ──▶ RewardsService
                                      │                      │
                                      └──────────────┐       ▼
                                                      Reward rule engine
                                                             │
                                                             ▼
                                                       Coin ledger
```

Handlers are registered once in `app/main.py`, dispatch synchronously on
the caller's session, and a handler that raises is logged and skipped — a
reward bug must never fail a user's save. Swapping this bus for Kafka, an
outbox table or SQS means replacing one module and nothing else.

Rules that aren't a single user action (budget kept, saved more than last
month, a dropped subscription, a finished challenge) are evaluated in one
idempotent sweep, `RewardsService.settle`, which runs lazily whenever
`GET /api/rewards` is read. In production the same method would be called
from a nightly job and behave identically, because every award is keyed.
It only pays out for the **last three complete months**, so switching the
feature on doesn't hand a household with two years of history a
five-figure windfall.

Challenge *definitions* live in code; only the fact that a household
joined one is stored, and progress is recomputed from transactions on
every read — so editing or deleting a transaction re-scores a challenge
immediately. A challenge is settled only once its window has closed, so
it can never be claimed while it could still be failed.

The API is `GET /api/rewards` (the whole page in one response, and it
settles as a side effect), `GET /api/rewards/health`,
`POST /api/rewards/review`, `POST /api/rewards/challenges/{key}/join`
and `DELETE /api/rewards/challenges/{key}`.

### Refer a friend

The one reward that pays for bringing in someone new — and the one that
needed the most care, because a referral programme that pays on sign-up
is a programme people farm.

**An invite is not a referral.** An invite adds a person to *your*
household: they share your books, so paying coins for one would be free
money for typing in an email address. A referral creates a **separate
household**, and that distinction is what makes it payable at all.

**Nothing is paid for signing up.** A referral is created `pending` and
earns nothing until the referred household behaves like a household:

| Requirement | Why |
| --- | --- |
| 10 expenses logged | one or two rows is a tyre-kick, not a user |
| on 3 separate days | the part that can't be faked in one sitting |

Days are counted from when a row was *entered*, not the date on it — so
typing ten expenses in one evening is one day of activity, not ten.
Meeting both pays the referrer **500** coins and the new household a
**100**-coin welcome bonus, both keyed on the referral id so each is paid
exactly once no matter which side's app settles first.

**What is left, and why it's acceptable.** Someone can still register a
second household with their own code — there is no identity verification
here, and pretending otherwise would be the real mistake. What that costs
them is the qualification: ten expenses across three separate days, per
fake household, before a single coin appears. A monthly ceiling of 10
rewarded referrals bounds the damage if anyone has that patience, and
hitting it writes a flag row in the ledger like every other withheld
award.

A bad code never costs someone their account: an unknown, malformed or
self-referring code attaches nothing and the sign-up proceeds. The
`/register?ref=CODE` link names the household that shared it, and the
sign-up copy is generated from the thresholds rather than repeating them,
so changing `REFERRAL_MIN_*` updates both screens.

The API is `GET /api/referrals` (your code, who you have brought in, and
how far along each of them is) and the public
`GET /api/referrals/preview/{code}`, which returns a household name and
nothing else — a code is not a way to enumerate anything worth having.
The referrer never sees a referred user's email address.

### What is deliberately not built

- **Redemption / gift cards** — non-monetary rewards first, as above.
- **Cancelled subscriptions are inferred, not self-reported** — a
  Subscriptions-category merchant billed for three straight months and
  then absent counts as cancelled. Nobody has to remember to tell the app.

## The design system

Both this app and the marketing site in `../expense-tracker-website` run
on one visual language, **Deep Teal** — a teal → mint → lime palette on a
near-black teal ground, with soft ambient colour fields behind the
content.

Everything hangs off the token block at the top of
`frontend/src/styles.css`. Components reference tokens and never a raw
hex, so re-theming the entire product — both colour schemes, every page,
every chart — is an edit to that one block.

```
--accent      #0D9488 light · #2DD4BF dark    the interactive colour
--accent-2/-3 mint, lime                      gradient + glow partners only
--grad-brand  teal → mint → lime              primary buttons, meters, the mark
--ambient     three radial fields             the light in the room
--series-1…6  teal amber lime sky violet rose categorical charts
--radius-sm/-/-lg/-xl, --shadow, --shadow-lg, --glow, --ring, --ease
```

A few rules the system follows:

- **The brand gradient means "action".** It appears on the primary
  button, the app mark, progress meters and the active nav tick, and
  nowhere else — so it always reads as the thing to do or the thing
  moving forward.
- **Surfaces are translucent, not opaque.** The nav rail and modals blur
  what is behind them and cards carry a faint brand wash, which is what
  lets the ambient field show through instead of being punched out.
- **Colour carries meaning, text stays legible.** Insight tiles and pills
  put the verdict in a border or a wash and leave the text at full
  contrast, rather than colour-coding sentences into unreadability.
- **Type**: Plus Jakarta Sans throughout, JetBrains Mono for every
  figure. Currency is tabular and never wraps.
- **Motion** is 160–350ms on `--ease`, and the whole system collapses to
  near-zero under `prefers-reduced-motion`.

Icons are a small inline-SVG set in `components/ui/Icon.jsx` — about a
dozen 24×24 stroke paths, which costs less than the bundle and licence
care an icon package needs. Add one by adding a path to its map.

Light mode is a full peer, not an afterthought: the same tokens with a
mint-tinted ground, and the dark values declared twice so an explicit
`data-theme` wins in both directions.

## The dashboard

Laid out as a story rather than a wall of charts — each section answers
one question, in this order:

1. **At a glance** — net worth, income, spent, invested, savings rate.
2. **Insights** — a strip of one-line observations, each generated only
   when it applies (`frontend/src/lib/insights.js`). A household with no
   loans never sees an EMI tile rather than one reading "0%". The
   thresholds behind the wording — 20% savings, 15% invested, 40% EMI
   ceiling — are collected in one exported `TARGETS` object.
3. **Where the money went** — the month's outflow as one stacked bar:
   expenses, investments, loan payments, and whatever is left of income.
   These decompose the accrual total exactly (`accrual = Expense +
   Investment + Loan`), which is why a bar is the right shape for it — the
   parts really do add up to the whole. Beside it, the same three series
   over six months, so you can see whether the investment share is
   growing.
4. **Building wealth** — portfolio value against what was put in, an
   allocation donut by asset class, and cumulative *net saved* vs
   *invested* over a year. The cumulative curves are the one place the
   dashboard shows a trend rather than a snapshot: the shape answers "are
   we putting money away faster than we used to?".
5. **What you owe** — loan balances with payoff progress, and what the
   logged EMIs actually bought: principal vs interest, split by
   [the portfolio amortisation](#portfolio-investments-loans-and-the-transactions-that-move-them).
6. **Spending detail** — category donut, ranked categories with their
   change, needs vs wants.
7. **Month over month** and **merchant analysis**.

### Two rules the numbers follow

- **Like-for-like comparison.** A month in progress is compared against
  the *same day range* of the month before. Comparing nine days against a
  full month made every category look like it had collapsed, and turned
  every insight built on the comparison into a false alarm. Card hints say
  what the baseline is ("vs 1–9 Aug").
- **A budget is a spending envelope.** Budget usage is measured against
  day-to-day expenses only. Counting an SIP instalment or a loan
  prepayment as overspend flagged the household's *best* months as its
  worst.

Charts are still dependency-free SVG (`components/charts/`): `DonutChart`,
`BarChart` and `LineChart`, plus a `StackedBar` in the UI kit. They draw
at 1:1 with their container so labels stay ~10px at any width.

## Portfolio: investments, loans and the transactions that move them

The Portfolio page holds two lists — investments (FD, RD, SIP, mutual
funds, stocks, bonds, gold, PPF/EPF) and debts (home, car, personal,
consumer, education, business loans, credit-card debt). Each can be
maintained by hand, but the point is not to have to.

**Link a transaction to a holding and the holding keeps itself up to
date.** On the Add Transaction form, an `Investment` row gets an *Adds to
investment* picker and a `Loan` row gets a *Pays down loan* picker:

- **Investment contributions add up.** Every linked `Investment`
  transaction counts toward the holding's invested total. Where an
  expected return is set, each contribution is also grown from its own
  date to today, which gives a projected value — useful for an RD or FD,
  where the maturity value is just arithmetic, and a rough guide for a
  SIP until you enter the real number. Type a **current value** and that
  wins; leave it at 0 and the projection is shown, labelled as such.
- **Loan EMIs are split into interest and principal.** Interest is
  charged on the balance outstanding at the time of the payment, for the
  time since the previous one; whatever the payment covers beyond that
  reduces the principal. So a regular EMI on a ₹31.6L home loan at 8.6%
  splits roughly ₹22,500 interest / ₹19,500 principal, while a
  part-prepayment made three days after an EMI accrues almost no interest
  and is nearly all principal. **EMI split** on each loan shows the
  per-payment breakdown and the running balance.

### The two figures you still type in

`Opening invested` and `Opening outstanding` are the balances **tracking
started from** — money that went in, or debt that was run up, before you
began logging transactions against the holding. Linked transactions stack
on top of those, and both halves are always shown separately (*"6 logged
contributions · ₹48,000 on top of ₹40,000 opening"*), so if you
accidentally count the same instalment twice you can see it rather than
having to trust a single mystery total.

### Derived, not stored

Nothing about a linked holding is written to the database. `contributed`,
`totalInvested`, `projectedValue`, `outstandingNow`, `principalRepaid`
and `interestPaid` are all recomputed from the transactions on every read
(`app/services/portfolio_math.py`).

The alternative — adjusting a stored balance on each write — needs a
per-transaction record of what was applied so an edit or a delete can be
undone, and *still* gets the split wrong when a payment is back-dated,
because the interest depends on the balance at that moment. Replaying the
payments in date order is the only way to be right about both, and it
self-heals: correct a transaction's amount or date, or delete it, and
every figure downstream is right on the next read. Two nullable columns
on `transaction` (`investment_id`, `debt_id`) are the entire schema change.

The read model is also the authority on when a loan is **closed**, so a
loan paid off by its final EMI earns the same payoff coins as one marked
settled by hand (₹1,000 for a home loan, 500 for a car loan, 100 for the
rest).

A link only counts for the transaction type it belongs to: re-type an EMI
as an expense and it stops paying the loan down; type it back and it
resumes. Links are checked against the household on write, so one
household's EMI can never touch another's loan.

The API is `GET /api/investments` and `GET /api/debts` (both already
carry the derived figures), `GET /api/investments/{id}` for a holding
with its contributions, and `GET /api/debts/{id}/schedule` for the
interest/principal split of every EMI.

## The core idea: credit card expense vs. repayment

A credit card purchase is logged as an expense the day you make it
(`Accrual Expense`), no matter how you paid. The repayment you make
later is a *different kind of thing* — cash leaving your bank account —
so it's excluded from the accrual/necessity totals and only shows up in
`Cash Outflow`. The **Credit Cards & Loans** page turns this into a
running balance per card: `Opening Balance + Spend to Date − Repaid to
Date = Current Outstanding`. All of this logic lives in one place,
`frontend/src/lib/compute.js` — read that file if you want to see
exactly how every number on the dashboard is derived.

## Running it locally

You need Python 3.10+ and Node 18+.

**1. Backend**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py            # loads sample data + a demo login — safe to skip for a blank start
uvicorn main:app --reload --port 8000
```

The API is now at `http://127.0.0.1:8000` (check `http://127.0.0.1:8000/api/health`).

By default it uses a local SQLite file. To use Postgres, set
`DATABASE_URL=postgresql://user:pass@host:5432/db` before starting.

After `python seed.py` you can sign in with **`demo@ledger.app` /
`demo1234`**. Otherwise open the app and **Create a household** to
register your own owner login.

**2. Frontend** (in a second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. In dev, Vite proxies `/api/*` calls to the
backend on port 8000 (see `frontend/vite.config.js`), so there's no CORS
to think about.

## Running it with Docker

If you'd rather not install Python and Node, `docker compose` builds the
frontend and runs the single-process setup described below:

```bash
docker compose up --build
```

Open `http://127.0.0.1:8000` — one container serves both the UI and the
API. `docker compose down` stops it; the database survives, because the
SQLite file lives on a named volume (`ledger-data`) rather than inside
the container. Use `docker compose down -v` to throw the data away too.

To start with the sample September 2026 data instead of an empty app, set
`SEED_DATA: "true"` in `docker-compose.yml` before the first `up` (or run
`docker compose exec app python seed.py` at any time — it does nothing if
you already have transactions).

The other knobs are `docker-compose.yml` environment entries:
`DATABASE_URL` (point it at Postgres for heavier use), `ALLOWED_ORIGINS`,
and `PORT`. Note the image builds the frontend with no `VITE_API_URL`, so
`/api` stays same-origin — if you want the split deploy below, build the
frontend outside Docker.

## Deploying it for real

**Simplest option — one process serves everything.** Build the frontend,
and the FastAPI app will serve the compiled files itself:

```bash
cd frontend && npm run build       # writes frontend/dist
cd ../backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

Now `http://<your-server>:8000` serves the whole app — API and UI — from
one process. Put this behind a reverse proxy (Caddy, nginx) for TLS, or
run it on a platform like Railway/Render/Fly.io/a VPS with a process
manager (systemd, pm2, or `gunicorn -k uvicorn.workers.UvicornWorker`).

### Render (free instances)

`render.yaml` deploys a **free** web service (the Docker image: UI + API)
and a **free** Postgres 16 database. No card is required on the Hobby
workspace, but free Postgres **expires after 30 days** and has **no
backups** — keep `docker compose` running locally as the real copy.

1. Commit and push this repo to GitHub (Render only builds what is on
   the branch you connect).
2. [Render Dashboard](https://dashboard.render.com) → **New** →
   **Blueprint**. Connect the repo. Confirm both resources show plan
   **Free**, then apply.
3. Wait until `ledger-and-card` is Live. First request can take ~1
   minute while the free instance wakes. Open the URL on the service
   page (`https://ledger-and-card.onrender.com`).
4. Copy local Docker Compose data onto Render:

```bash
sudo apt install -y postgresql-client   # once, for psql
./scripts/dump-local-db.sh
RENDER_DATABASE_URL='postgresql://USER:PASS@HOST/ledger?sslmode=require' \
  ./scripts/restore-to-render.sh
```

The External connection string is on **ledger-db → Info**. Then
**Manual Deploy → Restart** the web service.

Free web services sleep after 15 minutes idle. Free Postgres is 1 GB,
one per workspace, and is deleted if you do not upgrade within 14 days
after the 30-day expiry. Do **not** run `docker compose down -v` locally.

**Split option** — deploy `frontend/dist` to a static host (Vercel,
Netlify, Cloudflare Pages) and the backend anywhere that runs Python
(Railway, Render, a VPS). Set `VITE_API_URL` (an `.env` file in
`frontend/`, e.g. `VITE_API_URL=https://api.yourdomain.com`) before
building the frontend, and set `ALLOWED_ORIGINS` on the backend to your
frontend's real origin (comma-separated if more than one) — the default
is `*` (open), which is fine for local use but not for a public deploy.

**The database.** For local dev, `backend/expense_tracker.db` is a single
SQLite file — back it up like any file. For real/multi-user use, point
`DATABASE_URL` (read in `backend/app/core/config.py`) at Postgres —
SQLModel/SQLAlchemy uses `postgresql://user:pass@host/db` with no code
changes; `psycopg2-binary` is already in `requirements.txt`. The Docker
compose file provisions Postgres for you.

## Authentication & invites

Passwords are bcrypt-hashed (`app/core/security.py`) and a JWT is issued
on login and sent as `Authorization: Bearer <token>` on every request
(`frontend/src/api/client.js`). The token is verified by the
`get_current_user` dependency (`app/core/deps.py`), which also resolves
the caller's household so every query is scoped to it.

- **Register** creates a household, seeds its default categories, and
  makes the registrant its **owner**.
- **Invite** (owner only) mints a single-use link `/invite/<token>`;
  share it however you like (no email is sent). Opening it lets someone
  create a login that joins your household.
- Set a strong **`JWT_SECRET`** env var in any real deployment — the
  default is a placeholder only.

## Extending it

- **More members**: the Family Members page. **More cards/loans**: the
  Settings page. No code changes needed for either.
- **New necessity categories or transaction types**: edit the `<option>`
  lists in `frontend/src/components/AddTransaction.jsx` and the matching
  logic in `frontend/src/lib/compute.js`.
- **New investment or debt kinds**: add the string to
  `INVESTMENT_KINDS` / `DEBT_KINDS` in `backend/app/models/` and to the
  matching registry at the top of `frontend/src/pages/PortfolioPage.jsx`.
  The linking, amortisation and projection are kind-agnostic.
- **New reward rules**: add a `Rule` to `RULES` in
  `backend/app/services/reward_rules.py` (that also feeds the "how coins
  are earned" table in the UI, so the two can't disagree), then award it
  from `RewardsService` with a fresh `event_key`. **New challenges**: add
  a `Challenge` there plus an evaluator in `challenge_service.py` —
  nothing else needs to change.
- **Charts**: `DonutChart.jsx`, `BarChart.jsx` and `LineChart.jsx` in
  `frontend/src/components/charts/` are small, dependency-free SVG
  components — extend them directly rather than pulling in a charting
  library. Series colours come from `--series-1` … `--series-6` in
  `styles.css`; add a `--series-7` there before using one.
- **New dashboard insights**: add a builder to
  `frontend/src/lib/insights.js` and list it in `buildInsights`. Return
  `null` when the insight doesn't apply — the strip renders only what
  comes back, and the page shows the first six.
- **Real-time sync between browsers**: the app reads the API once when it
  loads and re-reads after each change you make, so a second browser
  won't pick up your entries until it's reloaded. If you want live sync,
  add a Server-Sent-Events or WebSocket endpoint on the backend and have
  `refresh()` in `App.jsx` fire on its messages — better than putting an
  interval back.
