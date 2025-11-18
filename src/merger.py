import logging
from pathlib import Path
from typing import List

from pypdf import PdfWriter

from src.config import RunConfig

logger = logging.getLogger(__name__)


class Merger:
    def __init__(self, config: RunConfig):
        self.config = config

    def merge(self, source_files: List[Path]):
        """
        Dispatches to specific merge logic based on file type.
        """
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        if not source_files:
            logger.warning("No files to merge.")
            return

        ext = source_files[0].suffix

        logger.info(f"Merging {len(source_files)} files of type {ext}...")

        if ext == ".pdf":
            self._merge_pdfs(source_files)
        else:
            # .txt or .md
            self._merge_text_files(source_files, ext)

    def _merge_pdfs(self, files: List[Path]):
        part_num = 1
        current_writer = PdfWriter()
        current_batch_size = 0
        files_in_batch = 0

        for f in files:
            try:
                # Retrieve exact size from OS
                file_size = f.stat().st_size

                # Check if adding this file exceeds limit
                if ((current_batch_size + file_size > self.config.max_bytes) or (files_in_batch >= 50)) and (files_in_batch > 0):
                    self._write_pdf(current_writer, part_num)
                    part_num += 1
                    current_writer = PdfWriter()
                    current_batch_size = 0
                    files_in_batch = 0

                current_writer.append(f)
                current_batch_size += file_size
                files_in_batch += 1
            except Exception as e:
                logger.error(f"Error appending PDF {f}: {e}")

        if files_in_batch > 0:
            self._write_pdf(current_writer, part_num)

    def _write_pdf(self, writer: PdfWriter, part: int):
        fname = f"{self.config.output_name}_part{part}.pdf"
        out_path = self.config.output_dir / fname
        try:
            with open(out_path, "wb") as f:
                writer.write(f)
            logger.info(f"Saved: {out_path}")
        except Exception as e:
            logger.error(f"Failed to write PDF {out_path}: {e}")

    def _merge_text_files(self, files: List[Path], ext: str):
        part_num = 1
        current_content = []
        current_batch_size = 0

        separator = "\n\n" + "=" * 40 + "\n\n"
        sep_size = len(separator.encode('utf-8'))

        for f in files:
            try:
                # Retrieve exact size from OS
                file_size = f.stat().st_size

                # Check if adding this file + separator exceeds limit
                if (current_batch_size + file_size + sep_size > self.config.max_bytes) and (len(current_content) > 0):
                    self._write_text(current_content, part_num, ext)
                    part_num += 1
                    current_content = []
                    current_batch_size = 0

                # Read content after size check passes
                text = f.read_text(encoding="utf-8")
                current_content.append(text)
                current_content.append(separator)
                current_batch_size += file_size + sep_size
            except Exception as e:
                logger.error(f"Error reading {f}: {e}")

        if current_content:
            self._write_text(current_content, part_num, ext)

    def _write_text(self, content_list: List[str], part: int, ext: str):
        fname = f"{self.config.output_name}_part{part}{ext}"
        out_path = self.config.output_dir / fname
        try:
            with out_path.open("w", encoding="utf-8") as f:
                [f.write(c) for c in content_list]
            logger.info(f"Saved: {out_path}")
        except Exception as e:
            logger.error(f"Failed to write text file {out_path}: {e}")