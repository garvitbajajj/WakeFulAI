# 🤖 WakeFulAI — Multi-Agent Site Health & Keep-Alive System

## Overview

WakeFulAI runs scripted user journeys against your deployed web apps on a schedule, checks their health, and logs every run with screenshot evidence. You describe a journey in plain English, Gemini turns it into browser steps, and Playwright runs them in a real headless Chromium. LangGraph orchestrates the agents, FastAPI serves the REST API and dashboard, and Supabase stores everything (or a local JSON file in dev mode).

It started as a keep-alive tool: platforms like Render, Railway and Fly.io spin down free-tier services after ~15 minutes of inactivity, and regular visits keep them warm.

### Intended use

Point this at applications you own. Synthetic traffic whose purpose is to
defeat an idle timeout is against the terms of most free tiers, so using it
that way risks the deployment it is meant to protect — and a paid instance or
the platform's own cron is the honest fix for a service that must stay warm.

The part that holds up on any deployment, free or paid, is the monitoring:
scripted user journeys that prove a real flow still works, latency tracking
with anomaly detection, screenshot evidence of each run, and alerts when a
check fails. Run it as synthetic monitoring and the keep-alive is a side
effect rather than the point.

### What it does

- **Plain-English journeys** — "go to the homepage, click 'Get Started', scroll down 500, go to /about" becomes a list of browser steps (Gemini, with a rule-based fallback)
- **Real browser runs** — Playwright Chromium executes the steps and screenshots the end state, or the exact step that failed
- **Health checks** — status code, latency and response size on every run
- **Anomaly detection** — non-2xx, >5s latency, connection failures, and latency spikes vs. the site's own recent history (z-score)
- **Alerting** — one Slack message per incident, plus a recovery message and auto-resolve when the site is healthy again
- **Per-site schedules** — each site has its own check interval
- **Multi-user** — Supabase Auth; users only see their own sites, runs and anomalies (enforced in the API and by Row Level Security)
- **Dashboard + REST API** — add/run/delete sites, live run feed with screenshots, anomaly panel

---

## Architecture

```
      APScheduler (1-minute tick)          POST /sites/trigger
                 │                                 │
                 └────────────────┬────────────────┘
                                  ▼
              ┌───────────────────────────────────────┐
              │        Orchestrator (LangGraph)        │
              │  for each due site:                    │
              │  plan_flow → dispatch_browser →        │
              │  dispatch_monitor → log_results        │
              └─────┬──────────────┬──────────────┬────┘
                    ▼              ▼              ▼
                Planner      Browser Agent   Monitor Agent
              (Gemini, or    (Playwright,    (httpx check, z-score,
              rule fallback)  screenshots)    Slack alert / recovery)
                    └──────────────┬──────────────┘
                                   ▼
               Supabase — Postgres · Storage · Auth
          (or .local_db.json + .screenshots/ in mock mode)
                                   │
                                   ▼
                 FastAPI — REST API + dashboard at /
```

---

## Project Structure

```
WakeFulAI/
│
├── orchestrator/
│   ├── __init__.py         # run_orchestrator() entrypoint
│   ├── agent.py            # OrchestratorState (LangGraph state schema)
│   ├── graph.py            # LangGraph nodes and edges
│   └── planner.py          # Gemini / rule-based plain-English → browser steps
│
├── browser_agent/
│   ├── __init__.py
│   ├── agent.py            # Executes planned steps, captures screenshots
│   ├── actions.py          # navigate(), click(), fill_form(), scroll(), screenshot()
│   └── session.py          # Headless Chromium lifecycle (fresh browser per run)
│
├── monitor_agent/
│   ├── __init__.py
│   ├── agent.py            # Runs the check, logs it, decides alert vs. recovery
│   ├── checker.py          # httpx health check + z-score latency anomaly
│   └── alerter.py          # Anomaly + recovery Slack webhooks
│
├── db/
│   ├── __init__.py
│   └── supabase_client.py  # Supabase client (live) / JSON file DB (mock) + all queries
│
├── api/
│   ├── __init__.py
│   ├── main.py             # FastAPI app, lifespan (scheduler), dashboard HTML
│   ├── schemas.py          # Pydantic request/response models
│   └── routes/
│       ├── sites.py        # Auth, site CRUD, manual trigger
│       ├── runs.py         # Run history
│       └── anomalies.py    # List / resolve anomalies
│
├── scheduler/
│   ├── __init__.py
│   └── runner.py           # 1-minute tick, runs sites whose interval is due
│
├── tests/                  # pytest suite (see Tests)
│
├── supabase_schema.sql     # Tables + RLS policies
├── .env.example            # Template for environment variables
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## Setup & Running Locally

```bash
# 1. Clone the repo
git clone https://github.com/garvitbajajj/WakeFulAI.git
cd WakeFulAI

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies and the browser
pip install -r requirements.txt
playwright install chromium

# 4. Configure
cp .env.example .env      # then edit — see Environment Variables

