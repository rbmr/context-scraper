import logging
from pathlib import Path
from typing import List

from pypdf import PdfWriter

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
        if dest.resolve() == pdf_src.resolve():
            logger.warning(f"Source file {pdf_src} is same as output file, ignoring.")
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