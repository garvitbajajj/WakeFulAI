from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from loguru import logger

class BrowserSessionManager:
    @asynccontextmanager
    async def get_page(self):
        async with async_playwright() as p:
            logger.info("Launching Playwright Chromium browser...")
            # Launch browser in headless mode
            browser: Browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            # Create context with realistic desktop viewport and user agent
            context: BrowserContext = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            # Define default timeout
            context.set_default_timeout(15000) # 15 seconds default timeout
            page: Page = await context.new_page()
            try:
                yield page
            except Exception as e:
                logger.error(f"Error during page session: {e}")
                raise e
            finally:
                logger.info("Closing Playwright context and browser...")
                await context.close()
                await browser.close()

session_manager = BrowserSessionManager()