# 5. Start the app
uvicorn api.main:app --reload
```

- Dashboard: http://localhost:8000
- Interactive API docs: http://localhost:8000/docs

### Running without Supabase

Set `MOCK_SUPABASE=true` in `.env` and the whole stack runs with no Supabase
project at all: records are written to a local `.local_db.json`, screenshots
to `.screenshots/` (served at `/screenshots`), and JWT verification is skipped
so every request is treated as a single local user. It is the fastest way to
see the agents work end to end, and it is strictly a development mode — never
set it on a deployment, since it removes authentication.

### Running with Supabase

1. Create a Supabase project.
2. Run [`supabase_schema.sql`](supabase_schema.sql) in the SQL editor. It is safe to re-run — tables use `IF NOT EXISTS` and policies are dropped and recreated.
3. Create a **public** Storage bucket named `agent-screenshots`.
4. Set `MOCK_SUPABASE=false`, `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`.

If `MOCK_SUPABASE` is not `true` and the Supabase credentials are missing, the app refuses to start rather than silently running without auth.

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `MOCK_SUPABASE` | `false` | `true` = local JSON DB and no auth (dev only) |
| `SUPABASE_URL` | — | Supabase project URL (required when not mocked) |
| `SUPABASE_SERVICE_KEY` | — | Service-role key; the backend uses it for all DB access |
| `GEMINI_API_KEY` | — | Google AI Studio key for the planner |
| `MOCK_GEMINI` | `true` | `true` = skip Gemini and use the rule-based planner |
| `GEMINI_MODEL` | `gemini-flash-latest` | Gemini model; the `-latest` alias survives model retirements |
| `CHECK_INTERVAL_MINUTES` | `10` | Check interval for sites that don't set their own |
| `WEBHOOK_URL` | — | Slack incoming webhook; alerts are only logged if unset |

---

## Database

Defined in [`supabase_schema.sql`](supabase_schema.sql):

| Table | Holds |
|---|---|
| `target_sites` | URL, name, plain-English `session_flow`, `check_interval_minutes`, `is_active`, owner `user_id` |
| `agent_runs` | One row per agent per run: `agent_type` (`browser` / `monitor` / `orchestrator`), `status` (`success` / `failure` / `anomaly`), latency, notes, screenshot URL |
| `anomalies` | Detected incidents with latency, error message and `resolved` flag |

Row Level Security limits every table to the owning user. The backend uses the service-role key (which bypasses RLS) and filters by user in the API itself.

---

## How a Run Works

### 1. Orchestrator (`orchestrator/graph.py`)

A LangGraph `StateGraph` that processes sites one at a time:

```
fetch_sites → plan_flow ──(no sites left)──→ END
                  │
                  ▼
          dispatch_browser → dispatch_monitor → log_results ─┐
                  ▲                                          │
                  └────────────── next site ─────────────────┘
```

- `fetch_sites` — uses the sites it was given (scheduler / manual trigger), otherwise all active sites
- `plan_flow` — takes the next site and turns its `session_flow` into steps (falls back to just opening the URL if planning fails)
- `dispatch_browser` — runs the steps in Playwright
- `dispatch_monitor` — runs the HTTP health check
- `log_results` — uploads the screenshot, logs the browser run and a combined orchestrator run (`anomaly` if either agent saw one, `failure` if either failed)

### 2. Planner (`orchestrator/planner.py`)

Sends the site URL and `session_flow` to Gemini (via `langchain-google-genai`) and asks for a JSON array of steps. When `MOCK_GEMINI=true`, no key is set, or Gemini errors, a rule-based parser handles it instead: it splits the text into sentences and matches *navigate / go to / open* (with an optional `/path`), *click* (quoted text or the words after "click"), *fill / type / enter* (quoted value; email/password inputs detected), and *scroll* (up/down plus pixels), and always starts by opening the site URL.

### 3. Browser Agent (`browser_agent/agent.py`)

Runs the steps in order in a fresh headless Chromium (1280×720):

| Step | Example |
|---|---|
| `navigate` | `{"action": "navigate", "url": "https://myapp.com/about"}` — waits for network idle |
| `click` | `{"action": "click", "selector": "text=Get Started"}` |
| `fill` | `{"action": "fill", "selector": "input[type=email]", "value": "me@example.com"}` |
| `scroll` | `{"action": "scroll", "direction": "down", "amount": 500}` |
| `screenshot` | `{"action": "screenshot"}` |

It stops at the first failing step and screenshots the page at that point; otherwise it screenshots the final page. Unknown actions are skipped.

### 4. Monitor Agent (`monitor_agent/`)

A plain `httpx` GET (10s timeout) — no LLM. The check is an **anomaly** when:

- the status code is not 2xx
- latency is over 5000 ms
- the request fails (timeout, DNS, connection error)
- latency is a spike: z-score > 2 against the site's last 10 successful monitor checks (needs at least 5) **and** over 1000 ms, so small jitter isn't flagged

**Alerting is once per incident:** the first anomaly inserts an `anomalies` row and posts to Slack; while it stays open, further anomalies are logged but not re-alerted; the next healthy check resolves it and posts a recovery message.

---

## API & Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard |
| GET | `/sites` | List your sites |
| POST | `/sites` | Add a site |
| PUT | `/sites/{id}` | Update a site |
| DELETE | `/sites/{id}` | Delete a site (and its runs and anomalies) |
| POST | `/sites/trigger` | Queue a run for one site (`{"site_id": ...}`) or all your active sites; returns 202 immediately |
| GET | `/runs` | Recent runs (`?site_id=`, `?limit=` up to 100) |
| GET | `/anomalies` | Unresolved anomalies |
| POST | `/anomalies/{id}/resolve` | Mark an anomaly resolved |
| GET | `/health` | API status, including whether the scheduler is running |

**Authentication:** a Supabase JWT in the `Authorization: Bearer <token>` header, verified against Supabase Auth. Requests for another user's site return 404. With `MOCK_SUPABASE=true` auth is disabled.

**Dashboard:** add, run and delete sites; a live feed of runs with status, latency and zoomable screenshots; an anomaly panel with resolve buttons. The run feed and anomalies refresh every 10 seconds. All server data is escaped before rendering, since run notes include text from the monitored pages.

### Adding a site

```bash
curl -X POST http://localhost:8000/sites \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT" \
  -d '{
    "url": "https://myapp.onrender.com",
    "name": "My Render App",
    "session_flow": "Navigate to the homepage, click \"Get Started\", scroll down 500, go to /about",
    "check_interval_minutes": 10
  }'
