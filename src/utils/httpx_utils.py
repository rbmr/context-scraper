# src/processors.py

import json
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine, List, Optional, TypeVar

import httpx
from httpx import AsyncClient, HTTPStatusError, Response

from src.utils.async_utils import PBarConfig, run_async_tasks

logger = logging.getLogger(__name__)
T = TypeVar("T")


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
        with open(state_file, "r") as f:
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
            name=cookie["name"],
            value=cookie["value"],
            domain=cookie["domain"],
            path=cookie["path"],
        )

    logger.info(f"Successfully loaded {len(cookies)} cookies.")
    return cookies