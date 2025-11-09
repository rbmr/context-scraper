import asyncio
import logging.config

import httpx
from playwright.async_api import async_playwright

from src.utils.httpx_utils import load_cookies_from_state
from src.utils.playwright_utils import get_browser_context
from src.constants import LOGGING_CONFIG, SRC_DIR, STATE_FILE
from src.pdf import create_pdf_from_urls
from src.search import async_search

DEFAULT_OUTPUT = SRC_DIR / "output2.pdf"

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


async def main():

    start_url = "https://publish.obsidian.md/git-doc/Start+here"
    allowed_prefixes = "https://publish.obsidian.md/git-doc/"

    def url_filter(url: str) -> bool:
        """Checks if a URL starts with any of the allowed prefixes."""
        return url.startswith(allowed_prefixes)

    logger.info(f"Loading cookies from {STATE_FILE}")
    cookies = load_cookies_from_state(STATE_FILE)

    logger.info("Starting fast HTTPX-based search...")
    async with httpx.AsyncClient(cookies=cookies, follow_redirects=True, timeout=20.0) as client:
        # Add a User-Agent, as many sites block default httpx requests
        client.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

        urls = await async_search(
            client=client, url=start_url,
            depth=5, url_filter=url_filter,
            limit=20, pbar=True,
        )

    if not urls:
        logger.warning("No URLs found by the search. Exiting.")
        return

    urls_list = sorted(urls)
    logger.info(f"Search complete. Converting {len(urls_list)} URLs to PDF.")

    logger.info("Starting Playwright-based PDF creation...")
    async with async_playwright() as p:
        async with get_browser_context(p, storage_state=STATE_FILE, headless=True, save_on_exit=False) as context:
            await create_pdf_from_urls(
                browser=context,urls=urls_list,
                output_file=DEFAULT_OUTPUT,
                limit=10, pbar=True,
            )

if __name__ == "__main__":
    asyncio.run(main())
