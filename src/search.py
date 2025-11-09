import logging
from typing import Callable, Iterable, Set
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from httpx import AsyncClient, Response
from tqdm.auto import trange

from src.utils.async_utils import PBarConfig
from src.utils.httpx_utils import httpx_process_urls

logger = logging.getLogger(__name__)

def parse_links(content: str, url: str) -> set[str]:
    links = set()
    soup = BeautifulSoup(content, "lxml")
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
            # remove trailing slash
            cleaned_link = cleaned_link.rstrip("/")

            links.add(cleaned_link)

    return links

async def extract_links(response: Response) -> Set[str]:
    """
    Processing function for httpx_process_url.
    Parses links from an httpx response.
    """
    url = str(response.url)

    # Check content type
    content_type = response.headers.get("content-type")
    if content_type is None:
        logger.warning(f"Failed to get content type for URL {url}")
        return set()
    if "text/html" not in content_type:
        logger.warning(f"Skipping non-HTML content at {url} (Type: {content_type})")
        return set()

    # Parse content
    content = response.text
    links = parse_links(content, url)
    logger.debug(f"Found {len(links)} unique links on {url} (via HTTPX).")
    return links


async def multi_get_links(
    client: AsyncClient,
    urls: Iterable[str],
    limit: int,
    pbar: bool = False,
) -> Set[str]:
    """
    Creates and runs scraping tasks concurrently using httpx.
    """
    if not urls:
        return set()

    # Get the results
    results = await httpx_process_urls(
        client=client,
        urls=list(urls),
        processing_func=extract_links,
        limit=limit,
        pbar=(
            PBarConfig(desc="Scraping URLs", unit="URL", leave=False)
            if pbar
            else None
        )
    )

    # Flatten the results.
    all_discovered_links = set()
    for link_set in results:
        all_discovered_links.update(link_set)

    return all_discovered_links


async def async_search(
    client: AsyncClient,
    url: str,
    depth: int = 10,
    url_filter: Callable[[str], bool] | None = None,
    limit: int = 20,
    pbar: bool = False,
) -> Set[str]:
    """
    Asynchronously follows links up to a specified depth using HTTPX.
    """
    if depth <= 0:
        return set()
    url = url.rstrip("/")
    if url_filter is not None and not url_filter(url):
        logger.warning(f"Initial URL {url} does not match the filter.")
        return set()

    logger.info(
        f"Starting HTTPX crawl from {url} to depth {depth} with {limit} concurrent workers."
    )
    discovered = {url}
    queue = {url}

    depths = (
        trange(depth, desc="Crawling Depth", unit="depth", leave=True)
        if pbar else range(depth)
    )

    for current_depth in depths:
        if not queue:
            logger.info("No new URLs to visit. Stopping crawl.")
            break

        logger.info(f"Depth {current_depth + 1}/{depth}. Visiting {len(queue)} URLs.")

        new_links = await multi_get_links(
            client=client, urls=queue, limit=limit, pbar=pbar
        )

        # Filter the urls
        if url_filter:
            new_links = {u for u in new_links if url_filter(u)}

        # Remove urls that we have already visited
        new_links.difference_update(discovered)

        # Add the newly validated links.
        discovered.update(new_links)

        # Set them to be explored next
        queue = new_links

    logger.info(f"Crawl finished. Found a total of {len(discovered)} unique links.")
    return discovered
