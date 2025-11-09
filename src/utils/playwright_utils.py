import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from playwright.async_api import Playwright, async_playwright, BrowserContext, Page

from src.constants import STATE_FILE

logger = logging.getLogger(__name__)

@asynccontextmanager
async def get_browser_context(
    p: Playwright,
    headless: bool,
    storage_state: Optional[Path] = None,
    save_on_exit: bool = False,
) -> AsyncGenerator[BrowserContext, None]:
    """
    An async context manager to provide a Playwright browser context.

    It loads authentication state from a file if it exists, and can save
    the state back to the file upon exit.
    """
    # Validate storage state parameters
    load_storage_state = None
    if storage_state is None:
        logger.info("Creating context without storage state")
    elif storage_state.exists():
        logger.info(f"Loading state from {storage_state}")
        load_storage_state = storage_state
    else:
        logger.info(f"Could not find storage state {storage_state}")

    save_storage_state = None
    if save_on_exit and storage_state is not None:
        save_storage_state = storage_state
    elif save_on_exit and storage_state is None:
        logger.warning("save_on_exit is True, but storage_state is None")

    # Launch browser and get context
    logger.info(f"Launching browser.")
    browser = await p.chromium.launch(headless=headless)
    context = await browser.new_context(storage_state=load_storage_state)
    logger.info("Browser is ready.")
    try:
        yield context
    finally:
        if save_storage_state is not None:
            logger.info(f"Saving browser state to {storage_state}...")
            storage_state.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=save_storage_state)
            logger.info("State saved successfully.")
        logger.info("Closing browser...")
        await context.close()
        await browser.close()
        logger.info("Browser closed.")

@asynccontextmanager
async def open_page(context: BrowserContext) -> AsyncGenerator[Page, Any]:
    """An async context manager to provide a Playwright page.

    It opens a new page and ensures it's closed upon exit.
    """
    page: Page | None = None
    try:
        page = await context.new_page()
        yield page
    finally:
        if page is not None and not page.is_closed():
            await page.close()

async def run_browser():
    async with async_playwright() as p:
        async with get_browser_context(p, headless=False, storage_state=STATE_FILE, save_on_exit=True) as context:
            async with open_page(context) as page:
                await page.pause()

if __name__ == "__main__":
    asyncio.run(run_browser())
