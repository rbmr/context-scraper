from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from playwright.async_api import BrowserContext, Page

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

