"""Tests for USPTO API client."""

from unittest.mock import MagicMock, patch

import pytest

from uspto.api import USPTOClient


@pytest.fixture
def client():
    return USPTOClient(use_cache=False)


def test_client_init():
    c = USPTOClient(use_cache=False)
    assert c.cache is None
    assert c.rate_limiter is not None


def test_client_init_with_cache():
    c = USPTOClient(use_cache=True)
    assert c.cache is not None


@patch("uspto.api.USPTOClient._request")
def test_search_patents(mock_request, client):
    mock_request.return_value = {"response": {"docs": [], "numFound": 0}}
    result = client.search_patents("machine learning")
    mock_request.assert_called_once()
    assert "response" in result


@patch("uspto.api.USPTOClient._request")
def test_get_patent(mock_request, client):
    mock_request.return_value = {"response": {"docs": [{"applId": "123"}], "numFound": 1}}
    result = client.get_patent("US12345678")
    mock_request.assert_called_once()


@patch("uspto.api.USPTOClient._request")
def test_search_patentsview(mock_request, client):
    mock_request.return_value = {"patents": [], "total_patent_count": 0}
    result = client.search_patentsview("neural network")
    mock_request.assert_called_once()
    assert "patents" in result
