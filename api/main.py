from fastapi import FastAPI, Depends, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from api.routes import sites, runs, anomalies
from scheduler import start_scheduler, stop_scheduler, scheduler
from db import db_client
from db.supabase_client import SCREENSHOT_DIR
from loguru import logger
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start APScheduler
    logger.info("FastAPI Lifespan: Starting Scheduler...")
    start_scheduler()
    yield
    # Shutdown: Stop APScheduler
    logger.info("FastAPI Lifespan: Stopping Scheduler...")
    stop_scheduler()

app = FastAPI(
    title="WakeFulAI API & Dashboard",
    description="Multi-Agent Site Health & Keep-Alive Orchestration System",
    version="1.0.0",
    lifespan=lifespan
)

# Register routes
app.include_router(sites.router)
app.include_router(runs.router)
app.include_router(anomalies.router)

# Mock mode stores screenshots on disk instead of Supabase Storage
if db_client.mock_mode:
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    app.mount("/screenshots", StaticFiles(directory=SCREENSHOT_DIR), name="screenshots")

@app.get("/health", tags=["System"])
async def system_health():
    return {"status": "healthy", "scheduler_running": scheduler.running}

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WakeFulAI — Multi-Agent Keep-Alive Dashboard</title>
    <!-- Outfit Font -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #0b0f19;
            --bg-card: rgba(17, 24, 39, 0.7);
            --border-card: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --color-primary: #6366f1;
            --color-primary-glow: rgba(99, 102, 241, 0.2);
            --color-success: #10b981;
            --color-warning: #f59e0b;
            --color-danger: #ef4444;
            --font-family: 'Outfit', sans-serif;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-main);
            color: var(--text-primary);
            font-family: var(--font-family);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        /* Ambient Glow Backdrops */
        .glow-1 {
            position: absolute;
            top: -10%;
            left: -10%;
            width: 50%;
            height: 50%;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
            z-index: -1;
            filter: blur(80px);
            pointer-events: none;
        }
        .glow-2 {
            position: absolute;
            bottom: -10%;
            right: -10%;
            width: 50%;
            height: 50%;
            background: radial-gradient(circle, rgba(168, 85, 247, 0.1) 0%, transparent 70%);
            z-index: -1;
            filter: blur(80px);
            pointer-events: none;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.5rem 2rem;
            border-bottom: 1px solid var(--border-card);
            background: rgba(11, 15, 25, 0.8);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .logo-area {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-icon {
            font-size: 1.8rem;
            background: linear-gradient(135deg, #818cf8 0%, #c084fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo-title {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -0.025em;
            background: linear-gradient(180deg, #f8fafc 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .system-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.875rem;
            color: var(--text-secondary);
            background: rgba(255, 255, 255, 0.03);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            border: 1px solid var(--border-card);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--color-success);
            box-shadow: 0 0 12px var(--color-success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        main {
            flex: 1;
            max-width: 1400px;
            width: 100%;
            margin: 0 auto;
            padding: 2rem;
            display: grid;
            grid-template-columns: 350px 1fr;
            gap: 2rem;
        }

        @media (max-width: 1024px) {
            main {
                grid-template-columns: 1fr;
            }
        }

        /* Panels styling */
        .glass-panel {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(16px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
            transition: transform 0.3s ease, border-color 0.3s ease;
        }

        .glass-panel:hover {
            border-color: rgba(255, 255, 255, 0.15);
        }

        .panel-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* Form Inputs */
        .input-group {
            margin-bottom: 1rem;
        }

        .input-label {
            display: block;
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 0.4rem;
            font-weight: 500;
        }

        .form-control {
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-card);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: var(--text-primary);
            font-family: var(--font-family);
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }

        .form-control:focus {
            outline: none;
            border-color: var(--color-primary);
            box-shadow: 0 0 0 2px var(--color-primary-glow);
            background: rgba(255, 255, 255, 0.08);
        }

        textarea.form-control {
            resize: vertical;
            min-height: 80px;
        }

        /* Custom buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.75rem 1.25rem;
            font-size: 0.9rem;
            font-weight: 600;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            font-family: var(--font-family);
            width: 100%;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--color-primary) 0%, #4f46e5 100%);
            color: white;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(99, 102, 241, 0.45);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-primary);
            border: 1px solid var(--border-card);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .btn-small {
            padding: 0.4rem 0.8rem;
            font-size: 0.8rem;
            width: auto;
        }

        /* Anomalies Alerts */
        .anomalies-feed {
            margin-bottom: 1.5rem;
        }

        .anomaly-card {
            background: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.25);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            animation: slideIn 0.3s ease;
        }

        @keyframes slideIn {
            from { transform: translateY(10px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .anomaly-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }

        .anomaly-title {
            color: var(--color-danger);
            font-weight: 600;
            font-size: 0.95rem;
        }

        .anomaly-text {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 0.75rem;
        }

        /* Target Sites list */
        .site-list {
            margin-top: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .site-item {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-card);
            border-radius: 10px;
            padding: 0.9rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .site-info {
            flex: 1;
            min-width: 0;
            margin-right: 0.5rem;
        }

        .site-name-display {
            font-weight: 500;
            font-size: 0.95rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .site-url-display {
            font-size: 0.75rem;
            color: var(--text-secondary);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .site-actions {
            display: flex;
            gap: 0.4rem;
        }

        /* Runs Column */
        .dashboard-content {
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }

        .runs-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 1rem;
        }

        .run-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            transition: all 0.2s ease;
        }

        .run-card:hover {
            border-color: rgba(255, 255, 255, 0.12);
            background: rgba(17, 24, 39, 0.8);
        }

        .run-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
        }

        .run-agent-badge {
            background: var(--color-primary-glow);
            color: #a5b4fc;
            padding: 0.25rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .badge-monitor { background: rgba(16, 185, 129, 0.1); color: #6ee7b7; }
        .badge-browser { background: rgba(245, 158, 11, 0.1); color: #fcd34d; }
        .badge-orchestrator { background: rgba(99, 102, 241, 0.1); color: #a5b4fc; }

        .run-status-badge {
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.75rem;
        }

        .status-success { background: rgba(16, 185, 129, 0.1); color: var(--color-success); }
        .status-failure { background: rgba(239, 68, 68, 0.1); color: var(--color-danger); }
        .status-anomaly { background: rgba(245, 158, 11, 0.1); color: var(--color-warning); }

        .run-details {
            font-size: 0.9rem;
            line-height: 1.5;
            color: #cbd5e1;
            white-space: pre-line;
        }

        .run-time {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .run-screenshot-container {
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border-card);
            max-height: 200px;
            cursor: zoom-in;
            position: relative;
        }

        .run-screenshot-container img {
            width: 100%;
            height: auto;
            object-fit: cover;
            display: block;
            transition: transform 0.2s ease;
        }

        .run-screenshot-container:hover img {
            transform: scale(1.02);
        }

        .screenshot-overlay {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(0,0,0,0.6);
            color: white;
            font-size: 0.75rem;
            padding: 0.4rem;
            text-align: center;
            backdrop-filter: blur(4px);
        }

        /* Modal for full screenshot view */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            cursor: zoom-out;
            padding: 2rem;
        }

        .modal img {
            max-width: 90%;
            max-height: 90%;
            border-radius: 8px;
            border: 1px solid var(--border-card);
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }

        /* Footer */
        footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.8rem;
            border-top: 1px solid var(--border-card);
            margin-top: auto;
            background: rgba(11, 15, 25, 0.4);
        }

        footer a {
            color: var(--color-primary);
            text-decoration: none;
        }

        .stats-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border-card);
            padding: 1rem;
            border-radius: 12px;
            text-align: center;
        }

        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
            color: var(--color-primary);
        }
        
        .stat-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
            font-weight: 500;
        }

        /* Quick helper formatting */
        .text-bold { font-weight: 600; }
        .text-italic { font-style: italic; }
    </style>
</head>
<body>
    <div class="glow-1"></div>
    <div class="glow-2"></div>

    <header>
        <div class="logo-area">
            <span class="logo-icon">🤖</span>
            <div class="logo-title">WakeFulAI</div>
        </div>
        <div class="system-status">
            <div class="status-dot"></div>
            <span>Keep-Alive Engine Running</span>
        </div>
    </header>

    <main>
        <!-- Sidebar controls -->
        <div style="display: flex; flex-direction: column; gap: 1.5rem;">
            <!-- Site Creation -->
            <div class="glass-panel">
                <div class="panel-title">Add Target Site</div>
                <form id="add-site-form">
                    <div class="input-group">
                        <label class="input-label" for="site-name">Site Name</label>
                        <input class="form-control" type="text" id="site-name" placeholder="e.g. My Render App" required>
                    </div>
                    <div class="input-group">
                        <label class="input-label" for="site-url">App URL</label>
                        <input class="form-control" type="url" id="site-url" placeholder="https://example.com" required>
                    </div>
                    <div class="input-group">
                        <label class="input-label" for="session-flow">Session Flow (English Steps)</label>
                        <textarea class="form-control" id="session-flow" placeholder="e.g. Navigate to homepage, click features, wait 2 seconds."></textarea>
                    </div>
                    <div class="input-group">
                        <label class="input-label" for="check-interval">Interval (Minutes)</label>
                        <input class="form-control" type="number" id="check-interval" value="10" min="1" required>
                    </div>
                    <button class="btn btn-primary" type="submit">Register Site</button>
                </form>
            </div>

            <!-- Active Sites List -->
            <div class="glass-panel">
                <div class="panel-title">
                    <span>Configured Targets</span>
                    <button class="btn btn-secondary btn-small" onclick="loadSites()">🔄 Refresh</button>
                </div>
                <div id="active-sites" class="site-list">
                    <!-- Loaded dynamically -->
                    <div style="text-align: center; color: var(--text-secondary); font-size: 0.9rem; padding: 1rem 0;">Loading sites...</div>
                </div>
            </div>
        </div>

        <!-- Central Feed / Dashboard Content -->
        <div class="dashboard-content">
            <!-- Stats -->
            <div class="stats-summary">
                <div class="stat-card">
                    <div class="stat-value" id="stat-total-sites">0</div>
                    <div class="stat-label">Monitored Apps</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-total-runs">0</div>
                    <div class="stat-label">Runs Logged</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-active-anomalies" style="color: var(--color-success);">0</div>
                    <div class="stat-label">Active Anomalies</div>
                </div>
            </div>

            <!-- Anomalies Alerts Panel -->
            <div class="glass-panel" id="anomalies-section" style="display: none;">
                <div class="panel-title" style="color: var(--color-danger);">🚨 Active Anomalies</div>
                <div id="anomalies-feed" class="anomalies-feed">
                    <!-- Populated dynamically -->
                </div>
            </div>

            <!-- Logs / Runs Feed -->
            <div class="glass-panel">
                <div class="panel-title">
                    <span>Observed Keep-Alive Runs (Feed)</span>
                    <button class="btn btn-secondary btn-small" onclick="loadRuns()">🔄 Refresh</button>
                </div>
                <div id="runs-feed" class="runs-grid">
                    <!-- Loaded dynamically -->
                    <div style="text-align: center; color: var(--text-secondary); font-size: 0.9rem; padding: 2rem 0;">No activities logged yet. Trigger a keep-alive run!</div>
                </div>
            </div>
        </div>
    </main>

    <!-- Modal for screenshot view -->
    <div id="screenshot-modal" class="modal" onclick="closeModal()">
        <img id="modal-img" src="" alt="Screenshot Fullscreen">
    </div>

    <footer>
        WakeFulAI — Powered by LangGraph, Playwright, and FastAPI.
    </footer>

    <script>
        // Escape server data before putting it in innerHTML (site titles/errors come from monitored pages)
        const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

        async function fetchAPI(endpoint, method = 'GET', body = null) {
            const options = { method, headers: {} };
            if (body) {
                options.headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(body);
            }
            try {
                const response = await fetch(endpoint, options);
                if (!response.ok) {
                    const data = await response.json().catch(() => ({ detail: 'API Error' }));
                    throw new Error(data.detail || `HTTP error! Status: ${response.status}`);
                }
                return await response.json();
            } catch (err) {
                console.error(err);
                alert(`API Error: ${err.message}`);
                return null;
            }
        }

        async function loadSites() {
            const sites = await fetchAPI('/sites');
            if (!sites) return;

            document.getElementById('stat-total-sites').textContent = sites.length;
            const container = document.getElementById('active-sites');
            container.innerHTML = '';

            if (sites.length === 0) {
                container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); font-size: 0.9rem; padding: 1rem 0;">No targets added.</div>';
                return;
            }

            sites.forEach(site => {
                const item = document.createElement('div');
                item.className = 'site-item';
                item.innerHTML = `
                    <div class="site-info">
                        <div class="site-name-display">${esc(site.name)}</div>
                        <div class="site-url-display">${esc(site.url)}</div>
                    </div>
                    <div class="site-actions">
                        <button class="btn btn-primary btn-small" onclick="triggerSite('${site.id}')">⚡ Run</button>
                        <button class="btn btn-secondary btn-small" style="color: var(--color-danger);" onclick="deleteSite('${site.id}')">🗑️</button>
                    </div>
                `;
                container.appendChild(item);
            });
        }

        async function loadRuns() {
            const runs = await fetchAPI('/runs?limit=25');
            if (!runs) return;

            document.getElementById('stat-total-runs').textContent = runs.length;
            const container = document.getElementById('runs-feed');
            container.innerHTML = '';

            if (runs.length === 0) {
                container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); font-size: 0.9rem; padding: 2rem 0;">No activities logged yet.</div>';
                return;
            }

            runs.forEach(run => {
                const card = document.createElement('div');
                card.className = 'run-card';
                
                let agentClass = 'badge-orchestrator';
                if (run.agent_type === 'monitor') agentClass = 'badge-monitor';
                if (run.agent_type === 'browser') agentClass = 'badge-browser';

                let statusClass = 'status-success';
                if (run.status === 'failure') statusClass = 'status-failure';
                if (run.status === 'anomaly') statusClass = 'status-anomaly';

                const formattedDate = new Date(run.created_at).toLocaleString();
                const latencyText = run.latency_ms !== null ? `${run.latency_ms}ms` : 'N/A';

                let screenshotHtml = '';
                if (run.screenshot_url) {
                    screenshotHtml = `
                        <div class="run-screenshot-container" onclick="openModal(this.querySelector('img').src)">
                            <img src="${esc(run.screenshot_url)}" alt="Screenshot">
                            <div class="screenshot-overlay">🔍 Click to zoom screenshot</div>
                        </div>
                    `;
                }

                card.innerHTML = `
                    <div class="run-meta">
                        <span class="run-agent-badge ${agentClass}">${esc(run.agent_type)}</span>
                        <span class="run-status-badge ${statusClass}">${esc(run.status)}</span>
                    </div>
                    <div class="run-details">${esc(run.notes || 'No description provided.')}</div>
                    ${screenshotHtml}
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="run-time">⏱️ Latency: <span class="text-bold">${latencyText}</span></span>
                        <span class="run-time">${formattedDate}</span>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        async function loadAnomalies() {
            const anomalies = await fetchAPI('/anomalies');
            if (!anomalies) return;

            document.getElementById('stat-active-anomalies').textContent = anomalies.length;
            const badge = document.getElementById('stat-active-anomalies');
            if (anomalies.length > 0) {
                badge.style.color = 'var(--color-danger)';
                document.getElementById('anomalies-section').style.display = 'block';
            } else {
                badge.style.color = 'var(--color-success)';
                document.getElementById('anomalies-section').style.display = 'none';
            }

            const container = document.getElementById('anomalies-feed');
            container.innerHTML = '';

            anomalies.forEach(anomaly => {
                const card = document.createElement('div');
                card.className = 'anomaly-card';
                const formattedDate = new Date(anomaly.detected_at).toLocaleString();
                card.innerHTML = `
                    <div class="anomaly-header">
                        <span class="anomaly-title">🚨 Latency/Uptime Issue Detected</span>
                        <button class="btn btn-secondary btn-small" onclick="resolveAnomaly('${anomaly.id}')">Resolve Alert</button>
                    </div>
                    <div class="anomaly-text">
                        <strong>Error message:</strong> ${esc(anomaly.error_message)}<br>
                        <strong>Latency:</strong> ${esc(anomaly.latency_ms)}ms | <strong>Detected at:</strong> ${formattedDate}
                    </div>
                `;
                container.appendChild(card);
            });
        }

        async function triggerSite(siteId) {
            const btn = document.querySelector(`[onclick="triggerSite('${siteId}')"]`);
            const prevText = btn.innerHTML;
            btn.innerHTML = '⏳ running...';
            btn.disabled = true;

            const res = await fetchAPI('/sites/trigger', 'POST', { site_id: siteId });
            if (res) {
                setTimeout(async () => {
                    await loadRuns();
                    await loadAnomalies();
                }, 1000);
            }

            btn.innerHTML = prevText;
            btn.disabled = false;
        }

        async function deleteSite(siteId) {
            if (confirm('Are you sure you want to delete this target site?')) {
                const res = await fetchAPI(`/sites/${siteId}`, 'DELETE');
                if (res) {
                    await loadSites();
                    await loadRuns();
                    await loadAnomalies();
                }
            }
        }

        async function resolveAnomaly(anomalyId) {
            const res = await fetchAPI(`/anomalies/${anomalyId}/resolve`, 'POST');
            if (res) {
                await loadAnomalies();
            }
        }

        // Form handler
        document.getElementById('add-site-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('site-name').value;
            const url = document.getElementById('site-url').value;
            const session_flow = document.getElementById('session-flow').value;
            const check_interval_minutes = parseInt(document.getElementById('check-interval').value);

            const res = await fetchAPI('/sites', 'POST', {
                name, url, session_flow, check_interval_minutes
            });

            if (res) {
                document.getElementById('add-site-form').reset();
                await loadSites();
            }
        });

        // Screenshot modal functions
        function openModal(src) {
            document.getElementById('modal-img').src = src;
            document.getElementById('screenshot-modal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('screenshot-modal').style.display = 'none';
        }

        // Initial Load & polling
        async function init() {
            await loadSites();
            await loadRuns();
            await loadAnomalies();
            
            // Auto refresh feeds every 10 seconds to keep live dashboard state
            setInterval(async () => {
                await loadRuns();
                await loadAnomalies();
            }, 10000);
        }

        window.onload = init;
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard_index():
    return DASHBOARD_HTML
