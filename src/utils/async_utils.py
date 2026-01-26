# src/async_utils.py

import asyncio
import logging
from dataclasses import asdict, dataclass
from typing import Any, Coroutine, List, Optional, TypeVar

from tqdm.asyncio import tqdm as async_tqdm

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class PBarConfig:
    """A typed configuration for tqdm progress bars."""

    desc: str
    unit: str
    leave: bool = False
    colour: Optional[str] = None


def limit_conc(
    tasks: List[Coroutine[Any, Any, T]], limit: int
) -> List[Coroutine[Any, Any, T]]:
    """Wraps a list of tasks using the same semaphore with a specified limit."""
    semaphore = asyncio.Semaphore(limit)

    async def worker(task: Coroutine[Any, Any, T]) -> T:
        """Wrapper to acquire semaphore before running a task."""
        async with semaphore:
            return await task

    return [worker(task) for task in tasks]


async def run_async_tasks(
    tasks: List[Coroutine[Any, Any, T]],
    limit: int = 0,
    pbar: Optional[PBarConfig] = None,
) -> List[T]:
    """
    Runs a list of awaitable tasks concurrently with a specified concurrency limit.
    """
    if limit < 0:
        raise ValueError("limit must non-negative")

    if not tasks:
        return []

    if limit > 0:
        tasks = limit_conc(tasks, limit)
        logger.info(
            f"Running {len(tasks)} tasks with a concurrency limit of {limit}..."
        )
    else:
        logger.info(f"Running {len(tasks)} tasks concurrently...")

    if pbar is None:
        return await asyncio.gather(*tasks)

    kwargs = asdict(pbar)
    kwargs["total"] = len(tasks)
    return await async_tqdm.gather(*tasks, **kwargs)
