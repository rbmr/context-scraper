import asyncio
import logging.config
import tempfile
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from src.cli import parse_args, get_user_inputs, interactive_auth_check
from src.config import RunConfig, OutputType
from src.constants import LOGGING_CONFIG, STATE_FILE
from src.utils.playwright_utils import get_browser_context
from src.utils.httpx_utils import load_cookies_from_state
from src.fetcher import run_fetcher_worker
from src.merger import run_merger_worker
from src.crawler import run_crawler

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)



async def run_process(config: RunConfig):
    logger.info(f"Starting job: {config.output_name}")

    # 1. Setup Queues
    fetch_queue = asyncio.Queue()
    merge_queue = asyncio.Queue()

    # 2. Setup Resources
    cookies = load_cookies_from_state(STATE_FILE)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safar/537.36"
    }

    async with httpx.AsyncClient(cookies=cookies, follow_redirects=True, timeout=20.0, headers=headers) as client:
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)

            # 3. Define Pipeline Tasks

            # A. Crawler (Producer)
            crawler_task = asyncio.create_task(
                run_crawler(
                    client=client,
                    start_url=config.start_url,
                    allowed_prefixes=config.allowed_prefixes,
                    max_urls=config.max_urls,
                    fetch_queue=fetch_queue,
                    limit=config.concurrency_limit
                )
            )

            # B. Fetcher (Transformer)
            # Needs Playwright context if PDF output is requested
            async def launch_fetcher():
                if config.output_type == OutputType.PDF:
                    async with async_playwright() as p:
                        async with get_browser_context(p, headless=True, storage_state=STATE_FILE) as context:
                            # Pass 'client' here
                            await run_fetcher_worker(fetch_queue, merge_queue, config, temp_dir, context, client)
                else:
                    await run_fetcher_worker(fetch_queue, merge_queue, config, temp_dir, None, client)

            fetcher_tasks = [
                asyncio.create_task(launch_fetcher())
                for _ in range(config.concurrency_limit)
            ]

            # C. Merger (Consumer)
            merger_task = asyncio.create_task(run_merger_worker(merge_queue, config))

            # 4. Wait for pipeline completion
            # We await the crawler first. Once it finishes, it puts None in fetch_queue.
            await crawler_task
            logger.info("Crawler finished. Waiting for fetcher...")

            # Signal fetchers to finish
            for _ in range(config.concurrency_limit - 1):
                await fetch_queue.put(None)

            # Fetcher sees None, finishes work, puts None in merge_queue.
            await asyncio.gather(*fetcher_tasks)
            logger.info("Fetcher finished. Waiting for merger...")

            # Signal merger to finish
            await merge_queue.put(None)

            # Merger sees None, flushes, and exits.
            await merger_task
            logger.info("Merger finished. Job Complete.")
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