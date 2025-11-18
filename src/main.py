# src/main.py
import asyncio
import logging.config
import shutil
import tempfile
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from src.cli import parse_args, get_user_inputs, interactive_auth_check
from src.config import RunConfig, OutputType
from src.constants import LOGGING_CONFIG, STATE_FILE
from src.crawler import crawl_for_urls
from src.fetcher import ContentFetcher
from src.merger import Merger
from src.utils.playwright_utils import get_browser_context
from src.utils.httpx_utils import load_cookies_from_state

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


async def run_process(config: RunConfig):
    logger.info(f"Starting job: {config.output_name}")
    logger.info(f"Target: {config.start_url} (Matches: {config.allowed_prefixes})")

    # 1. Setup HTTPX Client (Fast Crawling)
    cookies = load_cookies_from_state(STATE_FILE)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    async with httpx.AsyncClient(cookies=cookies, follow_redirects=True, timeout=20.0, headers=headers) as client:

        # 2. Crawl (Discovery Phase)
        urls = await crawl_for_urls(
            client=client,
            start_url=config.start_url,
            allowed_prefixes=config.allowed_prefixes,
            max_depth=config.max_depth,
            limit=config.concurrency_limit
        )

        if not urls:
            logger.warning("No URLs found.")
            return

        # 3. Fetch (Data Gathering Phase)
        # We use a temporary directory for intermediate files to manage memory and safety
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            fetcher = ContentFetcher(config, temp_dir)

            # If PDF-Rendered, we need Playwright
            if config.output_type == OutputType.PDF_RENDERED:
                async with async_playwright() as p:
                    async with get_browser_context(p, headless=True, storage_state=STATE_FILE) as context:
                        files = await fetcher.process_urls(urls, client, context)
            else:
                # Pure HTTPX fetching for text/md
                files = await fetcher.process_urls(urls, client, None)

            # 4. Merge (Output Phase)
            if files:
                merger = Merger(config)
                merger.merge(files)
            else:
                logger.warning("No content was successfully fetched.")


async def main():
    # Parse CLI Flags
    args = parse_args()

    # Interactive Setup
    try:
        config = get_user_inputs(args)

        # Ask for auth update
        await interactive_auth_check()

        # Run
        await run_process(config)

    except KeyboardInterrupt:
        logger.info("Aborted by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())