# Household Finance Agent

A LangChain **deep agent** that reads one household's books out of the
Ledger & Card database and answers questions about them: what was spent,
what is unusual, what is coming, what it will cost, and what to do next.

It runs as **its own service**. The backend calls it over HTTP when a
user asks for something; nothing else talks to it.

```
frontend ──▶ backend (FastAPI)  ──HTTP──▶  ai-agent (this service)
                   │                              │
                   └──── writes ───▶ PostgreSQL ◀── reads (READ ONLY)
```

## The one idea worth understanding

**Python computes every number. The model only decides what the numbers
mean.**

`app/finance/` is ordinary arithmetic over the ledger — medians, budget
pro-rating, reducing-balance amortisation, robust z-scores. No LLM is
involved in producing a single rupee figure. The agent's tools return
those results, and the system prompt forbids the model from doing
arithmetic of its own: if it wants a figure no tool gives it, it has to
say so.

That is what makes the service safe to put in front of someone's money.
An LLM that adds two numbers together produces a result that looks
exactly as authoritative as a real one and is wrong often enough to
matter. Here, a figure either came out of `app/finance/` or it is not in
the answer.

It also means the numbers are worth something on their own — hence two
families of endpoint (below), one of which never calls a model at all.

## What it can do

| Capability | What it answers |
| --- | --- |
| `categorise` | Which category each uncategorised expense belongs to |
| `anomalies` | What spending is unusual **for this household** |
| `budget` | Budget vs actual, at pace, per category |
| `forecast` | What next month will cost, committed vs variable |
| `investments` | Holdings, allocation, returns, stalled SIPs, debts |
| `obligations` | SIPs, deposits maturing, loans, credit cards |
| `bills` | What is due in the next N days |
| `report` | The monthly financial report |
| `recommendations` | What to do next, against the household's own goals |
| `ask` | A free-form question about their finances |

## The two families of endpoint

Every capability is addressable twice.

**`POST /analysis/{capability}`** returns the figures alone. No model,
byte-identical on every run, milliseconds rather than minutes. This is what a dashboard card,
a chart, or a test should call.

**`POST /agent/{capability}`** runs the deep agent over exactly those
figures and returns a typed narrative — insights with the evidence
behind them, and actions with their expected effect.

A caller that wants numbers should never pay for tokens to get them, and
a caller that wants judgement gets it grounded in numbers it can fetch
separately and check.

```
GET  /health                      posture; unauthenticated (container probe)
GET  /capabilities                what this service can do
POST /analysis/{capability}       deterministic figures
POST /analysis/recurring/detect   standing commitments, active and lapsed
POST /agent/{capability}          the agent's narrative
```

Request body (both families):

```jsonc
{
  "householdId": 1,       // required; the backend sets this, never the client
  "month": "2026-09",     // optional, 'YYYY-MM'
  "horizonDays": 45,      // optional, for bills/obligations
  "question": "...",      // required by `ask` only
  "history": [            // `ask` only; earlier turns, oldest first
    { "question": "How did September go?", "answer": "You spent …" }
  ],
  "asOf": "2026-09-30"    // optional; tests and back-dated reports only
}
```

This service holds **no conversation state** — every call rebuilds the
household's books from scratch — so a client that wants follow-up
questions to work sends `history` with each one. Only the last six turns
are replayed, and only the questions and answers: the tool results behind
them are left out on purpose, because replaying those would grow the
context with every question and put stale figures in front of the model
as if they were current.

## How the agent is put together

`create_deep_agent` from `deepagents`, with:

- **14 finance tools**, each a closure over one already-loaded household
  snapshot (`app/agent/tools.py`);
- **three subagents** — `spending-analyst`, `portfolio-analyst`,
  `planning-analyst` — each holding only the tools its remit needs
  (`app/agent/subagents.py`);
- **typed output** per capability via `ToolStrategy`
  (`app/agent/schemas.py`), so the backend gets something renderable and
  a run that produces nothing validated is an error rather than a
  plausible paragraph.