```

The scheduler picks it up within a minute, or run it immediately with `POST /sites/trigger`.

---

## Scheduler (`scheduler/runner.py`)

An `AsyncIOScheduler` ticks every minute and runs the orchestrator only for sites whose own `check_interval_minutes` has elapsed since their last run. It starts and stops with the FastAPI app (lifespan events), so everything runs in one process.

---

## Docker

```bash
docker-compose up --build
```

The image is built on the official Playwright Python image (Chromium and its system dependencies included) and serves the app on port 8000. Compose loads `.env`, mounts the project into the container and restarts it automatically. There is no database container — Supabase is external.

---

## Tests

```bash
pytest
```

17 tests across six files cover the API routes (including per-user isolation), the browser agent, the database layer, the monitor's anomaly rules, z-score detection and once-per-incident alerting, and the scheduler's per-site intervals. `tests/conftest.py` forces mock mode, so no Supabase project or API key is needed. The API trigger test queues a real browser run in the background; it passes offline, since a failed run doesn't fail the test.

---

## Known Limitations

- **No login screen** — in live mode the API requires a JWT, but the dashboard doesn't send one yet, so it only works in mock mode. Use the API with a token until a login form is added.
- **Last-run times are in memory** — after a restart, every site runs on the first tick.
- **Sites run one at a time** — fine for a handful of sites; a large list would need concurrent runs.
- **Only the monitor raises anomalies** — a failed browser journey is logged as a `failure` run but doesn't alert.
- **No retention** — old runs and screenshots are never deleted.

---

## Key Design Decisions

**Why LangGraph over vanilla LangChain agents?**
An explicit, typed state graph makes the orchestrator's flow transparent and debuggable — important for something that runs unattended.

**Why Playwright over plain HTTP pings?**
A ping only proves the server answers. A real browser runs the JavaScript and walks a user journey, so it catches a broken frontend, a missing button or a failing login that a 200 response would hide — and the screenshot shows what went wrong.

**Why Supabase?**
WakeFulAI is meant to run on an always-on machine, not the platforms it monitors. Supabase provides managed Postgres, file storage and auth without extra infrastructure.

**Why run the scheduler inside FastAPI?**
One process and one container. APScheduler's `AsyncIOScheduler` shares FastAPI's event loop and is started and stopped by the app's lifespan.

---

## Deployment

Deploy WakeFulAI on something that does **not** sleep:

- **Oracle Cloud Free Tier** — always-free ARM VM, enough for this workload
- **A small VPS** or **your own machine** — run with Docker or as a systemd service

Do **not** deploy WakeFulAI itself on Render/Railway free tier — it would be the thing that needs to keep itself alive.

---

## Resume / Interview Talking Points

- **Multi-agent orchestration:** LangGraph state graph coordinating planner, browser and monitor agents in a per-site loop
- **LLM-driven planning:** Gemini turns plain-English journeys into structured browser steps at runtime, with a deterministic fallback so runs never depend on the LLM
- **Browser automation:** real Chromium sessions with screenshot evidence of the final page or the failing step
- **Observability:** rolling z-score latency anomaly detection, once-per-incident alerting with automatic recovery
- **Security:** Supabase Auth, per-user data isolation in the API and via Row Level Security, fail-closed configuration, XSS-safe dashboard
- **Engineering:** Dockerized, FastAPI REST control plane, per-site scheduling, 17 automated tests

---

## License

MIT
