from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class OutputType(str, Enum):
    PDF_RENDERED = "pdf-rendered"  # Full render of page
    PDF_TEXT = "pdf-text"  # Text extraction -> PDF
    TXT = "txt"
    MARKDOWN = "md"


class MarkdownStrategy(str, Enum):
    ONLY_HTML = "only-html"
    ONLY_MD = "only-md"
    PRIORITIZE_MD = "prioritize-md"


class RunConfig(BaseModel):
    start_url: str
    allowed_prefixes: List[str]
    output_dir: Path
    output_name: str
    output_type: OutputType
    md_strategy: MarkdownStrategy
    max_urls: int
    max_filesize_mb: int
    concurrency_limit: int = 20

    @property
    def max_bytes(self) -> int:
        return self.max_filesize_mb * 1024 * 1024


class AppState(BaseModel):
    cookies_path: Path