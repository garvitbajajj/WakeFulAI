import pytest
from db import db_client

def test_db_client_mock_crud():
    # Verify it runs in mock mode for safety during tests
    assert db_client.mock_mode is True
    
    # 1. Add site
    site_data = {
        "url": "https://example.com/test-suite",
        "name": "Test Suite App",
        "session_flow": "1. Navigate\n2. Click button",
        "check_interval_minutes": 5,
        "is_active": True
    }
    new_site = db_client.add_site(site_data)
    assert new_site is not None
    assert new_site["id"] is not None
    assert new_site["name"] == "Test Suite App"
    site_id = new_site["id"]

    # 2. Get site
    fetched = db_client.get_site(site_id)
    assert fetched is not None
    assert fetched["name"] == "Test Suite App"

    # 3. Update site
    updated = db_client.update_site(site_id, {"name": "Updated Test Suite App"})
    assert updated is not None
    assert updated["name"] == "Updated Test Suite App"

    # 4. Log agent run
    run = db_client.log_run(
        site_id=site_id,
        agent_type="monitor",
        status="success",
        latency_ms=300,
        notes="Health check OK"
    )
    assert run["id"] is not None
    assert run["site_id"] == site_id
    assert run["status"] == "success"

    # 5. Fetch runs
    runs = db_client.get_recent_runs(site_id=site_id, limit=5)
    assert len(runs) >= 1
    assert runs[0]["latency_ms"] == 300

    # 6. Log and resolve anomaly
    anomaly = db_client.log_anomaly(
        site_id=site_id,
        latency_ms=6000,
        error_message="Uptime Timeout"
    )
    assert anomaly["id"] is not None
    assert anomaly["resolved"] is False

    unresolved = db_client.get_unresolved_anomalies()
    assert any(a["id"] == anomaly["id"] for a in unresolved)

    resolved = db_client.resolve_anomaly(anomaly["id"])
    assert resolved["resolved"] is True

    unresolved_after = db_client.get_unresolved_anomalies()
    assert not any(a["id"] == anomaly["id"] for a in unresolved_after)

    # 7. Delete site
    success = db_client.delete_site(site_id)
    assert success is True

    assert db_client.get_site(site_id) is None

def test_mock_screenshot_saved_as_file_and_served():
    from fastapi.testclient import TestClient
    from api.main import app
    url = db_client.upload_screenshot("test-site", b"\x89PNG fake")
    assert url.startswith("/screenshots/test-site/")
    assert TestClient(app).get(url).content == b"\x89PNG fake"
