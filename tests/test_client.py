"""
Tests for the FreshService client wrapper.

These tests verify the client's behavior without making actual API calls
by using mocked responses.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from freshops import FreshServiceClient, FreshServiceConfig


@pytest.fixture
def config() -> FreshServiceConfig:
    """
    Create a test configuration.

    :returns: A FreshServiceConfig instance for testing
    """
    return FreshServiceConfig(
        domain="testcompany",
        api_key="test_api_key",
        log_level="DEBUG",
    )


@pytest.fixture
def client(config: FreshServiceConfig) -> FreshServiceClient:
    """
    Create a FreshServiceClient instance for testing.

    :param config: Test configuration fixture
    :returns: A FreshServiceClient instance
    """
    return FreshServiceClient(config)


class TestFreshServiceClientInit:
    """Tests for FreshServiceClient initialization."""

    def test_client_initializes_with_config(
        self, config: FreshServiceConfig
    ) -> None:
        """
        Verify client initializes correctly with valid config.

        :param config: Test configuration fixture
        """
        client = FreshServiceClient(config)
        assert client.config == config
        assert client.base_url == "https://testcompany.freshservice.com/api/v2"

    def test_client_builds_correct_url(self) -> None:
        """
        Verify client builds the correct URL from company name.
        """
        config = FreshServiceConfig(
            domain="evergreen",
            api_key="test_key",
        )
        client = FreshServiceClient(config)
        assert client.base_url == "https://evergreen.freshservice.com/api/v2"

    def test_from_credentials_creates_client(self) -> None:
        """
        Verify from_credentials classmethod creates a valid client.
        """
        client = FreshServiceClient.from_credentials(
            domain="mycompany",
            api_key="test_key",
        )
        assert client.config.domain == "mycompany"
        assert client.config.api_key == "test_key"
        assert client.base_url == "https://mycompany.freshservice.com/api/v2"


class TestTicketOperations:
    """Tests for ticket-related client operations."""

    def test_list_tickets_returns_list(
        self, client: FreshServiceClient
    ) -> None:
        """
        Verify list_tickets returns a list of ticket dictionaries.

        :param client: Test client fixture
        """
        # TODO: Implement when list_tickets is implemented
        pytest.skip("list_tickets not yet implemented")

    def test_list_tickets_with_status_filter(
        self, client: FreshServiceClient
    ) -> None:
        """
        Verify list_tickets correctly filters by status.

        :param client: Test client fixture
        """
        pytest.skip("list_tickets not yet implemented")

    def test_get_ticket_returns_dict(
        self, client: FreshServiceClient
    ) -> None:
        """
        Verify get_ticket returns a ticket dictionary.

        :param client: Test client fixture
        """
        pytest.skip("get_ticket not yet implemented")

    def test_get_ticket_not_found_raises(
        self, client: FreshServiceClient
    ) -> None:
        """
        Verify get_ticket raises ValueError for non-existent ticket.

        :param client: Test client fixture
        """
        pytest.skip("get_ticket not yet implemented")


class TestAgentOperations:
    """Tests for agent-related client operations."""

    def test_list_agents_returns_list(
        self, client: FreshServiceClient
    ) -> None:
        """
        Verify list_agents returns a list of agent dictionaries.

        :param client: Test client fixture
        """
        with patch("freshops.client.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"agents": [{"id": 1, "first_name": "Test"}]}'
            mock_response.json.return_value = {
                "agents": [{"id": 1, "first_name": "Test"}]
            }
            mock_get.return_value = mock_response

            agents = client.list_agents()

            assert isinstance(agents, list)
            assert len(agents) == 1
            assert agents[0]["first_name"] == "Test"


class TestRequesterOperations:
    """Tests for requester-related client operations."""

    def test_list_requesters_returns_list(
        self, client: FreshServiceClient
    ) -> None:
        """
        Verify list_requesters returns a list of requester dictionaries.

        :param client: Test client fixture
        """
        pytest.skip("list_requesters not yet implemented")

    def test_search_requesters_by_email(
        self, client: FreshServiceClient
    ) -> None:
        """
        Verify search_requesters finds by email address.

        :param client: Test client fixture
        """
        pytest.skip("search_requesters not yet implemented")


class TestAssetOperations:
    """Tests for asset-related client operations."""

    def test_list_assets_returns_list(
        self, client: FreshServiceClient
    ) -> None:
        """
        Verify list_assets returns a list of asset dictionaries.

        :param client: Test client fixture
        """
        pytest.skip("list_assets not yet implemented")

    def test_search_assets_by_name(
        self, client: FreshServiceClient
    ) -> None:
        """
        Verify search_assets finds by name.

        :param client: Test client fixture
        """
        pytest.skip("search_assets not yet implemented")
