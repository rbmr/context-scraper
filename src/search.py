import logging
from typing import Set, Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import requests

logger = logging.getLogger(__name__)


def get_links(url: str) -> Set[str]:
    """Gets all unique, absolute hyperlinks from a URL using requests and BeautifulSoup."""
    logger.info(f"Scraping for links on: {url}")
    links = set()
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue

            absolute_link = urljoin(url, href)
            if urlparse(absolute_link).scheme in ['http', 'https']:
                links.add(absolute_link)

    except requests.RequestException as e:
        logger.error(f"Could not fetch or read URL {url}. Error: {e}")
        return set()

    logger.debug(f"Found {len(links)} unique links on {url}.")
    return links


def conc_get_links(urls: Iterable[str], num_workers: int = 1) -> Set[str]:
    """
    Concurrently fetches links from a set of URLs and returns the union of all links found.
    """
    all_discovered_links = set()
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_url = {executor.submit(get_links, u): u for u in urls}

        for future in as_completed(future_to_url):
            url_origin = future_to_url[future]
            try:
                all_discovered_links.update(future.result())
            except Exception as exc:
                logger.error(f"Error processing URL {url_origin}: {exc}")
    return all_discovered_links


def search(url: str, depth: int = 10, url_filter: Callable[[str], bool] = None, num_workers: int = 1) -> Set[str]:
    """
    Follows links up to a specified depth, returning the set of all unique, valid links found.
    This function performs a breadth-first search (BFS) by orchestrating layer-by-layer crawls.
    """
    if depth <= 0:
        return set()

    if url_filter and not url_filter(url):
        logger.warning(f"Initial URL {url} does not match the filter.")
        return set()

    logger.info(f"Starting crawl from {url} to depth {depth} with {num_workers} workers.")

    visited_urls = set()
    all_found_urls = {url}
    urls_to_visit = {url}

    for current_depth in range(depth):
        if not urls_to_visit:
            logger.info("No new URLs to visit. Stopping crawl.")
            break

        logger.info(f"Depth {current_depth + 1}/{depth}. Visiting {len(urls_to_visit)} URLs.")

        visited_urls.update(urls_to_visit)

        # Retrieve all connected urls
        urls_to_visit = conc_get_links(urls=urls_to_visit, num_workers=num_workers)

        # Remove urls that we have already visited
        urls_to_visit.difference_update(visited_urls)

        # Filter the urls
        if url_filter:
            urls_to_visit = {u for u in urls_to_visit if url_filter(u)}

        # Add the newly validated links to our master set.
        all_found_urls.update(urls_to_visit)

    logger.info(f"Crawl finished. Found a total of {len(all_found_urls)} unique links.")
    return all_found_urls