from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_system_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "scheduler_running": True}

def test_api_dashboard_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "WakeFulAI" in response.text

def test_api_crud_and_trigger_flow():
    # 1. Get all target sites
    response = client.get("/sites")
    assert response.status_code == 200
    sites = response.json()
    assert len(sites) >= 1  # Should contain pre-populated target site

    # 2. Add target site
    new_site = {
        "url": "https://httpbin.org/status/200",
        "name": "Integration Test Site",
        "session_flow": "1. Navigate",
        "check_interval_minutes": 15,
        "is_active": True
    }
    response = client.post("/sites", json=new_site)
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Integration Test Site"
    site_id = created["id"]

    # 3. Update target site
    response = client.put(f"/sites/{site_id}", json={"name": "Updated Integration Test"})
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Integration Test"

    # 4. Trigger Orchestrator Run for this site
    response = client.post("/sites/trigger", json={"site_id": site_id})
    assert response.status_code == 202
    assert "Orchestrator successfully run" in response.json()["detail"]

    # 5. Delete target site
    response = client.delete(f"/sites/{site_id}")
    assert response.status_code == 200
    assert response.json()["detail"] == "Site successfully deleted"

def test_sites_are_scoped_to_owner():
    from api.routes.sites import get_current_user
    user_a, user_b = "aaaaaaaa-0000-0000-0000-000000000000", "bbbbbbbb-0000-0000-0000-000000000000"
    try:
        app.dependency_overrides[get_current_user] = lambda: user_a
        site_id = client.post("/sites", json={"url": "https://example.com", "name": "A's site"}).json()["id"]
        assert [s["id"] for s in client.get("/sites").json()] == [site_id]

        app.dependency_overrides[get_current_user] = lambda: user_b
        assert client.get("/sites").json() == []
        assert client.put(f"/sites/{site_id}", json={"name": "hijacked"}).status_code == 404
        assert client.delete(f"/sites/{site_id}").status_code == 404
        assert client.get(f"/runs?site_id={site_id}").status_code == 404

        app.dependency_overrides[get_current_user] = lambda: user_a
        assert client.delete(f"/sites/{site_id}").status_code == 200
    finally:
        app.dependency_overrides.clear()
