# 🤖 SiteKeeper — Multi-Agent Site Health & Keep-Alive System

## Overview

SiteKeeper is a Python-based multi-agent system that keeps free-tier deployed web applications alive by simulating realistic user sessions, monitoring health metrics, and logging all activity to Supabase. It uses LangGraph for multi-agent orchestration, Playwright for browser automation, and FastAPI for a control dashboard API.

The core problem it solves: platforms like Render, Railway, and Fly.io spin down free-tier services after ~15 minutes of inactivity. SiteKeeper intelligently simulates user activity to prevent this, while also acting as a lightweight observability layer.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     APScheduler (runner.py)                  │
│              Triggers orchestrator every N minutes           │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │   Orchestrator Agent    │
              │   (LangGraph + Gemini)  │
              │  Reads target sites     │
              │  Plans which flows to   │
              │  trigger per site       │
              └──────┬─────────┬────────┘
                     │         │
        ┌────────────▼──┐  ┌───▼──────────────┐
        │ Browser Agent │  │  Monitor Agent    │
        │  (Playwright) │  │  (httpx)          │
        │               │  │                   │
        │ Simulates real │  │ Health checks,   │
        │ user sessions  │  │ latency tracking,│
        │ Screenshots    │  │ anomaly detection,│
        │ uploaded to    │  │ webhook alerts    │
        │ Supabase       │  │                   │
        └───────┬────────┘  └────────┬──────────┘
                │                    │
        ┌───────▼────────────────────▼──────────┐
        │              Supabase                  │
        │  PostgreSQL  │  Realtime  │  Storage   │
        │  (logs, runs,│  (live     │  (screens- │
        │   anomalies) │   updates) │   hots)    │
        └────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │     FastAPI Dashboard   │
              │  CRUD for target sites  │
              │  View logs & anomalies  │
              │  Start/stop agents      │
              └─────────────────────────┘
```

---

## Project Structure

```
sitekeeper/
│
├── orchestrator/
│   ├── __init__.py
│   ├── agent.py            # LangGraph state graph — orchestrator node
│   ├── planner.py          # Gemini LLM decides which flows to run per site
│   ├── tools.py            # Tool definitions exposed to sub-agents
│   └── graph.py            # Full LangGraph graph wiring all agents together
│
├── browser_agent/
│   ├── __init__.py
│   ├── agent.py            # LangChain agent with Playwright tools
│   ├── actions.py          # navigate(), click(), fill_form(), scroll(), screenshot()
│   └── session.py          # Playwright browser context lifecycle manager
│
├── monitor_agent/
│   ├── __init__.py
│   ├── agent.py            # Health check agent
│   ├── checker.py          # httpx-based uptime + latency checks
│   └── alerter.py          # Webhook/email notifications on anomaly detection
│
├── db/
│   ├── __init__.py
│   └── supabase_client.py  # Shared Supabase client + all DB helper functions
│
├── api/
│   ├── __init__.py
│   ├── main.py             # FastAPI app entrypoint
│   ├── routes/
│   │   ├── sites.py        # CRUD for target_sites table
│   │   ├── runs.py         # Read agent_runs logs
│   │   └── anomalies.py    # Read and resolve anomalies
│   └── schemas.py          # Pydantic models for request/response validation
│
├── scheduler/
│   ├── __init__.py
│   └── runner.py           # APScheduler — triggers orchestrator on interval
│
├── tests/
│   ├── test_monitor.py
│   ├── test_browser.py
│   └── test_api.py
│
├── .env.example            # Template for environment variables
├── .env                    # Actual secrets — never commit this
├── requirements.txt
├── docker-compose.yml      # Wires all services together
└── README.md
```

---

## Supabase Schema

Run these SQL statements in the Supabase SQL editor to set up the database.

```sql
-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Target sites to keep alive
CREATE TABLE target_sites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users,
  url TEXT NOT NULL,
  name TEXT NOT NULL,
  session_flow TEXT,              -- Plain English: "navigate to login, click dashboard"
  check_interval_minutes INTEGER DEFAULT 10,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Every agent run is logged here
CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id UUID REFERENCES target_sites(id) ON DELETE CASCADE,
  agent_type TEXT NOT NULL,       -- 'orchestrator' | 'browser' | 'monitor'
  status TEXT NOT NULL,           -- 'success' | 'failure' | 'anomaly'
  latency_ms INTEGER,
  screenshot_url TEXT,            -- Supabase Storage public URL
  notes TEXT,                     -- LLM-generated summary of the run
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Anomalies flagged by the monitor agent
CREATE TABLE anomalies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id UUID REFERENCES target_sites(id) ON DELETE CASCADE,
  detected_at TIMESTAMPTZ DEFAULT now(),
  latency_ms INTEGER,
  error_message TEXT,
  resolved BOOLEAN DEFAULT false
);

-- Row Level Security
ALTER TABLE target_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own sites" ON target_sites
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own runs" ON agent_runs
  FOR ALL USING (
    site_id IN (SELECT id FROM target_sites WHERE user_id = auth.uid())
  );

CREATE POLICY "Users see own anomalies" ON anomalies
  FOR ALL USING (
    site_id IN (SELECT id FROM target_sites WHERE user_id = auth.uid())
  );
```

Also create a Supabase Storage bucket named `agent-screenshots` with public access enabled.

---

## Environment Variables

Create a `.env` file in the project root based on `.env.example`:

```env
# Supabase
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key        # Use service key for backend (bypasses RLS)
SUPABASE_ANON_KEY=your-anon-key                   # Use anon key for user-facing auth

# Gemini LLM (via Google AI Studio)
GEMINI_API_KEY=your-gemini-api-key

# Scheduler
CHECK_INTERVAL_MINUTES=10                          # Global default, overridden per site

# Alerting (optional)
WEBHOOK_URL=https://hooks.slack.com/services/...   # Slack webhook for anomaly alerts
ALERT_EMAIL=you@example.com

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
```

---

## Agent Details

### 1. Orchestrator Agent (`orchestrator/agent.py`)

**Role:** The brain. Reads all active target sites from Supabase, uses Gemini LLM to decide which browser flows to simulate for each, then dispatches tasks to the Browser Agent and Monitor Agent.

**Framework:** LangGraph `StateGraph`

**State schema:**
```python
class OrchestratorState(TypedDict):
    sites: list[dict]           # Fetched from Supabase target_sites
    current_site: dict          # Site currently being processed
    planned_flow: str           # LLM-generated action plan for browser agent
    monitor_result: dict        # Result from monitor agent
    browser_result: dict        # Result from browser agent
    run_complete: bool
```

**LangGraph nodes:**
- `fetch_sites` — queries Supabase for all active sites
- `plan_flow` — calls Gemini with the site URL and `session_flow` description to generate a structured action plan
- `dispatch_browser` — passes action plan to Browser Agent
- `dispatch_monitor` — triggers Monitor Agent health check
- `log_results` — writes run results to Supabase `agent_runs`

**LangGraph edges:**
```
fetch_sites → plan_flow → dispatch_browser → dispatch_monitor → log_results
                                                    ↓ (if anomaly detected)
                                              trigger_alert