Subagents are only wired in for the capabilities that genuinely span
domains — `report`, `recommendations` and `ask`. Everything else runs
flat, which also removes the `task` tool from its surface entirely.
Narrow capabilities see 15 tools; the delegating ones see 23.

### Why the tools are rebuilt per request

A tool takes **no household id**. It closes over one snapshot, so there
is no id for the model to get wrong, and a prompt injected through a
transaction name has no id to name. Compiling a LangGraph takes
microseconds against a model call measured in seconds, so per-request
construction costs nothing worth optimising away and removes the one bug
worth designing against.

### Why one snapshot per request

An agent run makes many tool calls over many seconds. Reading live each
time would let the books change underneath a single analysis — the
forecast could disagree with the budget it was derived from. One
snapshot means one run sees one set of facts, and the number of database
round trips is a function of requests rather than of how chatty the
model feels.

## Safety

- **Read-only by construction.** `create_all` is never called, and on
  Postgres every connection is opened with
  `default_transaction_read_only=on` as a libpq option, so a stray write
  raises instead of touching the family's books. (Setting it with a `SET`
  statement on connect is the obvious approach and does not work — `SET`
  is transactional, and the pool's rollback on check-in reverts it.)
  For defence that does not depend on this process at all, point
  `DATABASE_URL` at a Postgres role with only `SELECT` granted.
- **Tenancy decided once.** `household_id` is applied in exactly one
  place (`load_snapshot`). The backend resolves it from the
  authenticated user; this service never sees an end user.
- **Shared-secret auth.** `Authorization: Bearer $AGENT_SERVICE_TOKEN`,
  compared in constant time. An unset token refuses every request rather
  than defaulting to open.
- **Tool output is data, not instructions.** Transaction and merchant
  names are strings the household typed. The system prompt says so
  explicitly, because a household sharing books with relatives is a
  place where someone can type whatever they like.
- **Bounded cost.** A recursion limit caps graph loops, `asyncio.wait_for`
  caps wall-clock time, and tool results are capped and announce their
  own truncation.
- **The shell tool is removed** at the harness level — this service has
  no sandbox and nothing to run.

## Configuration

Copy `.env.example` to `.env`. Required:

| Variable | Meaning |
| --- | --- |
| `OLLAMA_BASE_URL` | Where Ollama listens (default `http://127.0.0.1:11434`). Point it at nothing and `/agent/*` returns 503 while `/analysis/*` still works. |
| `DATABASE_URL` | The backend's database. Postgres in production. |
| `AGENT_SERVICE_TOKEN` | Shared secret; must match the backend's. |

Optional: `AGENT_MODEL` (default `llama3.1:8b`), `AGENT_SUBAGENT_MODEL`,
`AGENT_TEMPERATURE` (default 0 — two runs over unchanged books must not
disagree), `AGENT_NUM_CTX` (16384), `AGENT_RECURSION_LIMIT` (40),
`AGENT_TIMEOUT_SECONDS` (270), `ALLOWED_ORIGINS`, `PORT` (8100).

### The model

The model runs on **Ollama, locally**. That is a deliberate choice, not a
cost one: a household's ledger — salary credits, loan balances, every
merchant they pay — is read by a model on hardware they control, and no
monetary figure crosses a network boundary to a vendor. There is no API
key here because there is no vendor.

Two constraints on which model you pick:

- **It must support tool calling.** Every figure reaches the model
  through a typed finance tool, and the structured answer comes back as
  one more tool call (`ToolStrategy`). `llama3.1:8b` and the `qwen3`
  family work. `gemma3` has no tool support and will fail every
  `/agent/*` call.
- **Give it context.** Ollama defaults `num_ctx` to 2048 and then
  silently drops the oldest tokens — which here means losing the system
  prompt, not getting an error. `AGENT_NUM_CTX` is passed on every model
  this service builds. The default of 16384 leaves room for the system
  prompt, the tool schemas and several rounds of tool output; the
  delegating capabilities (`report`, `recommendations`, `ask`) carry the
  most, so lower it only after watching one of those run.

```bash
ollama pull llama3.1:8b
```

