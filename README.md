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
- **Dashboard analytics** — category breakdown, income vs expenses,
  savings rate, month-over-month comparison, highest spending categories,
  and merchant-wise analysis.

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
│   │   │                      Goal, Transaction)
│   │   ├── schemas/           Pydantic request/response DTOs (camelCase on the wire)
│   │   ├── repositories/      data access (household-scoped, generic base)
│   │   ├── services/          business logic + invariants
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
        ├── components/charts/  dependency-free SVG Donut/Bar charts
        ├── lib/compute.js     accrual/necessity/analytics formulas
        └── pages/             Dashboard, Add, Transactions, Accounts, Income,
                               Budgets, Goals, Family, Settings, auth/
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
- **Charts**: `frontend/src/components/charts/DonutChart.jsx` and
  `BarChart.jsx` are small, dependency-free SVG components — extend them
  directly rather than pulling in a charting library.
- **Real-time sync between browsers**: the app reads the API once when it
  loads and re-reads after each change you make, so a second browser
  won't pick up your entries until it's reloaded. If you want live sync,
  add a Server-Sent-Events or WebSocket endpoint on the backend and have
  `refresh()` in `App.jsx` fire on its messages — better than putting an
  interval back.
