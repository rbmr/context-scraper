import asyncio
import tempfile
import logging
from pathlib import Path
from typing import List, Optional

from playwright.async_api import async_playwright, Browser, Page
from pypdf import PdfWriter

from src.constants import SRC_DIR

DEFAULT_OUTPUT = SRC_DIR / "output.pdf"
logger = logging.getLogger(__name__)

def merge_pdfs(src: List[Path], dest: Path) -> None:
    """Merge multiple PDF files into a single PDF."""
    pdf_merger = PdfWriter()

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

    for src_path in valid_sources:
        pdf_merger.append(src_path)

    try:
        with open(dest, "wb") as f_out:
            pdf_merger.write(f_out)
        logger.info(f"Final PDF saved to: {dest}")
    except Exception as e:
        logger.error(f"Could not write final PDF file. Error: {e}")
    finally:
        pdf_merger.close()


async def _generate_pdf_on_page(page: Page, url: str, dest: Path):
    """Core logic to navigate and print a PDF from a URL on a given page."""
    await page.goto(url, wait_until="networkidle", timeout=60_000)
    await page.wait_for_timeout(500)
    await page.pdf(
        path=str(dest),
        format="A4",
        print_background=True
    )


async def create_pdf_from_url(url: str, dest: Path, browser: Optional[Browser] = None) -> Optional[Path]:
    """
    Creates a PDF from a URL.
    If a browser instance is provided, it's used to create a new page.
    Otherwise, a new browser is created for this single operation.
    Returns the destination path on success, None on failure.
    """
    logger.info(f"Creating PDF from URL: {url}")
    try:
        if browser:
            page = await browser.new_page()
            await _generate_pdf_on_page(page, url, dest)
            await page.close()
        else:
            async with async_playwright() as p:
                browser_instance = await p.chromium.launch()
                page = await browser_instance.new_page()
                await _generate_pdf_on_page(page, url, dest)
                await browser_instance.close()

        logger.info(f"Successfully created PDF: {dest}")
        return dest
    except Exception as e:
        logger.error(f"Failed to create PDF from URL {url}. Error: {e}")
        return None


async def create_pdf_from_urls(urls: List[str], output_file: Path = DEFAULT_OUTPUT):
    """Creates multiple PDFs from a list of URLs in parallel and concatenates them."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            tasks = []
            for i, url in enumerate(urls):
                temp_pdf_path = temp_dir_path / f"temp_{i}.pdf"
                tasks.append(create_pdf_from_url(url, temp_pdf_path, browser=browser))

            logger.info(f"Creating {len(tasks)} PDFs in parallel...")
            results = await asyncio.gather(*tasks)
            logger.info("All PDF creation tasks complete.")

        temp_pdf_paths = [path for path in results if path is not None]

        if not temp_pdf_paths:
            logger.warning("No PDFs were successfully created from the provided URLs.")
            return

        logger.info(f"Merging {len(temp_pdf_paths)} successfully created PDFs...")
        merge_pdfs(src=temp_pdf_paths, dest=output_file)
