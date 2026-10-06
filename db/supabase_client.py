import os
import json
import uuid
import base64
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

MOCK_SUPABASE = os.getenv("MOCK_SUPABASE", "true").lower() == "true"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

class SupabaseClient:
    def __init__(self):
        self.mock_mode = MOCK_SUPABASE
        if self.mock_mode:
            logger.info("SupabaseClient: Running in MOCK mode. Data saved locally to '.local_db.json'")
            self.db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".local_db.json")
            self._init_mock_db()
        else:
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                logger.error("Supabase credentials missing. Defaulting to MOCK mode.")
                self.mock_mode = True
                self.db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".local_db.json")
                self._init_mock_db()
                return
            logger.info(f"SupabaseClient: Running in LIVE mode connecting to {SUPABASE_URL}")
            from supabase import create_client, Client
            self.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def _init_mock_db(self):
        if not os.path.exists(self.db_file):
            # Prepopulate with dummy data
            dummy_site_id = str(uuid.uuid4())
            initial_data = {
                "target_sites": [
                    {
                        "id": dummy_site_id,
                        "user_id": None,
                        "url": "https://httpbin.org/status/200",
                        "name": "Httpbin Health Check",
                        "session_flow": "1. Navigate to url\n2. Verify the status code is 200",
                        "check_interval_minutes": 10,
                        "is_active": True,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    }
                ],
                "agent_runs": [],
                "anomalies": []
            }
            self._save_mock_db(initial_data)

    def _read_mock_db(self) -> dict:
        try:
            with open(self.db_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read mock db file: {e}")
            return {"target_sites": [], "agent_runs": [], "anomalies": []}

    def _save_mock_db(self, data: dict):
        try:
            with open(self.db_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write mock db file: {e}")

    # --- Target Sites CRUD ---

    def get_active_sites(self) -> list[dict]:
        if self.mock_mode:
            db = self._read_mock_db()
            return [site for site in db.get("target_sites", []) if site.get("is_active", True)]
        else:
            try:
                response = self.client.table("target_sites").select("*").eq("is_active", True).execute()
                return response.data
            except Exception as e:
                logger.error(f"Supabase get_active_sites error: {e}")
                return []

    def get_all_sites(self) -> list[dict]:
        if self.mock_mode:
            db = self._read_mock_db()
            return db.get("target_sites", [])
        else:
            try:
                response = self.client.table("target_sites").select("*").execute()
                return response.data
            except Exception as e:
                logger.error(f"Supabase get_all_sites error: {e}")
                return []

    def get_site(self, site_id: str) -> dict:
        if self.mock_mode:
            db = self._read_mock_db()
            for site in db.get("target_sites", []):
                if site["id"] == site_id:
                    return site
            return None
        else:
            try:
                response = self.client.table("target_sites").select("*").eq("id", site_id).maybe_single().execute()
                return response.data
            except Exception as e:
                logger.error(f"Supabase get_site error: {e}")
                return None

    def add_site(self, site_data: dict) -> dict:
        if self.mock_mode:
            db = self._read_mock_db()
            new_site = {
                "id": str(uuid.uuid4()),
                "user_id": site_data.get("user_id"),
                "url": site_data["url"],
                "name": site_data["name"],
                "session_flow": site_data.get("session_flow"),
                "check_interval_minutes": site_data.get("check_interval_minutes", 10),
                "is_active": site_data.get("is_active", True),
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            db["target_sites"].append(new_site)
            self._save_mock_db(db)
            return new_site
        else:
            try:
                response = self.client.table("target_sites").insert(site_data).execute()
                return response.data[0] if response.data else None
            except Exception as e:
                logger.error(f"Supabase add_site error: {e}")
                raise e

    def update_site(self, site_id: str, update_data: dict) -> dict:
        if self.mock_mode:
            db = self._read_mock_db()
            for site in db.get("target_sites", []):
                if site["id"] == site_id:
                    for key, val in update_data.items():
                        site[key] = val
                    self._save_mock_db(db)
                    return site
            return None
        else:
            try:
                response = self.client.table("target_sites").update(update_data).eq("id", site_id).execute()
                return response.data[0] if response.data else None
            except Exception as e:
                logger.error(f"Supabase update_site error: {e}")
                raise e

    def delete_site(self, site_id: str) -> bool:
        if self.mock_mode:
            db = self._read_mock_db()
            sites = db.get("target_sites", [])
            new_sites = [s for s in sites if s["id"] != site_id]
            if len(sites) == len(new_sites):
                return False
            db["target_sites"] = new_sites
            # Cascade delete runs and anomalies
            db["agent_runs"] = [r for r in db.get("agent_runs", []) if r["site_id"] != site_id]
            db["anomalies"] = [a for a in db.get("anomalies", []) if a["site_id"] != site_id]
            self._save_mock_db(db)
            return True
        else:
            try:
                response = self.client.table("target_sites").delete().eq("id", site_id).execute()
                return len(response.data) > 0
            except Exception as e:
                logger.error(f"Supabase delete_site error: {e}")
                return False

    # --- Agent Runs ---

    def log_run(self, site_id: str, agent_type: str, status: str, latency_ms: int, notes: str, screenshot_url: str = None) -> dict:
        run_data = {
            "site_id": site_id,
            "agent_type": agent_type,
            "status": status,
            "latency_ms": latency_ms,
            "screenshot_url": screenshot_url,
            "notes": notes,
        }
        if self.mock_mode:
            db = self._read_mock_db()
            run_data["id"] = str(uuid.uuid4())
            run_data["created_at"] = datetime.utcnow().isoformat() + "Z"
            db["agent_runs"].append(run_data)
            self._save_mock_db(db)
            return run_data
        else:
            try:
                response = self.client.table("agent_runs").insert(run_data).execute()
                return response.data[0] if response.data else None
            except Exception as e:
                logger.error(f"Supabase log_run error: {e}")
                return run_data

    def get_recent_runs(self, site_id: str = None, limit: int = 50) -> list[dict]:
        if self.mock_mode:
            db = self._read_mock_db()
            runs = db.get("agent_runs", [])
            if site_id:
                runs = [r for r in runs if r["site_id"] == site_id]
            runs = sorted(runs, key=lambda x: x["created_at"], reverse=True)
            return runs[:limit]
        else:
            try:
                query = self.client.table("agent_runs").select("*")
                if site_id:
                    query = query.eq("site_id", site_id)
                response = query.order("created_at", descending=True).limit(limit).execute()
                return response.data
            except Exception as e:
                logger.error(f"Supabase get_recent_runs error: {e}")
                return []

    # --- Anomalies ---

    def log_anomaly(self, site_id: str, latency_ms: int, error_message: str) -> dict:
        anomaly_data = {
            "site_id": site_id,
            "latency_ms": latency_ms,
            "error_message": error_message,
            "resolved": False
        }
        if self.mock_mode:
            db = self._read_mock_db()
            anomaly_data["id"] = str(uuid.uuid4())
            anomaly_data["detected_at"] = datetime.utcnow().isoformat() + "Z"
            db["anomalies"].append(anomaly_data)
            self._save_mock_db(db)
            return anomaly_data
        else:
            try:
                response = self.client.table("anomalies").insert(anomaly_data).execute()
                return response.data[0] if response.data else None
            except Exception as e:
                logger.error(f"Supabase log_anomaly error: {e}")
                return anomaly_data

    def resolve_anomaly(self, anomaly_id: str) -> dict:
        if self.mock_mode:
            db = self._read_mock_db()
            for anomaly in db.get("anomalies", []):
                if anomaly["id"] == anomaly_id:
                    anomaly["resolved"] = True
                    self._save_mock_db(db)
                    return anomaly
            return None
        else:
            try:
                response = self.client.table("anomalies").update({"resolved": True}).eq("id", anomaly_id).execute()
                return response.data[0] if response.data else None
            except Exception as e:
                logger.error(f"Supabase resolve_anomaly error: {e}")
                return None

    def get_unresolved_anomalies(self) -> list[dict]:
        if self.mock_mode:
            db = self._read_mock_db()
            return [a for a in db.get("anomalies", []) if not a.get("resolved", False)]
        else:
            try:
                response = self.client.table("anomalies").select("*").eq("resolved", False).execute()
                return response.data
            except Exception as e:
                logger.error(f"Supabase get_unresolved_anomalies error: {e}")
                return []

    # --- Storage for screenshots ---

    def upload_screenshot(self, site_id: str, image_bytes: bytes) -> str:
        filename = f"{site_id}/{int(datetime.utcnow().timestamp())}.png"
        if self.mock_mode:
            # For mock mode, save the screenshot locally to a mock folder or encode it as a Data URL
            # Data URL is amazing since the API / frontend can display it without extra endpoints!
            base64_str = base64.b64encode(image_bytes).decode("utf-8")
            return f"data:image/png;base64,{base64_str}"
        else:
            try:
                # Supposed to upload to 'agent-screenshots' bucket
                response = self.client.storage.from_("agent-screenshots").upload(
                    path=filename,
                    file=image_bytes,
                    file_options={"content-type": "image/png"}
                )
                # Get public URL
                public_url_resp = self.client.storage.from_("agent-screenshots").get_public_url(filename)
                return public_url_resp
            except Exception as e:
                logger.error(f"Supabase upload_screenshot error: {e}")
                # Fallback to local Data URL on upload error
                base64_str = base64.b64encode(image_bytes).decode("utf-8")
                return f"data:image/png;base64,{base64_str}"

# Singleton client instance
db_client = SupabaseClient()
