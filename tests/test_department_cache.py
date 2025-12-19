"""
Tests for Department caching and registry operations.

These tests verify the registry-based caching system for departments,
including cache hits, full list loading, and __class_getitem__ behavior.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from freshops import FreshServiceClient, FreshServiceConfig
from freshops.exceptions import EntityNotFoundError, RegistryClientNotInitializedError
from freshops.models.department import Department, Departments


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
def sample_department_data() -> dict:
    """Sample department data from API."""
    return {
        "id": 1001,
        "workspace_id": 2,
        "name": "Engineering",
        "description": "Engineering department",
        "head_user_id": 5001,
        "prime_user_id": 5002,
        "domains": ["engineering.example.com"],
        "custom_fields": {"budget_code": "ENG-2024"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_department_data_2() -> dict:
    """Second sample department data."""
    return {
        "id": 1002,
        "workspace_id": 2,
        "name": "Support",
        "description": "Customer Support department",
        "head_user_id": None,
        "prime_user_id": None,
        "domains": [],
        "custom_fields": {},
        "created_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def clean_registry():
    """
    Automatically clean the Departments registry before each test.

    Ensures test isolation by clearing the cache and resetting flags.
    """
    # Clear registry before test
    Departments._registry.clear()
    Departments._full_list_loaded = False
    Departments._client = None
    yield
    # Clean up after test
    Departments._registry.clear()
    Departments._full_list_loaded = False
    Departments._client = None


class TestDepartmentsRegistry:
    """Tests for Departments registry operations."""

    def test_registry_returns_cached_department(
        self, client: FreshServiceClient, sample_department_data: dict
    ) -> None:
        """Verify Departments[1001] returns cached department after loading."""
        Departments.set_client(client)

        # Load department into cache first
        with patch.object(
            client, "list_departments", return_value=[sample_department_data]
        ):
            dept1 = Departments[1001]

        # Second access should return same instance
        dept2 = Departments[1001]

        assert dept1 is dept2
        assert dept1.id == 1001
        assert dept1.name == "Engineering"

    def test_registry_loads_all_when_not_found(
        self,
        client: FreshServiceClient,
        sample_department_data: dict,
        sample_department_data_2: dict,
    ) -> None:
        """Verify Departments[dept_id] loads all departments if not in cache."""
        Departments.set_client(client)

        with patch.object(
            client,
            "list_departments",
            return_value=[sample_department_data, sample_department_data_2],
        ) as mock_list:
            dept = Departments[1001]

            # Should have loaded all departments
            assert mock_list.call_count == 1
            assert dept.id == 1001
            assert dept.name == "Engineering"
            assert len(Departments._registry) == 2

    def test_registry_raises_when_not_found(
        self, client: FreshServiceClient, sample_department_data: dict
    ) -> None:
        """Verify Departments[9999] raises ValueError when department doesn't exist."""
        Departments.set_client(client)

        with patch.object(
            client, "list_departments", return_value=[sample_department_data]
        ):
            with pytest.raises(EntityNotFoundError, match="Department 9999 not found"):
                _ = Departments[9999]

    def test_registry_requires_client(self) -> None:
        """Verify Departments[dept_id] requires client to be set."""
        Departments._client = None

        with pytest.raises(RegistryClientNotInitializedError, match="Departments registry client not initialized"):
            _ = Departments[1001]


