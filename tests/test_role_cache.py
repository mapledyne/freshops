"""
Tests for Role caching and registry operations.

These tests verify the registry-based caching system for roles,
including cache hits, full list loading, and __class_getitem__ behavior.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from freshops import FreshServiceClient, FreshServiceConfig
from freshops.exceptions import EntityNotFoundError, RegistryClientNotInitializedError
from freshops.models.role import Role, Roles


@pytest.fixture
def config() -> FreshServiceConfig:
    """Create a test configuration."""
    return FreshServiceConfig(
        domain="testcompany",
        api_key="test_api_key",
        log_level="DEBUG",
    )


@pytest.fixture
def client(config: FreshServiceConfig) -> FreshServiceClient:
    """Create a mocked FreshServiceClient for testing."""
    client = FreshServiceClient(config)
    return client


@pytest.fixture
def sample_role_data() -> dict:
    """Sample role data from API."""
    return {
        "id": 3001,
        "name": "Administrator",
        "description": "Full administrative access",
        "default": False,
        "role_type": 1,  # Admin role
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_role_data_2() -> dict:
    """Second sample role data."""
    return {
        "id": 3002,
        "name": "Agent",
        "description": "Standard agent role",
        "default": True,
        "role_type": 2,  # Agent role
        "created_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def clean_registry():
    """
    Automatically clean the Roles registry before each test.

    Ensures test isolation by clearing the cache and resetting flags.
    """
    # Clear registry before test
    Roles._registry.clear()
    Roles._full_list_loaded = False
    Roles._client = None
    yield
    # Clean up after test
    Roles._registry.clear()
    Roles._full_list_loaded = False
    Roles._client = None


class TestRolesRegistry:
    """Tests for Roles registry operations."""

    def test_registry_returns_cached_role(
        self, client: FreshServiceClient, sample_role_data: dict
    ) -> None:
        """Verify Roles[3001] returns cached role after loading."""
        Roles.set_client(client)

        # Load role into cache first
        with patch.object(
            client, "list_roles", return_value=[sample_role_data]
        ):
            role1 = Roles[3001]

        # Second access should return same instance
        role2 = Roles[3001]

        assert role1 is role2
        assert role1.id == 3001
        assert role1.name == "Administrator"

    def test_registry_loads_all_when_not_found(
        self,
        client: FreshServiceClient,
        sample_role_data: dict,
        sample_role_data_2: dict,
    ) -> None:
        """Verify Roles[role_id] loads all roles if not in cache."""
        Roles.set_client(client)

        with patch.object(
            client,
            "list_roles",
            return_value=[sample_role_data, sample_role_data_2],
        ) as mock_list:
            role = Roles[3001]

            # Should have loaded all roles
            assert mock_list.call_count == 1
            assert role.id == 3001
            assert role.name == "Administrator"
            assert len(Roles._registry) == 2

    def test_registry_raises_when_not_found(
        self, client: FreshServiceClient, sample_role_data: dict
    ) -> None:
        """Verify Roles[9999] raises ValueError when role doesn't exist."""
        Roles.set_client(client)

        with patch.object(
            client, "list_roles", return_value=[sample_role_data]
        ):
            with pytest.raises(EntityNotFoundError, match="Role 9999 not found"):
                _ = Roles[9999]

    def test_registry_requires_client(self) -> None:
        """Verify Roles[role_id] requires client to be set."""
        Roles._client = None

        with pytest.raises(RegistryClientNotInitializedError, match="Roles registry client not initialized"):
            _ = Roles[3001]


