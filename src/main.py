import asyncio
import logging.config

from src.constants import SRC_DIR, LOGGING_CONFIG
from src.pdf import create_pdf_from_urls
from src.search import search

DEFAULT_OUTPUT = SRC_DIR / "output.pdf"

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


async def main():
    """
    Crawls the belastingdienst.nl website for pages related to 'huurtoeslag'
    and 'toeslagen', then merges them all into a single PDF.
    """
    start_url = "https://www.belastingdienst.nl/wps/wcm/connect/nl/huurtoeslag/"
    allowed_prefixes = (
        "https://www.belastingdienst.nl/wps/wcm/connect/nl/huurtoeslag/",
        "https://www.belastingdienst.nl/wps/wcm/connect/nl/toeslagen/",
    )

    def url_filter(url: str) -> bool:
        """Checks if a URL starts with any of the allowed prefixes."""
        return url.startswith(allowed_prefixes)

    logger.info(f"Starting crawl from: {start_url}")

    # Run the synchronous search function in a separate thread to avoid blocking the event loop.
    # We set a reasonable depth and number of workers for the crawl.
    found_urls = await asyncio.to_thread(
        search,
        url=start_url,
        depth=5,
        url_filter=url_filter,
        num_workers=10
    )

    if not found_urls:
        logger.warning("No URLs found matching the criteria. Exiting.")
        return

    # Sort the URLs to ensure a deterministic order in the final PDF.
    urls_to_process = sorted(list(found_urls))
    logger.info(f"Found {len(urls_to_process)} URLs to convert to PDF.")

    logger.info("Starting PDF creation and merge process...")
    await create_pdf_from_urls(urls=urls_to_process, output_file=DEFAULT_OUTPUT)
    logger.info("Process finished.")


if __name__ == '__main__':
    asyncio.run(main())