```

---

### 2. Browser Agent (`browser_agent/agent.py`)

**Role:** Simulates realistic user sessions using Playwright. Receives an action plan from the Orchestrator and executes steps like navigation, clicks, scrolls, and form fills. Takes a screenshot at the end of each session.

**Framework:** LangChain Agent with custom Playwright tools

**Available tools (defined in `browser_agent/actions.py`):**
- `navigate(url)` — opens URL in headless browser
- `click(selector)` — clicks a CSS selector or XPath
- `fill_form(selector, value)` — fills an input field
- `scroll(direction, amount)` — scrolls page
- `screenshot()` — captures page as PNG, uploads to Supabase Storage, returns public URL
- `get_page_title()` — returns current page title (used to verify navigation success)

**Session flow example:**

The Orchestrator sends a plan like:
```
1. Navigate to https://myapp.onrender.com
2. Wait for page load
3. Click the "Features" link in the navbar
4. Scroll down 500px
5. Navigate to /about
6. Take a screenshot
```

The Browser Agent parses this and executes each step using Playwright tools.

**Playwright setup:** Uses `async_playwright` with a headless Chromium context. Each session is isolated (new browser context per run).

---

### 3. Monitor Agent (`monitor_agent/agent.py`)

**Role:** Performs HTTP health checks on each target site, measures latency, detects anomalies, and sends alerts when thresholds are breached.

**Framework:** Pure Python with `httpx` (no LLM needed here — deterministic logic)

**Health check logic (`monitor_agent/checker.py`):**
- Sends GET request to target URL using `httpx.AsyncClient`
- Records: status code, latency in ms, response size
- Anomaly thresholds:
  - Status code not 2xx → anomaly
  - Latency > 5000ms → anomaly
  - Connection timeout → anomaly

**Anomaly detection:** Uses a simple z-score over the last 10 runs stored in Supabase. If the current latency is more than 2 standard deviations above the rolling average, it's flagged as an anomaly even if within the absolute threshold.

**Alerting (`monitor_agent/alerter.py`):**
- On anomaly: POST to `WEBHOOK_URL` (Slack incoming webhook format)
- Payload includes: site name, URL, latency, error message, timestamp
- Inserts a row into Supabase `anomalies` table

---

## Supabase Client (`db/supabase_client.py`)

Single shared client used by all agents and the API. Uses the service role key (bypasses RLS) since all operations are backend-initiated.

**Key functions:**
```python
get_active_sites() -> list[dict]
log_run(site_id, agent_type, status, latency_ms, notes, screenshot_url) -> None
log_anomaly(site_id, latency_ms, error_message) -> None
resolve_anomaly(anomaly_id) -> None
upload_screenshot(site_id, image_bytes) -> str   # Returns public URL
```

**Realtime subscription (optional dashboard feature):**
```python
supabase.realtime.channel("agent_runs").on(
    "postgres_changes",
    event="INSERT",
    schema="public",
    table="agent_runs",
    callback=handle_new_run
).subscribe()
```

---

## FastAPI Dashboard (`api/main.py`)

Provides a REST API to manage target sites and inspect logs. Intended to be paired with a minimal frontend (or called directly via curl/Postman).

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sites` | List all target sites |
| POST | `/sites` | Add a new target site |
| PUT | `/sites/{id}` | Update site config |
| DELETE | `/sites/{id}` | Remove a site |
| GET | `/runs` | List recent agent runs (filterable by site_id) |
| GET | `/anomalies` | List unresolved anomalies |
| POST | `/anomalies/{id}/resolve` | Mark anomaly as resolved |
| POST | `/trigger` | Manually trigger orchestrator for a site |
| GET | `/health` | API health check |

**Authentication:** Supabase JWT token passed in `Authorization: Bearer <token>` header. FastAPI middleware validates it against Supabase Auth.

---

## Scheduler (`scheduler/runner.py`)

Uses `APScheduler` (AsyncIOScheduler) to trigger the Orchestrator at regular intervals.

```python
# Runs every CHECK_INTERVAL_MINUTES minutes globally
# Each site can override this with its own check_interval_minutes field
scheduler.add_job(
    orchestrator.run,
    trigger="interval",
    minutes=CHECK_INTERVAL_MINUTES,
    id="main_orchestrator_job"
)
```

The scheduler runs in the same process as the FastAPI app (started in `api/main.py` lifespan events) to keep Docker services minimal.

---

## Docker Setup

