# src/core/processors.py

import logging
from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Generic, List, Optional, Self, Tuple, TypeVar
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from src.utils.httpx_utils import load_cookies_from_state
from src.utils.playwright_utils import open_page

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AbstractProcessor(AbstractAsyncContextManager, ABC, Generic[T]):
    """
    Abstract base class for processing a single URL.
    """

    @abstractmethod
    async def process(self, url: str) -> Tuple[T, List[str]]:
        """
        Process a URL.

        Returns:
            Tuple containing:
            1. The result of the processing (e.g., PDF path, HTML content, or None).
            2. A list of raw links found on the page to be considered for the next layer.
        """
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        pass


class HttpxProcessor(AbstractProcessor[str]):
    """
    Lightweight processor using HTTPX. Returns the visited URL on success.
    """

    def __init__(self, cookies_path: Optional[Path] = None):
        self.cookies_path = cookies_path
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        cookies = (
            load_cookies_from_state(self.cookies_path)
            if self.cookies_path else None
        )
        # Add User-Agent to avoid blocking
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.client = httpx.AsyncClient(
            cookies=cookies,
            follow_redirects=True,
            timeout=20.0,
            headers=headers
        )
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.client is not None:
            await self.client.aclose()

    async def process(self, url: str) -> Tuple[Optional[str], List[str]]:
        if not self.client:
            raise RuntimeError("Client not initialized. Use 'async with'.")

        try:
            response = await self.client.get(url)
            response.raise_for_status()

            # Extract links using BeautifulSoup
            soup = BeautifulSoup(response.text, "lxml")
            links = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if href and not href.startswith(("#", "javascript:", "mailto:")):
                    links.append(urljoin(url, href))

            return url, links
        except Exception as e:
            logger.warning(f"Failed to process {url}: {e}")
            return None, []


class PlaywrightPDFProcessor(AbstractProcessor[Path]):
    """
    Heavyweight processor using Playwright. Saves PDFs and returns the Path.
    """

    def __init__(self, output_dir: Path, cookies_path: Optional[Path] = None):
        self.output_dir = output_dir
        self.cookies_path = cookies_path
        self.playwright = None
        self.browser = None
        self.context = None
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            storage_state=self.cookies_path
        )
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.context is not None:
            await self.context.close()
        if self.browser is not None:
            await self.browser.close()
        if self.playwright is not None:
            await self.playwright.stop()

    async def process(self, url: str) -> Tuple[Optional[Path], List[str]]:

        async with open_page(self.context) as page:
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Generate Safe Filename
            safe_name = (
                url.replace("https://", "")
                .replace("http://", "")
                .replace("/", "_")
                .replace("?", "_")
            )
            if len(safe_name) > 64:
                safe_name = safe_name[:64]
            output_path = self.output_dir / f"{safe_name}.pdf"

            # Save PDF
            await page.pdf(path=str(output_path), format="A4", print_background=True)

            # Extract Links via DOM evaluation
            # (More reliable than parsing HTML text for JS-heavy sites)
            links = await page.evaluate(
                """
                () => Array.from(document.querySelectorAll('a[href]'))
                           .map(a => a.href)
            """
            )

            return output_path, links