**Give it more than 8B if you can.** The arithmetic is all done in
`app/finance`, so the model cannot get a number wrong by computing it —
but it can still misread one, and choosing which figures matter is the
part a small model does badly. Measured on `llama3.1:8b` against the
demo household: it passed `"currentMonth"` as a literal month argument,
reported "the budget is not set" from a tool result that said
`monthlyBudget: 80000`, and ended `/agent/budget` with prose instead of
calling the response tool — so the run was reported as a failure rather
than returning a wrong answer, which is the behaviour you want but not
a working assistant. The tool-calling wiring is fine at that size; the
judgement is not. A 14B-class model or better is the floor for the
`/agent/*` half. The `/analysis/*` half needs no model at all and is
exact either way.

If the agent runs in Docker and Ollama runs on the host, the daemon must
be listening on more than loopback. Ollama binds `127.0.0.1` by default,
and a container's packets to the host gateway are then dropped rather
than refused — so the symptom is a *connect timeout*, not "connection
refused". Fix it on the host:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"\n' \
  | sudo tee /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

`0.0.0.0` also exposes the model to anything else on your network. It
cannot reach the ledger — that lives in Postgres, behind the agent — but
if the machine shares a network you do not control, bind the Docker
bridge instead (`OLLAMA_HOST=172.17.0.1:11434`) and reach it from the
host at that address rather than `127.0.0.1`. Compose already maps
`host.docker.internal` for Linux. Alternatively run the
bundled container: `docker compose --profile ollama up -d`.

## Running it

```bash
# the whole stack
docker compose up --build            # agent on the compose network, not published

# this service alone
cd ai-agent
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env                 # point OLLAMA_BASE_URL at your Ollama
./.venv/bin/python main.py           # http://127.0.0.1:8100/docs
```

Against the backend's local SQLite instead of Postgres:

```bash
DATABASE_URL="sqlite:///../backend/expense_tracker.db" \
AGENT_SERVICE_TOKEN=dev ./.venv/bin/python main.py
```

Check it without touching the model at all:

```bash
curl -s -X POST http://127.0.0.1:8100/analysis/budget \
  -H 'Authorization: Bearer dev' -H 'Content-Type: application/json' \
  -d '{"householdId":1,"month":"2026-09"}' | jq
```

## Keeping it honest

`app/finance/portfolio.py` ports the amortisation and contribution-growth
maths from `backend/app/services/portfolio_math.py`, and
`app/finance/month.py` restates the accrual rules from
`backend/app/services/month_math.py`. They are duplicated rather than
imported because this service runs in its own container.

**If either backend file changes, change its counterpart here.** An
agent that disagrees with the app about how much a loan still owes is
worse than no agent at all.

## Layout

```
app/
├── core/          config, the read-only engine, shared-secret auth
├── data/          thin read-only table mirrors + the per-request snapshot
├── finance/       ← every number lives here. No LLM.
│   ├── month.py        month keys, accrual rules, robust statistics
│   ├── rules.py        merchant → category table (word-boundary matched)
│   ├── categorize.py   history first, then rules, then the model
│   ├── recurring.py    what repeats, and what stopped
│   ├── anomaly.py      six checks, all median-based
│   ├── budget.py       budget vs actual, at pace
│   ├── forecast.py     committed + variable, with a band
│   ├── portfolio.py    holdings, allocation, amortisation  ⟵ mirrors backend
│   ├── obligations.py  bills, EMIs, maturities, cards, papers
│   ├── goals.py        progress, surplus, emergency fund, debt priority
│   └── report.py       the monthly report's raw material
├── agent/         ← the model's half
│   ├── llm.py          model factory; strips `execute` and the default subagent
│   ├── tools.py        14 tools, closures over one snapshot
│   ├── prompts.py      system + per-capability task prompts
│   ├── subagents.py    the three analysts
│   ├── schemas.py      typed output per capability
│   └── runner.py       build, run, bound, extract
├── schemas/       request/response DTOs (camelCase)
└── controllers/   the HTTP surface
```
