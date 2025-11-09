# src/processors.py

import logging
from typing import List, Callable, Coroutine, Any, TypeVar, Optional
import json

import httpx
from httpx import AsyncClient, Response, HTTPStatusError
from pathlib import Path

from src.utils.async_utils import run_async_tasks, PBarConfig

logger = logging.getLogger(__name__)
T = TypeVar('T')


def load_cookies_from_state(state_file: Path) -> Optional[httpx.Cookies]:
    """
    Loads cookies from a Playwright state.json file and converts them
    into an httpx.Cookies object.
    """
    if not state_file.exists():
        logger.warning(f"State file not found: {state_file}")
        return None

    logger.info(f"Loading cookies from state file: {state_file}")
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read or parse state file {state_file}: {e}")
        return None

    if "cookies" not in state or not state["cookies"]:
        logger.warning(f"No cookies found in state file: {state_file}")
        return None

    cookies = httpx.Cookies()
    for cookie in state["cookies"]:
        # The Playwright cookie format maps directly
        cookies.set(
            name=cookie['name'],
            value=cookie['value'],
            domain=cookie['domain'],
            path=cookie['path'],
        )

    logger.info(f"Successfully loaded {len(cookies)} cookies.")
    return cookies

async def httpx_process_url(
        client: AsyncClient,
        url: str,
        processing_func: Callable[[Response], Coroutine[Any, Any, T]],
        request_options: Optional[dict] = None,
) -> Optional[T]:
    """
    Internal worker task for processing a single URL with HTTPX.
    Fetches the URL and applies the processing_func to the response.
    """
    logger.debug(f"Processing (HTTPX): {url}")
    # Default options if none are provided
    if request_options is None:
        request_options = {"timeout": 20.0, "follow_redirects": True}

    try:
        response = await client.get(url, **request_options)
        response.raise_for_status()  # Raise an exception for 4xx/5xx

        # The provided async function does the actual work
        return await processing_func(response)
    except HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} for {url}")
        return None
    except httpx.RequestError as e:
        logger.error(f"HTTPX request error for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error processing {url}: {e}")
        return None

async def httpx_process_urls(
        client: AsyncClient,
        urls: List[str],
        processing_func: Callable[[Response], Coroutine[Any, Any, T]],
        limit: int = 0,
        pbar: Optional[PBarConfig] = None,
        request_options: Optional[dict] = None
) -> List[T]:
    """
    Given a list of links, loads them with HTTPX and applies
    an async function to the individual Response object.
    """
    if not urls:
        return []

    tasks = [
        httpx_process_url(client, url, processing_func, request_options)
        for url in urls
    ]

    results = await run_async_tasks(tasks, limit, pbar)

    return [res for res in results if res is not None]