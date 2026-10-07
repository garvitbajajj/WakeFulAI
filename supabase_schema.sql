-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Target sites to keep alive
CREATE TABLE IF NOT EXISTS target_sites (
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
CREATE TABLE IF NOT EXISTS agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id UUID REFERENCES target_sites(id) ON DELETE CASCADE,
  agent_type TEXT NOT NULL,       -- 'orchestrator' | 'browser' | 'monitor'
  status TEXT NOT NULL,           -- 'success' | 'failure' | 'anomaly'
  latency_ms INTEGER,
  screenshot_url TEXT,            -- Supabase Storage public URL
  notes TEXT,                     -- Step-by-step log of the run
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Anomalies flagged by the monitor agent
CREATE TABLE IF NOT EXISTS anomalies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id UUID REFERENCES target_sites(id) ON DELETE CASCADE,
  detected_at TIMESTAMPTZ DEFAULT now(),
  latency_ms INTEGER,
  error_message TEXT,
  resolved BOOLEAN DEFAULT false
);

-- Indexes for the foreign keys (runs are always read per site, newest first)
CREATE INDEX IF NOT EXISTS target_sites_user_id_idx ON target_sites (user_id);
CREATE INDEX IF NOT EXISTS agent_runs_site_id_created_at_idx ON agent_runs (site_id, created_at DESC);
CREATE INDEX IF NOT EXISTS anomalies_site_id_idx ON anomalies (site_id);

-- Row Level Security
ALTER TABLE target_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies ENABLE ROW LEVEL SECURITY;

-- The backend uses the service_role key, which bypasses RLS; these policies lock down anon/user-key access.
-- auth.uid() is wrapped in a subselect so Postgres evaluates it once per query, not once per row.
DROP POLICY IF EXISTS "Users see own sites" ON target_sites;
DROP POLICY IF EXISTS "Users see own runs" ON agent_runs;
DROP POLICY IF EXISTS "Users see own anomalies" ON anomalies;

CREATE POLICY "Users see own sites" ON target_sites
  FOR ALL USING ((select auth.uid()) = user_id);

CREATE POLICY "Users see own runs" ON agent_runs
  FOR ALL USING (
    site_id IN (SELECT id FROM target_sites WHERE user_id = (select auth.uid()))
  );

CREATE POLICY "Users see own anomalies" ON anomalies
  FOR ALL USING (
    site_id IN (SELECT id FROM target_sites WHERE user_id = (select auth.uid()))
  );

-- Public bucket for browser-run screenshots
INSERT INTO storage.buckets (id, name, public)
VALUES ('agent-screenshots', 'agent-screenshots', true)
ON CONFLICT (id) DO NOTHING;
