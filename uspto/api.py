"""USPTO Open Data Portal (ODP) API client.

Base URL: https://api.uspto.gov
Auth: X-API-KEY header
Spec: https://data.uspto.gov/swagger/swagger.yaml
"""

import logging
import os
import time

import requests
from dotenv import load_dotenv

from uspto.cache import PatentCache
from uspto.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

BASE_URL = "https://api.uspto.gov"

MAX_RETRIES = 4
DEFAULT_RETRY_WAIT = 5


class USPTOClient:
    """Client for the USPTO Open Data Portal API."""

    def __init__(self, api_key: str = None, use_cache: bool = True):
        # Load .env from the package directory or cwd
        load_dotenv()
        self.api_key = api_key or os.environ.get("USPTO_KEY", "")
        if not self.api_key:
            logger.warning("No USPTO_KEY found — API calls will return 403")

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "X-API-KEY": self.api_key,
            "User-Agent": "uspto-cli/0.1.0",
        })
        self.rate_limiter = get_rate_limiter()
        self.use_cache = use_cache
        self.cache = PatentCache() if use_cache else None

    # ── Patent Search ────────────────────────────────────────

    def search_patents(
        self,
        query: str = "",
        sort: str = None,
        offset: int = 0,
        limit: int = 25,
        fields: str = None,
        filters: str = None,
        range_filters: str = None,
        facets: str = None,
    ) -> dict:
        """Search patent applications (GET).

        Query supports boolean operators (AND, OR, NOT), wildcards (*),
        exact phrases (""), field:value syntax, and range queries.
        """
        params = {"q": query, "offset": offset, "limit": limit}
        if sort:
            params["sort"] = sort
        if fields:
            params["fields"] = fields
        if filters:
            params["filters"] = filters
        if range_filters:
            params["rangeFilters"] = range_filters
        if facets:
            params["facets"] = facets
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/search", params=params)

    def search_patents_post(self, payload: dict) -> dict:
        """Search patent applications (POST with JSON body)."""
        return self._request("POST", f"{BASE_URL}/api/v1/patent/applications/search", data=payload)

    def get_application(self, application_number: str) -> dict:
        """Get full patent application data by application number."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/{application_number}")

    def get_application_metadata(self, application_number: str) -> dict:
        """Get patent application meta data."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/{application_number}/meta-data")

    def get_application_assignment(self, application_number: str) -> dict:
        """Get patent assignment (ownership) data."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/{application_number}/assignment")

    def get_application_attorney(self, application_number: str) -> dict:
        """Get attorney/agent data for an application."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/{application_number}/attorney")

    def get_application_continuity(self, application_number: str) -> dict:
        """Get continuity (parent/child) data for an application."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/{application_number}/continuity")

    def get_application_transactions(self, application_number: str) -> dict:
        """Get transaction history for an application."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/{application_number}/transactions")

    def get_application_documents(
        self,
        application_number: str,
        document_codes: str = None,
        date_from: str = None,
        date_to: str = None,
    ) -> dict:
        """Get documents for an application number."""
        params = {}
        if document_codes:
            params["documentCodes"] = document_codes
        if date_from:
            params["officialDateFrom"] = date_from
        if date_to:
            params["officialDateTo"] = date_to
        return self._request(
            "GET",
            f"{BASE_URL}/api/v1/patent/applications/{application_number}/documents",
            params=params or None,
        )

    def get_application_adjustment(self, application_number: str) -> dict:
        """Get patent term adjustment data."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/{application_number}/adjustment")

    def get_application_foreign_priority(self, application_number: str) -> dict:
        """Get foreign priority data."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/{application_number}/foreign-priority")

    def get_associated_documents(self, application_number: str) -> dict:
        """Get associated (pgpub, grant) document metadata."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/{application_number}/associated-documents")

    def search_status_codes(self, query: str = "", offset: int = 0, limit: int = 25) -> dict:
        """Search patent application status codes."""
        params = {"q": query, "offset": offset, "limit": limit}
        return self._request("GET", f"{BASE_URL}/api/v1/patent/status-codes", params=params)

    # ── Patent Download ──────────────────────────────────────

    def download_patents(
        self,
        query: str = "",
        sort: str = None,
        offset: int = 0,
        limit: int = 25,
        fields: str = None,
        filters: str = None,
        range_filters: str = None,
        fmt: str = "json",
    ) -> dict:
        """Download patent search results (GET, supports json/csv)."""
        params = {"q": query, "offset": offset, "limit": limit, "format": fmt}
        if sort:
            params["sort"] = sort
        if fields:
            params["fields"] = fields
        if filters:
            params["filters"] = filters
        if range_filters:
            params["rangeFilters"] = range_filters
        return self._request("GET", f"{BASE_URL}/api/v1/patent/applications/search/download", params=params)

    # ── Petition Decisions ───────────────────────────────────

    def search_petition_decisions(
        self,
        query: str = "",
        sort: str = None,
        offset: int = 0,
        limit: int = 25,
        fields: str = None,
        filters: str = None,
        range_filters: str = None,
        facets: str = None,
    ) -> dict:
        """Search petition decisions."""
        params = {"q": query, "offset": offset, "limit": limit}
        if sort:
            params["sort"] = sort
        if fields:
            params["fields"] = fields
        if filters:
            params["filters"] = filters
        if range_filters:
            params["rangeFilters"] = range_filters
        if facets:
            params["facets"] = facets
        return self._request("GET", f"{BASE_URL}/api/v1/petition/decisions/search", params=params)

    def get_petition_decision(self, record_id: str, include_documents: bool = False) -> dict:
        """Get a specific petition decision by record identifier."""
        params = {}
        if include_documents:
            params["includeDocuments"] = "true"
        return self._request(
            "GET",
            f"{BASE_URL}/api/v1/petition/decisions/{record_id}",
            params=params or None,
        )

    # ── PTAB Trials ──────────────────────────────────────────

    def search_ptab_proceedings(self, query: str = "", offset: int = 0, limit: int = 25) -> dict:
        """Search PTAB trial proceedings."""
        params = {"q": query, "offset": offset, "limit": limit}
        return self._request("GET", f"{BASE_URL}/api/v1/patent/trials/proceedings/search", params=params)

    def get_ptab_proceeding(self, trial_number: str) -> dict:
        """Get a specific PTAB trial proceeding."""
        return self._request("GET", f"{BASE_URL}/api/v1/patent/trials/proceedings/{trial_number}")

    def search_ptab_decisions(self, query: str = "", offset: int = 0, limit: int = 25) -> dict:
        """Search PTAB trial decisions."""
        params = {"q": query, "offset": offset, "limit": limit}
        return self._request("GET", f"{BASE_URL}/api/v1/patent/trials/decisions/search", params=params)

    def search_ptab_documents(self, query: str = "", offset: int = 0, limit: int = 25) -> dict:
        """Search PTAB trial documents."""
        params = {"q": query, "offset": offset, "limit": limit}
        return self._request("GET", f"{BASE_URL}/api/v1/patent/trials/documents/search", params=params)

    # ── PTAB Appeals & Interferences ─────────────────────────

    def search_appeal_decisions(self, query: str = "", offset: int = 0, limit: int = 25) -> dict:
        """Search PTAB appeal decisions."""
        params = {"q": query, "offset": offset, "limit": limit}
        return self._request("GET", f"{BASE_URL}/api/v1/patent/appeals/decisions/search", params=params)

    def search_interference_decisions(self, query: str = "", offset: int = 0, limit: int = 25) -> dict:
        """Search PTAB interference decisions."""
        params = {"q": query, "offset": offset, "limit": limit}
        return self._request("GET", f"{BASE_URL}/api/v1/patent/interferences/decisions/search", params=params)

    # ── Bulk Datasets ────────────────────────────────────────

    def search_bulk_datasets(self, query: str = "", offset: int = 0, limit: int = 25) -> dict:
        """Search bulk dataset products."""
        params = {"q": query, "offset": offset, "limit": limit}
        return self._request("GET", f"{BASE_URL}/api/v1/datasets/products/search", params=params)

    def get_bulk_dataset(self, product_id: str, include_files: bool = True) -> dict:
        """Get a bulk dataset product by identifier."""
        params = {"includeFiles": "true" if include_files else "false"}
        return self._request("GET", f"{BASE_URL}/api/v1/datasets/products/{product_id}", params=params)

    # ── Internal ─────────────────────────────────────────────

    def _request(self, method: str, url: str, params: dict = None, data: dict = None) -> dict:
        """Execute an API request with retry on 429."""
        cache_key = url
        if method == "GET" and self.use_cache and self.cache:
            cached = self.cache.get(cache_key, params)
            if cached is not None:
                logger.debug("Cache hit: %s", url)
                return cached

        last_error = None
        response = None
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

                if method == "GET" and self.use_cache and self.cache and "error" not in result:
                    self.cache.set(cache_key, params, result)

                if attempt > 0:
                    logger.info("Request succeeded after %d retries: %s", attempt, url)
                return result

            except requests.exceptions.HTTPError as e:
                if response is not None and response.status_code == 429:
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
                status = response.status_code if response is not None else None
                return {"error": str(e), "status_code": status}

            except requests.exceptions.RequestException as e:
                last_error = e
                return {"error": str(e)}

        return {"error": str(last_error) if last_error else "max retries exceeded"}
