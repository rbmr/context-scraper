import logging
import asyncio
from typing import List, Set, Tuple, Optional
from urllib.parse import urljoin, urlparse, urlunparse
import httpx
from bs4 import BeautifulSoup, SoupStrainer

from src.utils.async_utils import PBarConfig
from src.utils.httpx_utils import httpx_process_urls

logger = logging.getLogger(__name__)


def parse_links(content: str, url: str) -> set[str]:
    links = set()
    soup = BeautifulSoup(content, "lxml", parse_only=SoupStrainer("a", href=True))
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_link = urljoin(url, href)
        parsed_url = urlparse(full_link)
        if parsed_url.scheme in ("http", "https"):
            cleaned_url = parsed_url._replace(fragment="")
            links.add(urlunparse(cleaned_url))
    return links


async def extract_links_task(response: httpx.Response) -> Tuple[str, Set[str], Optional[str]]:
    url = str(response.url)
    ctype = response.headers.get("content-type", "")
    if "text/html" not in ctype:
        return url, set(), None
    return url, parse_links(response.text, url), response.text


async def run_crawler(
        client: httpx.AsyncClient,
        start_url: str,
        allowed_prefixes: List[str],
        max_urls: int,
        fetch_queue: asyncio.Queue,
        limit: int = 20
):
    logger.info(f"Starting crawl from {start_url} (Max URLs: {max_urls})")

    def url_filter(u: str) -> bool:
        return any(u.startswith(p) for p in allowed_prefixes)

    discovered = {start_url}
    to_visit = {start_url}
    visited_count = 0

    pbar_cfg = PBarConfig(desc="Crawling", unit="url", leave=True)

    while to_visit and visited_count < max_urls:
        # Grab a batch of URLs to process, up to the remaining limit
        batch_size = min(len(to_visit), max_urls - visited_count)
        current_batch = list(to_visit)[:batch_size]

        # Remove current batch from to_visit immediately so we don't loop
        to_visit = set(list(to_visit)[batch_size:])

        results = await httpx_process_urls(
            client=client,
            urls=current_batch,
            processing_func=extract_links_task,
            limit=limit,
            pbar=pbar_cfg
        )

        for url, links, content in results:
            visited_count += 1
            # Push to Fetcher Pipeline
            if content:
                await fetch_queue.put((url, content))

            # Process new links
            new_links = {u for u in links if url_filter(u) and u not in discovered}
            discovered.update(new_links)
            to_visit.update(new_links)

    logger.info(f"Crawl complete. Visited {visited_count} URLs.")
    # Signal end of crawling to the fetcher
    await fetch_queue.put(None)