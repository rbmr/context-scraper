import asyncio
import logging
from typing import Set, Callable, Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext, Page, Error as PlaywrightError

logger = logging.getLogger(__name__)

def parse_links(content: str, url: str) -> set[str]:
    links = set()
    soup = BeautifulSoup(content, 'lxml')
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            continue
        absolute_link = urljoin(url, href).rstrip("/")
        if urlparse(absolute_link).scheme in ['http', 'https']:
            links.add(absolute_link)
    return links

async def async_get_links(context: BrowserContext, url: str) -> Set[str]:
    """
    Asynchronously gets all unique, absolute hyperlinks from a URL using httpx and BeautifulSoup.
    """
    logger.info(f"Scraping for links on: {url}")
    page: Page | None = None
    try:
        page = await context.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        if not response:
            logger.error(f"Failed to get response for URL {url}")
            return set()
        if not response.ok:
            logger.error(f"HTTP error {response.status} for URL {url}")
            return set()
        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type:
            logger.warning(f"Skipping non-HTML content at {url} (Type: {content_type})")
            return set()
        content = await page.content()
        links = parse_links(content, url)
        logger.debug(f"Found {len(links)} unique links on {url}.")
        return links
    except PlaywrightError as e:
        logger.error(f"Playwright error for URL {url}. Error: {e}")
        return set()
    except Exception as e:
        logger.error(f"Unexpected error parsing URL {url}. Error: {e}")
        return set()
    finally:
        if page and not page.is_closed():
            await page.close()

async def async_multi_get_links(
        context: BrowserContext,
        urls: Iterable[str],
        semaphore: asyncio.Semaphore
) -> Set[str]:
    """
    Creates and runs scraping tasks concurrently, constrained by the semaphore.
    """
    async def get_links_with_semaphore(url: str) -> Set[str]:
        """Wrapper to acquire semaphore before scraping."""
        async with semaphore:
            return await async_get_links(context, url)

    tasks = [get_links_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks)

    all_discovered_links = set()
    for res in results:
        all_discovered_links.update(res)

    return all_discovered_links

async def async_search(
        context: BrowserContext,
        url: str, depth: int = 10,
        url_filter: Callable[[str], bool] | None = None,
        num_workers: int = 20
) -> Set[str]:
    """Asynchronously follows links up to a specified depth using Playwright."""
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

    for current_depth in range(depth):
        if not queue:
            logger.info("No new URLs to visit. Stopping crawl.")
            break

        logger.info(f"Depth {current_depth + 1}/{depth}. Visiting {len(queue)} URLs.")

        # Retrieve all connected urls
        new_links = await async_multi_get_links(
            context=context,
            urls=queue,
            semaphore=semaphore,
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