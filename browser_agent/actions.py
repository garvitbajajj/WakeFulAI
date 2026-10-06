import asyncio
from playwright.async_api import Page
from loguru import logger

async def navigate(page: Page, url: str) -> str:
    logger.info(f"Navigating to {url}")
    await page.goto(url, wait_until="networkidle", timeout=20000)
    title = await page.title()
    logger.info(f"Successfully loaded. Page title: '{title}'")
    return f"Navigated to {url}. Title: {title}"

async def click(page: Page, selector: str) -> str:
    logger.info(f"Clicking element with selector '{selector}'")
    # Wait for element to be visible
    await page.wait_for_selector(selector, state="visible", timeout=5000)
    await page.click(selector)
    # Wait briefly for transition
    await asyncio.sleep(1)
    return f"Clicked element matching '{selector}'"

async def fill_form(page: Page, selector: str, value: str) -> str:
    logger.info(f"Filling input '{selector}' with value '{value}'")
    await page.wait_for_selector(selector, state="visible", timeout=5000)
    await page.fill(selector, value)
    return f"Filled input '{selector}' with value"

async def scroll(page: Page, direction: str, amount: int) -> str:
    logger.info(f"Scrolling page {direction} by {amount}px")
    if direction.lower() == "down":
        await page.evaluate(f"window.scrollBy(0, {amount})")
    elif direction.lower() == "up":
        await page.evaluate(f"window.scrollBy(0, -{amount})")
    else:
        raise ValueError("Direction must be 'up' or 'down'")
    await asyncio.sleep(1)
    return f"Scrolled {direction} by {amount}px"

async def screenshot(page: Page) -> bytes:
    logger.info("Capturing page screenshot")
    # Take screenshot as PNG bytes
    screenshot_bytes = await page.screenshot(type="png", full_page=False)
    return screenshot_bytes

async def get_page_title(page: Page) -> str:
    title = await page.title()
    return title
