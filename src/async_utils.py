# src/async_utils.py

import asyncio
import logging
from typing import List, TypeVar, Coroutine, Any
from tqdm.asyncio import tqdm as async_tqdm

logger = logging.getLogger(__name__)

T = TypeVar('T')

async def run_async_tasks(
        tasks: List[Coroutine[Any, Any, T]],
        limit: int,
        pbar: bool = False,
        desc: str = "Running tasks",
        unit: str = "task",
        leave: bool = False,
) -> List[T]:
    """
    Runs a list of awaitable tasks concurrently with a specified concurrency limit.
    """
    if not tasks:
        return []

    semaphore = asyncio.Semaphore(limit)

    async def worker(task: Coroutine[Any, Any, T]) -> T:
        """Wrapper to acquire semaphore before running a task."""
        async with semaphore:
            return await task

    # Wrap all tasks with the semaphore worker
    wrapped_tasks = [worker(task) for task in tasks]

    logger.info(
        f"Running {len(tasks)} tasks with a concurrency limit of {limit}..."
    )

    if pbar:
        return await async_tqdm.gather(
            *wrapped_tasks,
            desc=desc,
            total=len(wrapped_tasks),
            unit=unit,
            leave=leave,
        )
    else:
        return await asyncio.gather(*wrapped_tasks)