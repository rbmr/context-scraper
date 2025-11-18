import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext

from src.config import RunConfig, OutputType
from src.utils.playwright_utils import open_page

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    def __init__(self, config: RunConfig, temp_dir: Path):
        self.config = config
        self.temp_dir = temp_dir

    @abstractmethod
    async def handle(self, url: str, content: Optional[str], dest: Path, context: Optional[BrowserContext]) -> Optional[
        Path]:
        """Process a URL and return the path to the saved temporary file."""
        pass


class TextFetcher(BaseFetcher):
    async def handle(self, url: str, content: Optional[str], dest: Path, context: Optional[BrowserContext]) -> Optional[
        Path]:
        if not content:
            return None

        soup = BeautifulSoup(content, "lxml")
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
        text_content = soup.get_text(separator="\n\n")

        out_path = dest.with_suffix(".txt")
        out_path.write_text(text_content, encoding="utf-8")
        return out_path


class MarkdownFetcher(BaseFetcher):
    async def handle(self, url: str, content: Optional[str], dest: Path, context: Optional[BrowserContext]) -> Optional[
        Path]:
        # In a real scenario, you might run html2text here
        # For now, we save the raw content or lightly processed content
        if not content:
            return None
        out_path = dest.with_suffix(".md")
        out_path.write_text(content, encoding="utf-8")
        return out_path


class PdfRenderedFetcher(BaseFetcher):
    async def handle(self, url: str, content: Optional[str], dest: Path, context: Optional[BrowserContext]) -> Optional[
        Path]:
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
    if config.output_type == OutputType.PDF_RENDERED:
        return PdfRenderedFetcher(config, temp_dir)
    elif config.output_type == OutputType.MARKDOWN:
        return MarkdownFetcher(config, temp_dir)
    else:
        return TextFetcher(config, temp_dir)


async def run_fetcher_worker(
        queue: asyncio.Queue,
        merge_queue: asyncio.Queue,
        config: RunConfig,
        temp_dir: Path,
        context: Optional[BrowserContext]
):
    fetcher = get_fetcher_strategy(config, temp_dir)
    file_counter = 0

    while True:
        item = await queue.get()
        if item is None:
            # Propagate the finish signal to the merger
            await merge_queue.put(None)
            queue.task_done()
            break

        url, content = item
        dest = temp_dir / f"chunk_{file_counter:05d}"
        file_counter += 1

        try:
            path = await fetcher.handle(url, content, dest, context)
            if path:
                await merge_queue.put(path)
        except Exception as e:
            logger.error(f"Error in fetcher for {url}: {e}")

        queue.task_done()