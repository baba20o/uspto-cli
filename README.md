# USPTO CLI

A command-line tool for searching and analyzing U.S. patent data via the [USPTO Open Data Portal (ODP) API](https://data.uspto.gov/apis/getting-started).

Built for research agents and human analysts — supports rich terminal output, markdown tables, and raw JSON.

## Install

```bash
pip install -e .
```

## Setup

Get a free API key from [data.uspto.gov](https://data.uspto.gov/apis/getting-started), then set it:

```bash
# Option 1: environment variable
export USPTO_KEY=your_key_here

# Option 2: .env file in the project directory
echo "USPTO_KEY=your_key_here" > .env
```

## Commands

### `search` — Full-text patent search

```bash
# Basic search
uspto search "machine learning"

# Rich metadata (title, applicant, status, dates)
uspto search "machine learning" --full

# Boolean operators, field targeting, date ranges
uspto search "applicationMetaData.firstApplicantName:Google AND artificial intelligence" --full
uspto search "CRISPR" --full --sort "applicationMetaData.filingDate desc"
uspto search "quantum computing" --full --range-filters "applicationMetaData.filingDate 2024-01-01:2026-01-01"

# Faceted results
uspto search "neural network" --facets "applicationMetaData.firstApplicantName,applicationMetaData.applicationTypeCode"
```

### `lookup` — Patent application detail

```bash
# Full application data
uspto lookup 14412875

# Specific sections
uspto lookup 14412875 --section meta-data
uspto lookup 14412875 --section assignment
uspto lookup 14412875 --section continuity
uspto lookup 14412875 --section documents
uspto lookup 14412875 --section transactions
uspto lookup 14412875 --section attorney
uspto lookup 14412875 --section adjustment
uspto lookup 14412875 --section foreign-priority
uspto lookup 14412875 --section associated-documents
```

### `landscape` — Technology landscape analysis

Runs a faceted search to show who's filing patents and application type distribution for a technology area.

```bash
uspto landscape "autonomous vehicle"
uspto landscape "CRISPR gene editing" --markdown
```

Example output:
```
## Technology Landscape: 'autonomous vehicle'

**Total Patents:** 299,320

### firstApplicantName

| Value | Count |
|-------|-------|
| TOYOTA JIDOSHA KABUSHIKI KAISHA | 7242 |
| Ford Global Technologies, LLC | 6985 |
| GM GLOBAL TECHNOLOGY OPERATIONS LLC | 4279 |
| HONDA MOTOR CO., LTD. | 3994 |
| Bayerische Motoren Werke Aktiengesellschaft | 3484 |
```

### `family` — Patent continuity chain

Shows parent and child applications for a patent.

```bash
uspto family 14412875
uspto family 16330077 --markdown
```

### `assignee` — Search by company/applicant

Shortcut for applicant-targeted search.

```bash
uspto assignee "Google"
uspto assignee "OpenAI" --limit 20
uspto assignee "Tesla" --sort "applicationMetaData.filingDate asc"
```

### `petitions` — Petition decisions

```bash
uspto petitions "Denied AND Design"
```

### `ptab` — PTAB trials

Search proceedings, decisions, or documents.

```bash
uspto ptab "IPR2023" --type proceedings
uspto ptab "pharmaceutical" --type decisions
uspto ptab "Samsung" --type documents
```

### `appeals` — PTAB appeals & interferences

```bash
uspto appeals "pharmaceutical"
uspto appeals "semiconductor" --type interferences
```

### `datasets` — Bulk data products

```bash
uspto datasets "patent grant"
```

### `status-codes` — Application status code lookup

```bash
uspto status-codes "Preexam"
uspto status-codes "Patented"
```

### `clear-cache` — Cache management

```bash
uspto clear-cache
```

## Output Formats

Every search command supports three output modes:

| Flag | Format | Use case |
|------|--------|----------|
| *(default)* | Rich terminal tables | Human use in terminal |
| `--markdown` / `-m` | Markdown tables | Agent consumption, piping |
| `--json-output` / `-j` | Raw JSON | Programmatic access |

```bash
# Rich table (default)
uspto search "AI" --full

# Markdown for agents
uspto search "AI" --full --markdown

# Raw JSON for scripts
uspto search "AI" -j | jq '.patentFileWrapperDataBag[].applicationNumberText'
```

## Global Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug logging (shows API calls, cache hits) |
| `--no-cache` | Disable response caching (24hr TTL by default) |
| `--api-key` | Pass API key directly (overrides `USPTO_KEY` env) |

## Query Syntax

The patent search uses Lucene query syntax:

| Syntax | Example |
|--------|---------|
| Boolean | `machine AND learning`, `AI OR ML`, `NOT provisional` |
| Exact phrase | `"neural network"` |
| Field targeting | `applicationMetaData.firstApplicantName:Google` |
| Wildcards | `block*chain` |
| Range | `applicationMetaData.filingDate:[2024-01-01 TO 2025-01-01]` |
| Comparison | `applicationMetaData.applicationStatusCode:>600` |

## Architecture

```
uspto/
├── cli.py           # Click commands + Rich/Markdown renderers
├── api.py           # ODP API client (all endpoints)
├── cache.py         # File-based response cache (~/.uspto_cache/)
├── rate_limiter.py  # Shared cross-process rate limiter (SQLite)
├── __init__.py
└── __main__.py
```

- **Rate limiting**: SQLite-backed cross-process limiter at `~/.uspto/rate_limit.db`
- **Caching**: File-based with 24hr TTL at `~/.uspto_cache/`
- **429 retry**: Exponential backoff with `Retry-After` header support (up to 4 retries)

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -x --tb=short
```

## License

MIT