class TestDepartmentFromApiResponse:
    """Tests for Department.from_api_response caching."""

    def test_from_api_response_caches_department(
        self, client: FreshServiceClient, sample_department_data: dict
    ) -> None:
        """Verify from_api_response stores department in registry."""
        Departments.set_client(client)
        Departments._registry.clear()

        dept = Department.from_api_response(sample_department_data)

        assert dept.id == 1001
        assert dept.name == "Engineering"
        assert dept.workspace_id == 2
        assert 1001 in Departments._registry
        assert Departments._registry[1001] is dept

    def test_from_api_response_updates_existing(
        self, client: FreshServiceClient, sample_department_data: dict
    ) -> None:
        """Verify from_api_response replaces existing cached department."""
        Departments.set_client(client)
        Departments._registry.clear()

        # Create department with just ID (via registry) - mock the API call
        with patch.object(
            client, "list_departments", return_value=[sample_department_data]
        ):
            dept1 = Departments[1001]
            assert dept1.name == "Engineering"  # Loaded from API

        # Now update it with full data (creates new instance and replaces in cache)
        updated_data = sample_department_data.copy()
        updated_data["name"] = "Updated Engineering"
        dept2 = Department.from_api_response(updated_data)

        # from_api_response creates a new instance (authoritative source)
        # but it replaces the old one in the registry
        assert dept2.id == dept1.id
        assert dept2.name == "Updated Engineering"
        assert dept2.workspace_id == 2
        # Registry should now point to the new instance
        assert Departments._registry[1001] is dept2

    def test_from_api_response_handles_missing_fields(
        self, client: FreshServiceClient
    ) -> None:
        """Verify from_api_response handles missing optional fields."""
        Departments.set_client(client)
        Departments._registry.clear()

        minimal_data = {
            "id": 1003,
            "workspace_id": 2,
            "name": "Minimal Dept",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        dept = Department.from_api_response(minimal_data)

        assert dept.id == 1003
        assert dept.name == "Minimal Dept"
        assert dept.description == ""
        assert dept.head_user_id is None
        assert dept.domains == []
        assert dept.custom_fields == {}


class TestDepartmentModel:
    """Tests for Department model fields."""

    def test_department_default_workspace_id(
        self, client: FreshServiceClient, sample_department_data: dict
    ) -> None:
        """Verify department defaults workspace_id to 2."""
        Departments.set_client(client)
        Departments._registry.clear()

        # Remove workspace_id from data
        data_without_workspace = sample_department_data.copy()
        del data_without_workspace["workspace_id"]

        dept = Department.from_api_response(data_without_workspace)

        assert dept.workspace_id == 2  # Default value

    def test_department_custom_fields(
        self, client: FreshServiceClient, sample_department_data: dict
    ) -> None:
        """Verify department stores custom_fields correctly."""
        Departments.set_client(client)
        Departments._registry.clear()

        dept = Department.from_api_response(sample_department_data)

        assert dept.custom_fields == {"budget_code": "ENG-2024"}

    def test_department_domains_list(
        self, client: FreshServiceClient, sample_department_data: dict
    ) -> None:
        """Verify department stores domains as list."""
        Departments.set_client(client)
        Departments._registry.clear()

        dept = Department.from_api_response(sample_department_data)

        assert isinstance(dept.domains, list)
        assert dept.domains == ["engineering.example.com"]


class TestDepartmentsCollection:
    """Tests for Departments collection operations."""

    def test_from_api_response_creates_collection(
        self,
        client: FreshServiceClient,
        sample_department_data: dict,
        sample_department_data_2: dict,
    ) -> None:
        """Verify from_api_response creates Departments collection."""
        Departments.set_client(client)

        # Mock the list_departments call that happens in from_api_response
        with patch.object(
            client,
            "list_departments",
            return_value=[sample_department_data, sample_department_data_2],
        ):
            departments = Departments.from_api_response(
                [sample_department_data, sample_department_data_2], client=client
            )

            assert len(departments) == 2
            assert departments[0].name == "Engineering"
            assert departments[1].name == "Support"

    def test_find_by_name_uses_cache(
        self,
        client: FreshServiceClient,
        sample_department_data: dict,
        sample_department_data_2: dict,
    ) -> None:
        """Verify find_by_name loads cache and searches registry."""
        Departments.set_client(client)
        Departments._registry.clear()

        with patch.object(
            client,
            "list_departments",
            return_value=[sample_department_data, sample_department_data_2],
        ):
            departments = Departments.from_api_response([], client=client)
            dept = departments.find_by_name("Engineering")

            assert dept is not None
            assert dept.id == 1001
            assert dept.name == "Engineering"

    def test_find_by_name_case_insensitive(
        self,
        client: FreshServiceClient,
        sample_department_data: dict,
    ) -> None:
        """Verify find_by_name is case-insensitive."""
        Departments.set_client(client)
        Departments._registry.clear()

        with patch.object(
            client, "list_departments", return_value=[sample_department_data]
        ):
            departments = Departments.from_api_response([], client=client)
            dept1 = departments.find_by_name("engineering")
            dept2 = departments.find_by_name("ENGINEERING")
            dept3 = departments.find_by_name("Engineering")

            assert dept1 is not None
            assert dept1 is dept2
            assert dept2 is dept3

    def test_find_by_name_returns_none_when_not_found(
        self,
        client: FreshServiceClient,
        sample_department_data: dict,
    ) -> None:
        """Verify find_by_name returns None when department not found."""
        Departments.set_client(client)
        Departments._registry.clear()

        with patch.object(
            client, "list_departments", return_value=[sample_department_data]
        ):
            departments = Departments.from_api_response([], client=client)
            dept = departments.find_by_name("NonExistent")

            assert dept is None


class TestDepartmentsClientInitialization:
    """Tests for client initialization in registry."""

    def test_set_client_initializes_registry(
        self, client: FreshServiceClient
    ) -> None:
        """Verify set_client initializes the registry client."""
        Departments._client = None
        Departments.set_client(client)

        assert Departments._client is client

