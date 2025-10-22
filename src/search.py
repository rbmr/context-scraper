import asyncio
import logging
from typing import Set, Callable, Iterable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

async def async_get_links(client: httpx.AsyncClient, url: str) -> Set[str]:
    """
    Asynchronously gets all unique, absolute hyperlinks from a URL using httpx and BeautifulSoup.
    """
    logger.info(f"Scraping for links on: {url}")
    try:
        response = await client.get(url, headers=HEADERS, timeout=10.0)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            logger.warning(f"Skipping non-HTML content at {url} (Type: {content_type})")
            return set()

        links = set()
        soup = BeautifulSoup(response.content, 'lxml')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue

            absolute_link = urljoin(url, href).rstrip("/")
            if urlparse(absolute_link).scheme in ['http', 'https']:
                links.add(absolute_link)
        logger.debug(f"Found {len(links)} unique links on {url}.")
        return links
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} for URL {url}. Error: {e}")
        return set()
    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.error(f"Network/Request error for URL {url}. Error: {e}")
        return set()
    except Exception as e:
        logger.error(f"Unexpected error parsing URL {url}. Error: {e}")
        return set()


async def async_multi_get_links(
        client: httpx.AsyncClient,
        urls: Iterable[str],
        semaphore: asyncio.Semaphore
) -> Set[str]:
    """
    Creates and runs scraping tasks concurrently, constrained by the semaphore.
    """
    async def get_links_with_semaphore(url: str) -> Set[str]:
        """Wrapper to acquire semaphore before scraping."""
        async with semaphore:
            return await async_get_links(client, url)

    tasks = [get_links_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks)

    all_discovered_links = set()
    for res in results:
        all_discovered_links.update(res)

    return all_discovered_links

async def async_search(url: str, depth: int = 10, url_filter: Callable[[str], bool] | None = None, num_workers: int = 20) -> Set[str]:
    """Asynchronously follows links up to a specified depth using asyncio.

    This function performs a breadth-first search (BFS).

    num_workers controls asyncio.Semaphore to limit concurrency.
    """
    if depth <= 0:
        return set()
    url = url.rstrip('/')
    if url_filter is not None and not url_filter(url):
        logger.warning(f"Initial URL {url} does not match the filter.")
        return set()

    logger.info(f"Starting async crawl from {url} to depth {depth} with {num_workers} concurrent workers.")
    semaphore = asyncio.Semaphore(num_workers)
    discovered = {url}
    queue = {url}

    async with httpx.AsyncClient(follow_redirects=True, http2=True) as client:
        for current_depth in range(depth):
            if not queue:
                logger.info("No new URLs to visit. Stopping crawl.")
                break

            logger.info(f"Depth {current_depth + 1}/{depth}. Visiting {len(queue)} URLs.")

            # Retrieve all connected urls
            new_links = await async_multi_get_links(
                client=client,
                urls=queue,
                semaphore=semaphore,
            )

            # Remove urls that we have already visited
            new_links.difference_update(discovered)

            # Filter the urls
            if url_filter:
                urls_to_visit = {u for u in urls_to_visit if url_filter(u)}

            # Add the newly validated links.
            discovered.update(new_links)

            # Set them to be explored next
            queue = new_links

    logger.info(f"Crawl finished. Found a total of {len(discovered)} unique links.")
    return discovered