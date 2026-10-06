import pytest
from unittest.mock import AsyncMock, patch
import httpx
from monitor_agent.checker import perform_health_check

@pytest.mark.asyncio
async def test_perform_health_check_success():
    with patch("httpx.AsyncClient.get") as mock_get:
        import datetime
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.elapsed = datetime.timedelta(seconds=0.150)  # 150ms
        mock_response.content = b"Welcome to My App"
        mock_get.return_value = mock_response

        # Disable Z-score check fetching by mocking get_recent_runs to return empty list
        with patch("db.db_client.get_recent_runs", return_value=[]):
            result = await perform_health_check("https://myapp.onrender.com", "mock-site-id")
            
            assert result["status"] == "success"
            assert result["latency_ms"] == 150
            assert result["status_code"] == 200
            assert result["error_message"] is None

@pytest.mark.asyncio
async def test_perform_health_check_anomaly_status():
    with patch("httpx.AsyncClient.get") as mock_get:
        import datetime
        mock_response = AsyncMock()
        mock_response.status_code = 503
        mock_response.elapsed = datetime.timedelta(seconds=0.050)
        mock_response.content = b"Service Unavailable"
        mock_get.return_value = mock_response

        with patch("db.db_client.get_recent_runs", return_value=[]):
            result = await perform_health_check("https://myapp.onrender.com", "mock-site-id")
            
            assert result["status"] == "anomaly"
            assert result["status_code"] == 503
            assert "Non-2xx" in result["error_message"]

@pytest.mark.asyncio
async def test_perform_health_check_timeout():
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
        with patch("db.db_client.get_recent_runs", return_value=[]):
            result = await perform_health_check("https://myapp.onrender.com", "mock-site-id")
            
            assert result["status"] == "anomaly"
            assert "HTTP Request failed" in result["error_message"]

@pytest.mark.asyncio
async def test_perform_health_check_zscore_anomaly():
    with patch("httpx.AsyncClient.get") as mock_get:
        import datetime
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.elapsed = datetime.timedelta(seconds=3.0)
        mock_response.content = b"ok"
        mock_get.return_value = mock_response

        history = [{"agent_type": "monitor", "status": "success", "latency_ms": ms} for ms in (200, 210, 190, 205, 195, 200)]
        with patch("db.db_client.get_recent_runs", return_value=history) as mock_runs:
            result = await perform_health_check("https://myapp.onrender.com", "mock-site-id")

            mock_runs.assert_called_with(site_id="mock-site-id", limit=10, agent_type="monitor")
            assert result["status"] == "anomaly"
            assert result["is_zscore_anomaly"] is True

@pytest.mark.asyncio
@pytest.mark.parametrize("status,open_anomalies,expect_alert,expect_recovery", [
    ("anomaly", [], True, False),                  # first failure -> alert
    ("anomaly", [{"id": "a1"}], False, False),     # still down -> no repeat alert
    ("success", [{"id": "a1"}], False, True),      # back up -> recovery + auto-resolve
    ("success", [], False, False),                 # healthy -> nothing
])
async def test_monitor_alerts_once_per_incident(status, open_anomalies, expect_alert, expect_recovery):
    from monitor_agent import agent
    check = {"status": status, "latency_ms": 100, "status_code": 200, "response_size": 1, "error_message": None}
    site = {"id": "s1", "name": "Site", "url": "https://example.com"}
    with patch.object(agent, "perform_health_check", AsyncMock(return_value=check)), \
         patch.object(agent.db_client, "log_run"), \
         patch.object(agent.db_client, "get_unresolved_anomalies", return_value=open_anomalies), \
         patch.object(agent, "trigger_anomaly_alert", AsyncMock()) as alert, \
         patch.object(agent, "trigger_recovery_alert", AsyncMock()) as recovery:
        await agent.run_monitor_agent(site)
        assert alert.called is expect_alert
        assert recovery.called is expect_recovery
