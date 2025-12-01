# src/cli.py
import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

from src.config import RunConfig, OutputType, MarkdownStrategy
from src.constants import STATE_FILE
from src.utils.playwright_utils import run_browser_auth

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    return "".join([c for c in name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()


async def interactive_auth_check():
    """Asks user if they want to update cookies, runs browser if so."""
    print("\n--- Authentication ---")
    update = input("Do you want to update the session/cookies file (opens browser)? [y/N]: ").strip().lower()
    if update == 'y':
        print("Opening browser... Log in, then close the window to save state.")
        await run_browser_auth()
        print("State updated.\n")


def get_user_inputs(args: argparse.Namespace) -> RunConfig:
    print("--- Configuration ---")

    # 1. Start URL
    start_url = args.start_url
    if not start_url:
        start_url = input("Start URL: ").strip()
        while not start_url:
            start_url = input("Start URL (required): ").strip()

    # 2. Prefixes
    prefixes = []
    if args.prefixes:
        prefixes = args.prefixes
    else:
        print("Allowed Prefixes (Press Enter with empty line to finish):")
        # Default suggestion
        domain = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}"
        print(f"Suggestion: {domain}")
        while True:
            val = input(f"Prefix [{len(prefixes) + 1}]: ").strip()
            if not val:
                if not prefixes:
                    print("You must provide at least one prefix.")
                    continue
                break
            prefixes.append(val)

    # 3. Output Directory
    out_dir_str = args.output_dir

    default_folder = Path.cwd() / sanitize_filename(urlparse(start_url).netloc)

    if not out_dir_str:
        out_dir_str = input(f"Output Directory [Default: {default_folder}]: ").strip()

    output_dir = Path(out_dir_str) if out_dir_str else default_folder

    # 4. Output Type
    out_type = args.output_type
    if not out_type:
        print("Output Type Options: " + ", ".join([e.value for e in OutputType]))
        while True:
            val = input("Output Type: ").strip()
            try:
                out_type = OutputType(val)
                break
            except ValueError:
                print("Invalid output type.")

    # 5. MD Strategy
    md_strat = args.md_strategy
    md_strat = MarkdownStrategy.ONLY_HTML if out_type == OutputType.PDF else md_strat
    if not md_strat:
        print("Markdown Strategy Options: " + ", ".join([e.value for e in MarkdownStrategy]))
        while True:
            val = input("MD Strategy: ").strip()
            try:
                md_strat = MarkdownStrategy(val)
                break
            except ValueError:
                print("Invalid strategy.")

    # Derive a safe output name from start_url
    output_name = sanitize_filename(urlparse(start_url).netloc + urlparse(start_url).path)
    if not output_name:
        output_name = "crawled_output"

    return RunConfig(
        start_url=start_url,
        allowed_prefixes=prefixes,
        output_dir=output_dir,
        output_name=output_name,
        output_type=out_type,
        md_strategy=md_strat,
        max_urls=args.max_urls,
        max_filesize_mb=args.max_filesize,
        concurrency_limit=args.concurrency
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Async Web Crawler & Converter")
    parser.add_argument("--start-url", help="Initial URL to crawl")
    parser.add_argument("--prefixes", nargs="+", help="Allowed URL prefixes (supports glob wildcards, e.g. *.example.com/*)")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--output-type", choices=[e.value for e in OutputType], help="Output format")
    parser.add_argument("--md-strategy", choices=[e.value for e in MarkdownStrategy], help="Markdown checking strategy")
    parser.add_argument("--max-urls", type=int, default=500, help="Max URLs to crawl (default: 500)")
    parser.add_argument("--max-filesize", type=int, default=99, help="Max filesize per output in MB (default: 99)")
    parser.add_argument("--concurrency", type=int, default=20, help="Task concurrency limit")

    return parser.parse_args()