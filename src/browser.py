import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import Playwright, async_playwright

from src.constants import STATE_FILE

logger = logging.getLogger(__name__)

@asynccontextmanager
async def get_browser_context(
        p: Playwright,
        headless: bool,
        storage_state: Path = STATE_FILE,
        save_on_exit: bool = False
):
    """
    An async context manager to provide a Playwright browser context.

    It loads authentication state from a file if it exists, and can save
    the state back to the file upon exit.
    """
    logger.info(f"Launching browser.")
    load_storage_state = None
    if storage_state.exists():
        logger.info(f"Loading state from {storage_state}")
        load_storage_state = storage_state
    else:
        logger.info(f"Could not find storage state {storage_state}")
    browser = await p.chromium.launch(headless=headless)
    context = await browser.new_context(storage_state=load_storage_state)
    logger.info("Browser is ready.")
    try:
        yield context
    finally:
        if save_on_exit:
            logger.info(f"Saving browser state to {storage_state}...")
            storage_state.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=STATE_FILE)
            logger.info("State saved successfully.")
        logger.info("Closing browser...")
        await context.close()
        await browser.close()
        logger.info("Browser closed.")

async def main():
    async with async_playwright() as p:
        async with get_browser_context(p, headless=False, save_on_exit=True) as context:
            page = await context.new_page()
            await page.pause()

if __name__ == "__main__":
    asyncio.run(main())