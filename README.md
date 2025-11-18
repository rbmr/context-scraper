# Context Scraper

An asynchronous web crawler and content aggregator that crawls websites and converts them into consolidated markdown or PDF documents. Perfect for creating offline documentation, archiving web content, or preparing large context files for AI analysis.

## Features

- **Asynchronous Crawling**: High-performance concurrent web crawling with configurable limits
- **Multiple Output Formats**: 
  - Markdown (`.md`) - with flexible content strategies
  - PDF - rendered pages with browser automation
- **Smart Content Handling**:
  - `only-html`: Convert crawled HTML to markdown
  - `only-md`: Fetch `.md` files directly from the server
  - `prioritize-md`: Try markdown first, fallback to HTML
- **Automatic File Splitting**: Splits output into manageable chunks based on size limits
- **Session Management**: Persistent cookies/authentication via browser state
- **Configurable Crawling**: Set URL prefixes, depth limits, and concurrency

## Installation

### Prerequisites

- Python 3.8+
- pip

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd context-scraper
```

2. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. Create a `.env` file (optional):
```bash
touch .env
```

## Usage

### Interactive Mode

Run the scraper with interactive prompts:

```bash
python -m src.main
```

You'll be prompted for:
- Start URL
- Allowed URL prefixes
- Output directory
- Output type (pdf/md)
- Markdown strategy (only-html/only-md/prioritize-md)

### Command-Line Mode

Provide all configuration via CLI arguments:

```bash
python -m src.main \
  --start-url "https://example.com/docs" \
  --prefixes "https://example.com/docs" \
  --output-dir "./output" \
  --output-type md \
  --md-strategy prioritize-md \
  --max-urls 500 \
  --max-filesize 99 \
  --concurrency 20
```

### CLI Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--start-url` | Initial URL to start crawling | Interactive prompt |
| `--prefixes` | Allowed URL prefixes (space-separated) | Interactive prompt |
| `--output-dir` | Output directory for generated files | `<domain-name>` |
| `--output-type` | Output format: `pdf` or `md` | Interactive prompt |
| `--md-strategy` | Markdown strategy (see below) | Interactive prompt |
| `--max-urls` | Maximum URLs to crawl | 500 |
| `--max-filesize` | Max size per output file in MB | 99 |
| `--concurrency` | Concurrent task limit | 20 |

### Markdown Strategies

- **`only-html`**: Converts crawled HTML content to markdown
- **`only-md`**: Only fetches `.md` files (appends `.md` to URLs)
- **`prioritize-md`**: Tries `.md` first, falls back to HTML conversion

## Authentication

The scraper supports authenticated sessions through browser state persistence:

1. When prompted, choose to update session/cookies
2. A browser window will open
3. Log in to the target website
4. Close the browser window
5. Session is saved to `state.json` and will be reused

## Project Structure

```
context-scraper/
├── src/
│   ├── main.py              # Entry point and pipeline orchestration
│   ├── cli.py               # CLI argument parsing and interactive prompts
│   ├── config.py            # Configuration models and enums
│   ├── constants.py         # Project constants and logging config
│   ├── crawler.py           # Web crawler implementation
│   ├── fetcher.py           # Content fetching and processing
│   ├── merger.py            # Output file merging and splitting
│   └── utils/
│       ├── async_utils.py   # Async task management utilities
│       ├── httpx_utils.py   # HTTP client utilities
│       └── playwright_utils.py  # Browser automation utilities
├── state.json               # Saved browser state/cookies
├── .env                     # Environment variables (optional)
└── README.md
```

## Pipeline Architecture

The scraper uses a three-stage asynchronous pipeline:

1. **Crawler** (Producer): Discovers and queues URLs
2. **Fetcher** (Transformer): Fetches and processes content
3. **Merger** (Consumer): Aggregates and writes output files

```
Crawler → fetch_queue → Fetcher → merge_queue → Merger → Output Files
```

## Examples

### Crawl Documentation Site

```bash
python -m src.main \
  --start-url "https://docs.python.org/3/" \
  --prefixes "https://docs.python.org/3/" \
  --output-type md \
  --md-strategy only-html \
  --max-urls 1000
```

### Create PDF Archive

```bash
python -m src.main \
  --start-url "https://example.com/wiki" \
  --prefixes "https://example.com/wiki" \
  --output-type pdf \
  --max-urls 200 \
  --max-filesize 50
```

### Fetch Native Markdown Files

```bash
python -m src.main \
  --start-url "https://github.com/user/repo/tree/main/docs" \
  --prefixes "https://github.com/user/repo" \
  --output-type md \
  --md-strategy only-md
```

## Output

Generated files are saved to the specified output directory with naming:
- `<output-name>_part1.md` (or `.pdf`)
- `<output-name>_part2.md`
- etc.

Files are automatically split when they exceed the size limit.

## Dependencies

- **httpx**: Async HTTP client
- **playwright**: Browser automation for PDF rendering
- **beautifulsoup4**: HTML parsing
- **pypdf**: PDF merging
- **pydantic**: Configuration validation
- **tqdm**: Progress bars

## Troubleshooting

### "State file not found"
Run the scraper once and choose to update cookies when prompted.

### SSL/Certificate Errors
Some sites may require custom SSL verification settings. Modify `httpx_utils.py` to disable verification if needed (not recommended for production).

### Memory Issues with Large PDFs
Reduce `--max-filesize` or `--max-urls` to limit memory usage during PDF rendering.

## License

[Your License Here]

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