All services run in a single Docker Compose file. There is no database container — Supabase is used as the external managed database.

```yaml
# docker-compose.yml
version: "3.9"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./:/app
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

  # Playwright requires system dependencies
  # Use the official Playwright Docker base image
```

**Dockerfile:**
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium

COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Requirements

```txt
# requirements.txt

# Agent framework
langchain>=0.2.0
langchain-google-genai>=1.0.0
langgraph>=0.1.0

# Browser automation
playwright>=1.44.0

# HTTP & async
httpx>=0.27.0
asyncio

# Database
supabase>=2.4.0

# API
fastapi>=0.111.0
uvicorn>=0.30.0
pydantic>=2.0.0

# Scheduler
apscheduler>=3.10.0

# Utilities
python-dotenv>=1.0.0
loguru>=0.7.0
```

---

## Setup & Running Locally

```bash
# 1. Clone the repo
git clone https://github.com/your-username/sitekeeper.git
cd sitekeeper

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium

# 5. Set up environment variables
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_SERVICE_KEY, GEMINI_API_KEY

# 6. Run Supabase schema SQL (in Supabase SQL editor)
# Paste contents of supabase_schema.sql

# 7. Start the app
uvicorn api.main:app --reload

# OR with Docker
docker-compose up --build
```

---

## Adding a Target Site

Via the API:
```bash
curl -X POST http://localhost:8000/sites \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT" \
  -d '{
    "url": "https://myapp.onrender.com",
    "name": "My Render App",
    "session_flow": "Navigate to the homepage, click the Get Started button, scroll down to the features section, navigate to the /about page",
    "check_interval_minutes": 10
  }'
```

The Orchestrator will pick this up on the next scheduled run, pass the `session_flow` to Gemini for structured planning, and dispatch the Browser Agent to simulate the session.

---

## Key Design Decisions

**Why LangGraph over vanilla LangChain agents?**
LangGraph allows explicit control over agent-to-agent communication via a typed state graph. This makes the orchestrator's routing logic transparent and debuggable — critical for a system running unattended.

**Why Playwright over raw HTTP pings?**
Platforms detect simple HTTP pings and may not count them as "activity." Playwright spins up a real Chromium instance that renders JavaScript, fires browser events, and behaves like an actual user — harder to distinguish from real traffic.

**Why Supabase over a local database?**
This project is designed to run on a free VPS or always-on machine (not the platforms it monitors). Supabase provides managed PostgreSQL, Storage, Auth, and Realtime without additional infrastructure cost or management overhead.

**Why APScheduler inside FastAPI instead of a separate service?**
Keeps Docker Compose simple — one container instead of two. The scheduler runs in background threads managed by FastAPI's lifespan context.

---

## Deployment

Deploy this system on something that does **not** sleep. Recommended options:

- **Oracle Cloud Free Tier** — always-free ARM VM, enough for this workload
- **Fly.io** — paid tier ($0 with their free allowance), does not sleep
- **Your own machine** — run as a systemd service

Do **not** deploy SiteKeeper itself on Render/Railway free tier — it would be the thing that needs to keep itself alive.

---

## Resume / Interview Talking Points

- **Multi-agent architecture:** Orchestrator uses LangGraph state graph to coordinate Browser and Monitor agents with conditional routing based on health signal
- **LLM-driven planning:** Gemini interprets natural language session descriptions and generates structured browser action sequences at runtime
- **Browser automation:** Playwright simulates real Chromium sessions — not HTTP pings — making activity indistinguishable from a human user
- **Observability:** Rolling z-score anomaly detection on latency metrics; all runs logged to Supabase with screenshot evidence
- **Supabase integration:** PostgreSQL for structured logs, Storage for screenshots, Realtime for live dashboard updates, Auth + RLS for multi-user security
- **Production-ready:** Dockerized, environment-variable driven, FastAPI REST control plane, APScheduler for reliable job management

---

## License

MIT
