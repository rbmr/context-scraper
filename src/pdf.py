import asyncio
import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from playwright.async_api import BrowserContext, Page
from pypdf import PdfWriter
from tqdm.asyncio import tqdm as async_tqdm

from src.async_utils import run_async_tasks
from src.browser import open_page
from src.constants import SRC_DIR

DEFAULT_OUTPUT = SRC_DIR / "output.pdf"
logger = logging.getLogger(__name__)


def merge_pdfs(src: List[Path], dest: Path) -> None:
    """Merge multiple PDF files into a single PDF."""

    # Validate input sources
    valid_sources = []
    for pdf_src in src:
        if not pdf_src.is_file():
            logger.warning(f"Source file {pdf_src} is not a file, ignoring.")
            continue
        if not pdf_src.suffix == ".pdf":
            logger.warning(f"Source file {pdf_src} is not a PDF, ignoring.")
            continue
        valid_sources.append(pdf_src)

    if not valid_sources:
        logger.warning(f"No valid source files found, ignoring.")
        return

    # Merge and save
    pdf_merger = PdfWriter()
    for src_path in valid_sources:
        try:
            pdf_merger.append(src_path)
        except Exception as e:
            logger.error(f"Could not append {src_path}. Error: {e}")

    try:
        with open(dest, "wb") as f_out:
            pdf_merger.write(f_out)
        logger.info(f"Final PDF saved to: {dest}")
    except Exception as e:
        logger.error(f"Could not write final PDF file. Error: {e}")
    finally:
        pdf_merger.close()


async def create_pdf_from_url(
    browser: BrowserContext,
    url: str,
    dest: Path,
) -> Optional[Path]:
    """
    Creates a PDF from a URL.
    Returns the destination path on success, None on failure.
    """
    logger.info(f"Creating PDF from URL: {url}")
    async with open_page(browser) as page:
        try:
            await page.goto(url, wait_until="networkidle", timeout=60_000)
            await page.pdf(path=str(dest), format="A4", print_background=True)
            logger.info(f"Successfully created PDF: {dest}")
            return dest
        except Exception as e:
            logger.error(f"Failed to create PDF from URL {url}. Error: {e}")
            return None

async def create_pdf_from_urls(
    browser: BrowserContext,
    urls: List[str],
    output_file: Path = DEFAULT_OUTPUT,
    pbar: bool = False,
    limit: int = 20,
):
    """Creates multiple PDFs from a list of URLs in parallel and concatenates them."""
    with tempfile.TemporaryDirectory() as temp_dir:
        logging.info(f"Using temporary directory for PDFs: {temp_dir}")
        temp_dir_path = Path(temp_dir)

        tasks = []
        for i, url in enumerate(urls):
            temp_pdf_path = temp_dir_path / f"temp_{i}.pdf"
            tasks.append(create_pdf_from_url(browser, url, temp_pdf_path))

        results = await run_async_tasks(
            tasks,
            limit=limit,
            pbar=pbar,
            desc="Creating PDFs",
            unit="pdf",
            leave=False
        )

        logger.info("All PDF creation tasks complete.")

        temp_pdf_paths = [path for path in results if path is not None]

        if not temp_pdf_paths:
            logger.warning("No PDFs were successfully created from the provided URLs.")
            return

        logger.info(f"Merging {len(temp_pdf_paths)} successfully created PDFs...")
        merge_pdfs(src=temp_pdf_paths, dest=output_file)
