import logging
from typing import List, Set, Callable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup, SoupStrainer

from src.utils.async_utils import PBarConfig
from src.utils.httpx_utils import httpx_process_urls

logger = logging.getLogger(__name__)

def parse_links(content: str, url: str) -> set[str]:
    links = set()
    soup = soup = BeautifulSoup(content, "lxml", parse_only=SoupStrainer("a", href=True))
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        full_link = urljoin(url, href)
        parsed_url = urlparse(full_link)

        if parsed_url.scheme in ("http", "https"):
            # remove fragment
            cleaned_url = parsed_url._replace(fragment="")
            cleaned_link = urlunparse(cleaned_url)

            links.add(cleaned_link)

    return links

async def extract_links_task(response: httpx.Response) -> Set[str]:
    """
    Worker task: extracts links from a single response.
    """
    url = str(response.url)
    # Simple content type check
    ctype = response.headers.get("content-type", "")
    if "text/html" not in ctype:
        return set()

    return parse_links(response.text, url)


async def crawl_for_urls(
        client: httpx.AsyncClient,
        start_url: str,
        allowed_prefixes: List[str],
        max_depth: int,
        limit: int = 20
) -> List[str]:
    """
    Performs a BFS crawl to find all unique URLs matching the prefixes.
    """
    logger.info(f"Starting crawl from {start_url} (Depth: {max_depth})")

    def url_filter(u: str) -> bool:
        return any(u.startswith(p) for p in allowed_prefixes)

    discovered = {start_url}
    queue = {start_url}

    # Reuse pbar config style
    pbar_cfg = PBarConfig(desc="Crawling", unit="url", leave=True)

    for depth in range(max_depth):
        if not queue:
            break

        logger.info(f"Depth {depth + 1}: Processing {len(queue)} URLs...")

        # Fetch all pages in queue concurrently
        results = await httpx_process_urls(
            client=client,
            urls=list(queue),
            processing_func=extract_links_task,
            limit=limit,
            pbar=pbar_cfg
        )

        # Aggregate new links
        next_queue = set()
        for links in results:
            next_queue.update(links)

        # Filter
        next_queue = {u for u in next_queue if url_filter(u)}

        # Remove already seen
        next_queue.difference_update(discovered)

        discovered.update(next_queue)
        queue = next_queue

    logger.info(f"Crawl complete. Found {len(discovered)} unique URLs.")
    return sorted(list(discovered))