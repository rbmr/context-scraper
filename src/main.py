# main.py
import asyncio
import logging.config
import shutil
from pathlib import Path

from src.core.explore import explore
from src.core.processors import HttpxProcessor, PlaywrightPDFProcessor
from src.utils.pdf_utils import merge_pdfs
from src.constants import LOGGING_CONFIG, STATE_FILE, SRC_DIR

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


async def main():
    start_url = "https://publish.obsidian.md/git-doc/Start+here"
    base_domain = "https://publish.obsidian.md/git-doc/"
    output_pdf = SRC_DIR / "final_output.pdf"
    pdf_temp_dir = SRC_DIR / "temp_pdfs"

    # Define filter
    def url_filter(url: str) -> bool:
        return url.startswith(base_domain)

    # --- OPTION 1: Fast Scraping (Just finding links) ---
    # processor = HttpxProcessor(cookies_path=STATE_FILE)

    # --- OPTION 2: PDF Generation (Traversing & Printing) ---
    processor = PlaywrightPDFProcessor(
        output_dir=pdf_temp_dir,
        cookies_path=STATE_FILE
    )

    logger.info("Starting exploration...")

    # Run the explorer
    async with processor as p:

        results = await explore(
            start_urls=[start_url],
            processor=p,
            url_filter=url_filter,
            max_depth=5,
            concurrency=20
        )

    logger.info(f"Exploration complete. Generated {len(results)} items.")

    # Post-processing: Merge PDFs if we used the PDF processor
    if results and isinstance(results[0], Path):
        logger.info("Merging PDFs...")
        merge_pdfs(src=results, dest=output_pdf)  #

    shutil.rmtree(pdf_temp_dir)

if __name__ == "__main__":
    asyncio.run(main())