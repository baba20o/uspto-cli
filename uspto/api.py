"""USPTO API client — handles requests to USPTO Open Data APIs."""

import logging
import time

import requests

from uspto.cache import PatentCache
from uspto.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

# USPTO Open Data Portal base URLs
PATENT_API_BASE = "https://developer.uspto.gov/ibd-api/v1"
FULL_TEXT_BASE = "https://api.patentsview.org/patents"

MAX_RETRIES = 4
DEFAULT_RETRY_WAIT = 5


class USPTOClient:
    """Client for USPTO patent search APIs."""

    def __init__(self, use_cache: bool = True):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "uspto-cli/0.1.0",
        })
        self.rate_limiter = get_rate_limiter()
        self.use_cache = use_cache
        self.cache = PatentCache() if use_cache else None

    def search_patents(self, query: str, start: int = 0, rows: int = 25) -> dict:
        """Search patents by keyword query."""
        params = {
            "searchText": query,
            "start": start,
            "rows": rows,
        }
        return self._request("GET", f"{PATENT_API_BASE}/patent/application", params=params)

    def get_patent(self, patent_number: str) -> dict:
        """Look up a specific patent by number."""
        return self._request("GET", f"{PATENT_API_BASE}/patent/application", params={
            "searchText": patent_number,
            "rows": 1,
        })

    def search_patentsview(self, query: str, fields: list = None, per_page: int = 25, page: int = 1) -> dict:
        """Search via PatentsView API (richer data, full-text search)."""
        if fields is None:
            fields = [
                "patent_number", "patent_title", "patent_date",
                "patent_abstract", "patent_type",
                "assignee_organization", "inventor_first_name", "inventor_last_name",
            ]
        payload = {
            "q": {"_text_any": {"patent_title": query}},
            "f": fields,
            "o": {"per_page": per_page, "page": page},
            "s": [{"patent_date": "desc"}],
        }
        return self._request("POST", f"{FULL_TEXT_BASE}/query", data=payload)

    def _request(self, method: str, url: str, params: dict = None, data: dict = None) -> dict:
        """Execute an API request with retry on 429."""
        # Check cache for GET requests
        if method == "GET" and self.use_cache and self.cache:
            cached = self.cache.get(url, params)
            if cached is not None:
                logger.debug("Cache hit: %s", url)
                return cached

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            self.rate_limiter.acquire()
            try:
                response = self.session.request(
                    method=method, url=url, params=params, json=data,
                )
                response.raise_for_status()
                result = response.json()

                if hasattr(self.rate_limiter, "report_success"):
                    self.rate_limiter.report_success()

                # Cache successful GET responses
                if method == "GET" and self.use_cache and self.cache and "error" not in result:
                    self.cache.set(url, params, result)

                if attempt > 0:
                    logger.info("Request succeeded after %d retries: %s", attempt, url)
                return result

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    if hasattr(self.rate_limiter, "report_rate_limit"):
                        self.rate_limiter.report_rate_limit()
                    if attempt < MAX_RETRIES:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait = int(retry_after)
                            except ValueError:
                                wait = DEFAULT_RETRY_WAIT
                        else:
                            wait = DEFAULT_RETRY_WAIT * (2 ** attempt)
                        logger.warning(
                            "Rate limited (429) on %s — waiting %ds before retry %d/%d",
                            url, wait, attempt + 1, MAX_RETRIES,
                        )
                        time.sleep(wait)
                        continue
                    logger.error("Rate limited (429) on %s — exhausted %d retries", url, MAX_RETRIES)
                last_error = e
                return {"error": str(e), "status_code": response.status_code}

            except requests.exceptions.RequestException as e:
                last_error = e
                return {"error": str(e)}

        return {"error": str(last_error) if last_error else "max retries exceeded"}
