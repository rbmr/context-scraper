import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

import httpx
from playwright.async_api import BrowserContext
from bs4 import BeautifulSoup
from src.config import RunConfig, OutputType, MarkdownStrategy
from src.utils.playwright_utils import open_page

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    def __init__(self, config: RunConfig, temp_dir: Path):
        self.config = config
        self.temp_dir = temp_dir

    @abstractmethod
    async def handle(self, url: str, content: Optional[str], dest: Path, context: Optional[BrowserContext],
                     client: Optional[httpx.AsyncClient]) -> Optional[Path]:
        """Process a URL and return the path to the saved temporary file."""
        pass


class MarkdownFetcher(BaseFetcher):
    async def handle(self, url: str, content: Optional[str], dest: Path, context: Optional[BrowserContext],
                     client: Optional[httpx.AsyncClient]) -> Optional[Path]:
        strat = self.config.md_strategy
        out_path = dest.with_suffix(".md")

        # Helper to clean URL and add .md
        md_url = f"{url.rstrip('/')}.md"

        # 1. ONLY_HTML: Just dump the HTML we already have
        if strat == MarkdownStrategy.ONLY_HTML:
            if not content: return None
            out_path.write_text(content, encoding="utf-8")
            return out_path

        # 2. ONLY_MD: Try to fetch .md, ignore HTML content
        if strat == MarkdownStrategy.ONLY_MD:
            if not client: return None
            try:
                resp = await client.get(md_url, timeout=3.0)
                if resp.status_code == 200:
                    out_path.write_text(resp.text, encoding="utf-8")
                    return out_path
            except Exception:
                pass
            return None  # Failed to find MD, output nothing

        # 3. PRIORITIZE_MD: Try MD first, fallback to HTML
        if strat == MarkdownStrategy.PRIORITIZE_MD:
            # Try MD fetch
            if client:
                try:
                    resp = await client.get(md_url, timeout=2.0)
                    if resp.status_code == 200:
                        out_path.write_text(resp.text, encoding="utf-8")
                        return out_path
                except Exception:
                    pass

                    # Fallback to HTML if MD failed
            if content:
                out_path.write_text(content, encoding="utf-8")
                return out_path

            return None


class PdfRenderedFetcher(BaseFetcher):
    async def handle(self, url: str, content: Optional[str], dest: Path, context: Optional[BrowserContext],
                     client: Optional[httpx.AsyncClient]) -> Optional[Path]:
        if not context:
            logger.error("Browser context required for PDF Rendering")
            return None

        out_path = dest.with_suffix(".pdf")
        async with open_page(context) as page:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.pdf(path=str(out_path), format="A4")
                return out_path
            except Exception as e:
                logger.warning(f"PDF generation failed for {url}: {e}")
                return None


def get_fetcher_strategy(config: RunConfig, temp_dir: Path) -> BaseFetcher:
    if config.output_type == OutputType.PDF:
        return PdfRenderedFetcher(config, temp_dir)
    else:
        return MarkdownFetcher(config, temp_dir)


async def run_fetcher_worker(
        queue: asyncio.Queue,
        merge_queue: asyncio.Queue,
        config: RunConfig,
        temp_dir: Path,
        context: Optional[BrowserContext],
        client: Optional[httpx.AsyncClient]
):
    fetcher = get_fetcher_strategy(config, temp_dir)
    file_counter = 0

    while True:
        item = await queue.get()
        if item is None:
            # await merge_queue.put(None)
            queue.task_done()
            break

        url, content = item
        dest = temp_dir / f"chunk_{file_counter:05d}"
        file_counter += 1

        try:
            # Pass client to handle
            path = await fetcher.handle(url, content, dest, context, client)
            if path:
                await merge_queue.put(path)
        except Exception as e:
            logger.error(f"Error in fetcher for {url}: {e}")

        queue.task_done()