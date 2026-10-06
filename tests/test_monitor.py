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
