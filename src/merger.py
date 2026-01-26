import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from pypdf import PdfWriter
from src.config import RunConfig, OutputType

logger = logging.getLogger(__name__)


class BaseMerger(ABC):
    def __init__(self, config: RunConfig):
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.buffer_size = 0
        self.part_num = 1
        self.buffer = []

    @abstractmethod
    def add(self, file_path: Path):
        """Add a file to the merge buffer."""
        pass

    @abstractmethod
    def flush(self):
        """Write current buffer to disk."""
        pass

    def close(self):
        """Final flush."""
        if self.buffer:
            self.flush()


class TextMerger(BaseMerger):
    def __init__(self, config: RunConfig, ext: str):
        super().__init__(config)
        self.ext = ext
        self.separator = "\n\n" + "=" * 40 + "\n\n"
        self.sep_size = len(self.separator.encode('utf-8'))

    def add(self, file_path: Path):
        try:
            f_size = file_path.stat().st_size
            # Check limit
            if self.buffer_size + f_size + self.sep_size > self.config.max_bytes:
                self.flush()

            text = file_path.read_text(encoding="utf-8")
            self.buffer.append(text)
            self.buffer_size += f_size + self.sep_size
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")

    def flush(self):
        fname = f"{self.config.output_name}_part{self.part_num}{self.ext}"
        out_path = self.config.output_dir / fname
        try:
            with out_path.open("w", encoding="utf-8") as f:
                for content in self.buffer:
                    f.write(content)
                    f.write(self.separator)
            logger.info(f"Saved: {out_path}")
        except Exception as e:
            logger.error(f"Failed to write {out_path}: {e}")

        # Reset
        self.buffer = []
        self.buffer_size = 0
        self.part_num += 1


class PdfMerger(BaseMerger):
    def add(self, file_path: Path):
        try:
            f_size = file_path.stat().st_size
            # Limit by size OR count (PDF merging is memory intensive)
            if (self.buffer_size + f_size > self.config.max_bytes) or (len(self.buffer) >= 50):
                self.flush()

            self.buffer.append(file_path)
            self.buffer_size += f_size
        except Exception as e:
            logger.error(f"Error preparing PDF {file_path}: {e}")

    def flush(self):
        writer = PdfWriter()
        for f_path in self.buffer:
            try:
                writer.append(f_path)
            except Exception as e:
                logger.error(f"Error appending PDF {f_path}: {e}")

        fname = f"{self.config.output_name}_part{self.part_num}.pdf"
        out_path = self.config.output_dir / fname
        try:
            with open(out_path, "wb") as f:
                writer.write(f)
            logger.info(f"Saved: {out_path}")
        except Exception as e:
            logger.error(f"Failed to write PDF {out_path}: {e}")

        self.buffer = []
        self.buffer_size = 0
        self.part_num += 1


def get_merger(config: RunConfig) -> BaseMerger:
    if config.output_type == OutputType.PDF:
        return PdfMerger(config)
    else:
        return TextMerger(config, ".md")


async def run_merger_worker(queue: asyncio.Queue, config: RunConfig):
    merger = get_merger(config)
    while True:
        path = await queue.get()
        if path is None:
            merger.close()
            queue.task_done()
            break

        merger.add(path)
        queue.task_done()