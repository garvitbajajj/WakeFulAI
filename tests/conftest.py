import os

# Tests always run against the local JSON mock DB and the rule-based planner (set before .env is loaded)
os.environ["MOCK_SUPABASE"] = "true"
os.environ["MOCK_GEMINI"] = "true"
