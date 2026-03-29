"""Tests for USPTO ODP API client."""

from unittest.mock import patch

import pytest

from uspto.api import USPTOClient


@pytest.fixture
def client():
    return USPTOClient(api_key="test-key", use_cache=False)


def test_client_init():
    c = USPTOClient(api_key="test", use_cache=False)
    assert c.cache is None
    assert c.rate_limiter is not None
    assert c.api_key == "test"


def test_client_init_with_cache():
    c = USPTOClient(api_key="test", use_cache=True)
    assert c.cache is not None


def test_session_headers():
    c = USPTOClient(api_key="my-key", use_cache=False)
    assert c.session.headers["X-API-KEY"] == "my-key"
    assert c.session.headers["Accept"] == "application/json"


@patch("uspto.api.USPTOClient._request")
def test_search_patents(mock_request, client):
    mock_request.return_value = {"count": 0, "patentFileWrapperDataBag": []}
    result = client.search_patents("machine learning")
    mock_request.assert_called_once()
    args = mock_request.call_args
    assert "search" in args[0][1]  # URL contains 'search'


@patch("uspto.api.USPTOClient._request")
def test_get_application(mock_request, client):
    mock_request.return_value = {"count": 1, "patentFileWrapperDataBag": [{"applicationNumberText": "14412875"}]}
    result = client.get_application("14412875")
    mock_request.assert_called_once()
    assert "14412875" in mock_request.call_args[0][1]


@patch("uspto.api.USPTOClient._request")
def test_get_application_metadata(mock_request, client):
    mock_request.return_value = {"count": 1}
    client.get_application_metadata("14412875")
    assert "meta-data" in mock_request.call_args[0][1]


@patch("uspto.api.USPTOClient._request")
def test_get_application_assignment(mock_request, client):
    mock_request.return_value = {"count": 1}
    client.get_application_assignment("14412875")
    assert "assignment" in mock_request.call_args[0][1]


@patch("uspto.api.USPTOClient._request")
def test_search_petition_decisions(mock_request, client):
    mock_request.return_value = {"count": 0}
    client.search_petition_decisions("Denied")
    assert "petition" in mock_request.call_args[0][1]


@patch("uspto.api.USPTOClient._request")
def test_search_ptab_proceedings(mock_request, client):
    mock_request.return_value = {"count": 0}
    client.search_ptab_proceedings("IPR2023")
    assert "proceedings" in mock_request.call_args[0][1]


@patch("uspto.api.USPTOClient._request")
def test_search_bulk_datasets(mock_request, client):
    mock_request.return_value = {"count": 0}
    client.search_bulk_datasets("patent grant")
    assert "datasets" in mock_request.call_args[0][1]


@patch("uspto.api.USPTOClient._request")
def test_search_status_codes(mock_request, client):
    mock_request.return_value = {"count": 0}
    client.search_status_codes("Preexam")
    assert "status-codes" in mock_request.call_args[0][1]
