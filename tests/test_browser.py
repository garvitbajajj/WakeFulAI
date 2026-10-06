import pytest
from unittest.mock import AsyncMock, patch
from browser_agent.agent import execute_browser_plan

@pytest.mark.asyncio
async def test_execute_browser_plan_success():
    mock_page = AsyncMock()
    mock_page.title.return_value = "Test Suite Title"
    mock_page.screenshot.return_value = b"png-binary-data"

    # Context manager mock setup
    class MockSessionContext:
        async def __aenter__(self):
            return mock_page
        async def __aexit__(self, exc_type, exc, tb):
            pass

    with patch("browser_agent.session.session_manager.get_page", return_value=MockSessionContext()):
        # Mock action calls
        with patch("browser_agent.actions.navigate", return_value="Navigated to url"):
            with patch("browser_agent.actions.click", return_value="Clicked button"):
                with patch("browser_agent.actions.scroll", return_value="Scrolled"):
                    steps = [
                        {"action": "navigate", "url": "https://example.com"},
                        {"action": "click", "selector": "button.login"},
                        {"action": "scroll", "direction": "down", "amount": 300}
                    ]
                    result = await execute_browser_plan(steps, "test-site-id")
                    
                    assert result["status"] == "success"
                    assert len(result["results"]) == 3
                    assert result["error_message"] is None
                    assert result["screenshot_bytes"] == b"png-binary-data"

@pytest.mark.asyncio
async def test_execute_browser_plan_failure():
    mock_page = AsyncMock()
    mock_page.screenshot.return_value = b"error-screenshot-binary"

    class MockSessionContext:
        async def __aenter__(self):
            return mock_page
        async def __aexit__(self, exc_type, exc, tb):
            pass

    with patch("browser_agent.session.session_manager.get_page", return_value=MockSessionContext()):
        # Force navigation to fail
        with patch("browser_agent.actions.navigate", side_effect=Exception("Navigation Timeout")):
            steps = [
                {"action": "navigate", "url": "https://example.com"}
            ]
            result = await execute_browser_plan(steps, "test-site-id")
            
            assert result["status"] == "failure"
            assert "Navigation Timeout" in result["error_message"]
            assert result["screenshot_bytes"] == b"error-screenshot-binary"
