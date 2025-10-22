import asyncio
import logging.config

from playwright.async_api import async_playwright

from src.browser import get_browser_context
from src.constants import SRC_DIR, LOGGING_CONFIG
from src.pdf import create_pdf_from_urls
from src.search import async_search

DEFAULT_OUTPUT = SRC_DIR / "output.pdf"

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

async def main():
    start_url = "https://projectforum.tudelft.nl/course_editions/119"
    allowed_prefixes = "https://projectforum.tudelft.nl/course_editions/119"

    def url_filter(url: str) -> bool:
        """Checks if a URL starts with any of the allowed prefixes."""
        return (
                url.startswith(allowed_prefixes) and
                "?user_id=" not in url and
                not url.endswith("/interested")
        )

    async with async_playwright() as p:
        async with get_browser_context(p, headless=True) as context:

            urls = await async_search(
                context=context, url=start_url,
                depth=5, url_filter=url_filter
            )
            if not urls:
                logger.warning("No URLs found")
                return
            urls_list = sorted(urls)

            await create_pdf_from_urls(
                browser=context,
                urls=urls_list,
                output_file=DEFAULT_OUTPUT
            )

if __name__ == '__main__':
    asyncio.run(main())