class TestRoleFromApiResponse:
    """Tests for Role.from_api_response caching."""

    def test_from_api_response_caches_role(
        self, client: FreshServiceClient, sample_role_data: dict
    ) -> None:
        """Verify from_api_response stores role in registry."""
        Roles.set_client(client)
        Roles._registry.clear()

        role = Role.from_api_response(sample_role_data)

        assert role.id == 3001
        assert role.name == "Administrator"
        assert role.role_type == 1
        assert 3001 in Roles._registry
        assert Roles._registry[3001] is role

    def test_from_api_response_updates_existing(
        self, client: FreshServiceClient, sample_role_data: dict
    ) -> None:
        """Verify from_api_response replaces existing cached role."""
        Roles.set_client(client)
        Roles._registry.clear()

        # Create role with just ID (via registry) - mock the API call
        with patch.object(
            client, "list_roles", return_value=[sample_role_data]
        ):
            role1 = Roles[3001]
            assert role1.name == "Administrator"  # Loaded from API

        # Now update it with full data (creates new instance and replaces in cache)
        updated_data = sample_role_data.copy()
        updated_data["name"] = "Updated Administrator"
        role2 = Role.from_api_response(updated_data)

        # from_api_response creates a new instance (authoritative source)
        # but it replaces the old one in the registry
        assert role2.id == role1.id
        assert role2.name == "Updated Administrator"
        assert role2.role_type == 1
        # Registry should now point to the new instance
        assert Roles._registry[3001] is role2

    def test_from_api_response_handles_missing_fields(
        self, client: FreshServiceClient
    ) -> None:
        """Verify from_api_response handles missing optional fields."""
        Roles.set_client(client)
        Roles._registry.clear()

        minimal_data = {
            "id": 3003,
            "name": "Minimal Role",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        role = Role.from_api_response(minimal_data)

        assert role.id == 3003
        assert role.name == "Minimal Role"
        assert role.description == ""
        assert role.default is False
        assert role.role_type is None


class TestRoleModel:
    """Tests for Role model fields and properties."""

    def test_role_default_flag(
        self, client: FreshServiceClient, sample_role_data_2: dict
    ) -> None:
        """Verify role default flag."""
        Roles.set_client(client)
        Roles._registry.clear()

        role = Role.from_api_response(sample_role_data_2)

        assert role.default is True
        assert role.is_default is True

    def test_role_type_admin(
        self, client: FreshServiceClient, sample_role_data: dict
    ) -> None:
        """Verify admin role type detection."""
        Roles.set_client(client)
        Roles._registry.clear()

        role = Role.from_api_response(sample_role_data)

        assert role.role_type == 1
        assert role.is_admin_role is True
        assert role.is_agent_role is False

    def test_role_type_agent(
        self, client: FreshServiceClient, sample_role_data_2: dict
    ) -> None:
        """Verify agent role type detection."""
        Roles.set_client(client)
        Roles._registry.clear()

        role = Role.from_api_response(sample_role_data_2)

        assert role.role_type == 2
        assert role.is_admin_role is False
        assert role.is_agent_role is True

    def test_role_type_none(
        self, client: FreshServiceClient
    ) -> None:
        """Verify role with no role_type."""
        Roles.set_client(client)
        Roles._registry.clear()

        role_data = {
            "id": 3004,
            "name": "Custom Role",
            "role_type": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        role = Role.from_api_response(role_data)

        assert role.role_type is None
        assert role.is_admin_role is False
        assert role.is_agent_role is False


class TestRolesCollection:
    """Tests for Roles collection operations."""

    def test_from_api_response_creates_collection(
        self,
        client: FreshServiceClient,
        sample_role_data: dict,
        sample_role_data_2: dict,
    ) -> None:
        """Verify from_api_response creates Roles collection."""
        Roles.set_client(client)

        # Mock the list_roles call that happens in from_api_response
        with patch.object(
            client,
            "list_roles",
            return_value=[sample_role_data, sample_role_data_2],
        ):
            roles = Roles.from_api_response(
                [sample_role_data, sample_role_data_2], client=client
            )

            assert len(roles) == 2
            assert roles[0].name == "Administrator"
            assert roles[1].name == "Agent"

    def test_find_by_name_uses_cache(
        self,
        client: FreshServiceClient,
        sample_role_data: dict,
        sample_role_data_2: dict,
    ) -> None:
        """Verify find_by_name loads cache and searches registry."""
        Roles.set_client(client)
        Roles._registry.clear()

        with patch.object(
            client,
            "list_roles",
            return_value=[sample_role_data, sample_role_data_2],
        ):
            roles = Roles.from_api_response([], client=client)
            role = roles.find_by_name("Administrator")

            assert role is not None
            assert role.id == 3001
            assert role.name == "Administrator"

    def test_find_by_name_case_insensitive(
        self,
        client: FreshServiceClient,
        sample_role_data: dict,
    ) -> None:
        """Verify find_by_name is case-insensitive."""
        Roles.set_client(client)
        Roles._registry.clear()

        with patch.object(
            client, "list_roles", return_value=[sample_role_data]
        ):
            roles = Roles.from_api_response([], client=client)
            role1 = roles.find_by_name("administrator")
            role2 = roles.find_by_name("ADMINISTRATOR")
            role3 = roles.find_by_name("Administrator")

            assert role1 is not None
            assert role1 is role2
            assert role2 is role3

    def test_find_by_name_returns_none_when_not_found(
        self,
        client: FreshServiceClient,
        sample_role_data: dict,
    ) -> None:
        """Verify find_by_name returns None when role not found."""
        Roles.set_client(client)
        Roles._registry.clear()

        with patch.object(
            client, "list_roles", return_value=[sample_role_data]
        ):
            roles = Roles.from_api_response([], client=client)
            role = roles.find_by_name("NonExistent")

            assert role is None


class TestRolesClientInitialization:
    """Tests for client initialization in registry."""

    def test_set_client_initializes_registry(
        self, client: FreshServiceClient
    ) -> None:
        """Verify set_client initializes the registry client."""
        Roles._client = None
        Roles.set_client(client)

        assert Roles._client is client

