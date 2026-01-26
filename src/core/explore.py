# src/core/explorer.py
import logging
from typing import Callable, List, Optional
from urllib.parse import urlparse, urlunparse

from src.core.processors import AbstractProcessor, T
from src.utils.async_utils import PBarConfig, run_async_tasks

logger = logging.getLogger(__name__)


def standardize_url(url: str) -> str:
    """
    Standardizes URL: removes query/fragments and trailing slashes.
    """
    # Parse the url components
    parsed = urlparse(url)

    # Reconstruct without params, query, or fragment
    clean = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),  # Remove trailing slash
            "","",""
        )
    )
    return clean.lower()


async def explore(
    start_urls: List[str],
    processor: AbstractProcessor[T],
    url_filter: Optional[Callable[[str], bool]] = None,
    max_depth: int = 3,
    concurrency: int = 10,
) -> List[T]:
    """
    Executes the BFS traversal.
    """
    if max_depth <= 0:
        raise ValueError("max_depth must be greater than 0.")

    # Determine url filter.
    if url_filter is not None:
        _url_filter = lambda u: u.startswith("http") and url_filter(u)
    else:
        _url_filter = lambda u: u.startswith("http")

    # Initialize queue with standardized start URLs
    visited: set[str] = set()
    queue: list[str] = []
    for url in start_urls:
        std_url = standardize_url(url)
        if std_url not in visited and _url_filter(std_url):
            queue.append(std_url)
            visited.add(std_url)

    # Run the main BFS loop.
    results: List[T] = []
    depth = 0
    while queue:
        logger.info(f"Depth {depth + 1}/{max_depth}: Processing {len(queue)} URLs...")

        # Process current layer concurrently
        task_results = await run_async_tasks(
            [processor.process(url) for url in queue],
            limit=concurrency,
            pbar=PBarConfig(desc=f"Layer {depth + 1}", unit="url"),
        )

        # Add the results to the list
        for res, _ in task_results:
            results.append(res)

        # Skip processing links if max depth reached.
        if depth >= max_depth - 1:
            break

        queue.clear()
        for _, raw_urls in task_results:

            # Filter and queue next layer
            for raw_url in raw_urls:
                std_url = standardize_url(raw_url)
                if std_url not in visited and _url_filter(std_url):
                    visited.add(std_url)
                    queue.append(std_url)

        depth += 1

    return results
