"""
Tests for Location caching and registry operations.

These tests verify the registry-based caching system for locations,
including immediate loading (single-fetch pattern), cache hits, and full list loading.

Location now works consistently with other models (Agent, Group, Role, Department):
- No model-level lazy loading (all fields are standard dataclass fields)
- Locations[1234] loads immediately via get_location() API call
- All data is available immediately after Locations[1234] returns
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from freshops import FreshServiceClient, FreshServiceConfig
from freshops.exceptions import EntityNotFoundError, RegistryClientNotInitializedError
from freshops.models.location import Location, Locations


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
def sample_location_data() -> dict:
    """Sample location data from API."""
    return {
        "id": 1234,
        "name": "Main Office",
        "city": "Seattle",
        "state": "WA",
        "country": "USA",
        "line1": "123 Main St",
        "line2": "",
        "zipcode": "98101",
        "workspace_id": 1,
        "parent_location_id": None,
        "primary_contact_id": 100,
        "contact_name": "John Doe",
        "email": "office@example.com",
        "phone": "555-1234",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_location_data_2() -> dict:
    """Second sample location data."""
    return {
        "id": 5678,
        "name": "Remote Office",
        "city": "Portland",
        "state": "OR",
        "country": "USA",
        "line1": "456 Oak Ave",
        "line2": "",
        "zipcode": "97201",
        "workspace_id": 1,
        "parent_location_id": None,
        "primary_contact_id": None,
        "contact_name": "",
        "email": "",
        "phone": "",
        "created_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def clean_registry():
    """
    Automatically clean the Locations registry before each test.

    Ensures test isolation by clearing the cache and resetting flags.
    """
    # Clear registry before test
    Locations._registry.clear()
    Locations._full_list_loaded = False
    Locations._client = None
    yield
    # Clean up after test
    Locations._registry.clear()
    Locations._full_list_loaded = False
    Locations._client = None


class TestLocationsRegistry:
    """Tests for Locations registry operations."""

    def test_registry_creates_new_location(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify Locations[1234] fetches and creates a new Location instance."""
        Locations.set_client(client)

        with patch.object(client, "get_location", return_value=sample_location_data):
            location = Locations[1234]

            assert location.id == 1234
            assert location.name == "Main Office"
            assert 1234 in Locations._registry
            assert Locations._registry[1234] is location

    def test_registry_returns_cached_location(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify Locations[1234] returns same instance on second call."""
        Locations.set_client(client)

        with patch.object(client, "get_location", return_value=sample_location_data):
            location1 = Locations[1234]
            location2 = Locations[1234]

            assert location1 is location2
            assert id(location1) == id(location2)

    def test_registry_handles_multiple_locations(
        self,
        client: FreshServiceClient,
        sample_location_data: dict,
        sample_location_data_2: dict,
    ) -> None:
        """Verify registry handles multiple different location IDs."""
        Locations.set_client(client)

        def get_location_side_effect(location_id: int) -> dict:
            if location_id == 1234:
                return sample_location_data
            elif location_id == 5678:
                return sample_location_data_2
            raise ValueError(f"Location {location_id} not found")

        with patch.object(
            client, "get_location", side_effect=get_location_side_effect
        ):
            loc1 = Locations[1234]
            loc2 = Locations[5678]
            loc3 = Locations[1234]  # Should return same as loc1

            assert loc1.id == 1234
            assert loc2.id == 5678
            assert loc3 is loc1  # Same instance
            assert loc2 is not loc1  # Different instance
            assert len(Locations._registry) == 2


class TestLocationLoading:
    """Tests for location loading behavior."""

    def test_accessing_id_after_load(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify accessing location.id works (data loaded immediately)."""
        Locations.set_client(client)
        Locations._registry.clear()

        with patch.object(client, "get_location", return_value=sample_location_data) as mock_get:
            location = Locations[1234]  # This triggers the API call
            _ = location.id  # Access id

            mock_get.assert_called_once_with(1234)

    def test_accessing_name_uses_loaded_data(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify accessing location.name works (data loaded immediately)."""
        Locations.set_client(client)
        Locations._registry.clear()

        with patch.object(client, "get_location", return_value=sample_location_data) as mock_get:
            location = Locations[1234]  # API call happens here
            name = location.name  # Access name - data already loaded

            assert mock_get.call_count == 1
            assert name == "Main Office"
            assert location.city == "Seattle"
            assert location.country == "USA"

    def test_accessing_cached_field_uses_cache(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify accessing multiple fields works (data loaded immediately)."""
        Locations.set_client(client)
        Locations._registry.clear()

        with patch.object(client, "get_location", return_value=sample_location_data) as mock_get:
            location = Locations[1234]  # API call happens here
            _ = location.name  # First access - data already loaded
            _ = location.city  # Second access - uses loaded data
            _ = location.country  # Third access - uses loaded data

            # Should only call API once (during Locations[1234])
            assert mock_get.call_count == 1

    def test_cache_hit_from_registry(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify accessing location that's already in registry uses cache."""
        Locations.set_client(client)
        Locations._registry.clear()

        # First, create and load a location
        with patch.object(client, "get_location", return_value=sample_location_data) as mock_get:
            location1 = Locations[1234]  # API call happens here
            assert mock_get.call_count == 1
            assert location1.name == "Main Office"

        # Now create a new reference - should use cached data
        with patch.object(client, "get_location") as mock_get2:
            location2 = Locations[1234]  # Should use cache, not call API
            _ = location2.name  # Data already loaded

            assert location2 is location1  # Same instance
            assert location2.name == "Main Office"
            mock_get2.assert_not_called()  # No new API call

    def test_location_not_found_handling(
        self, client: FreshServiceClient
    ) -> None:
        """Verify handling when location doesn't exist."""
        Locations.set_client(client)
        Locations._registry.clear()

        with patch.object(
            client, "get_location", side_effect=ValueError("Location not found")
        ):
            # Error should be raised during Locations[9999], not when accessing name
            with pytest.raises(EntityNotFoundError, match="Location 9999 not found"):
                _ = Locations[9999]


class TestLocationFromApiResponse:
    """Tests for Location.from_api_response caching."""

    def test_from_api_response_caches_location(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify from_api_response stores location in registry."""
        Locations.set_client(client)
        Locations._registry.clear()

        location = Location.from_api_response(sample_location_data)

        assert location.id == 1234
        assert location.name == "Main Office"
        assert 1234 in Locations._registry
        assert Locations._registry[1234] is location

    def test_from_api_response_updates_existing(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify from_api_response updates existing cached location."""
        Locations.set_client(client)
        Locations._registry.clear()

        # Create location via API call (standardized pattern)
        with patch.object(client, "get_location", return_value=sample_location_data):
            location1 = Locations[1234]
            assert location1.name == "Main Office"

        # Now update it with new data
        updated_data = sample_location_data.copy()
        updated_data["name"] = "Updated Main Office"
        location2 = Location.from_api_response(updated_data)

        # from_api_response creates a new instance and replaces in cache
        assert location2.id == location1.id
        assert location2.name == "Updated Main Office"
        assert Locations._registry[1234] is location2  # New instance in cache


class TestFullListLoading:
    """Tests for full list loading into cache."""

    def test_ensure_cache_loaded_loads_all(
        self,
        client: FreshServiceClient,
        sample_location_data: dict,
        sample_location_data_2: dict,
    ) -> None:
        """Verify _ensure_cache_loaded loads all locations."""
        Locations.set_client(client)
        Locations._registry.clear()
        Locations._full_list_loaded = False

        with patch.object(
            client,
            "list_locations",
            return_value=[sample_location_data, sample_location_data_2],
        ):
            locations = Locations.from_api_response([])
            locations._ensure_cache_loaded()

            assert Locations._full_list_loaded is True
            assert len(Locations._registry) == 2
            assert 1234 in Locations._registry
            assert 5678 in Locations._registry

    def test_ensure_cache_loaded_only_loads_once(
        self,
        client: FreshServiceClient,
        sample_location_data: dict,
        sample_location_data_2: dict,
    ) -> None:
        """Verify _ensure_cache_loaded only loads once."""
        Locations.set_client(client)
        Locations._registry.clear()
        Locations._full_list_loaded = False

        with patch.object(
            client,
            "list_locations",
            return_value=[sample_location_data, sample_location_data_2],
        ) as mock_list:
            locations = Locations.from_api_response([])
            locations._ensure_cache_loaded()  # First call
            locations._ensure_cache_loaded()  # Second call - should not reload

            assert mock_list.call_count == 1
            assert Locations._full_list_loaded is True

    def test_filtering_uses_cached_data(
        self,
        client: FreshServiceClient,
        sample_location_data: dict,
        sample_location_data_2: dict,
    ) -> None:
        """Verify filtering operations use cached full list."""
        Locations.set_client(client)
        Locations._registry.clear()
        Locations._full_list_loaded = False

        with patch.object(
            client,
            "list_locations",
            return_value=[sample_location_data, sample_location_data_2],
        ):
            locations = Locations.from_api_response([])
            # This should trigger full list load
            seattle_locs = locations.in_city("Seattle")

            assert len(seattle_locs) == 1
            assert seattle_locs[0].name == "Main Office"
            assert Locations._full_list_loaded is True


class TestLocationClientInitialization:
    """Tests for client initialization in registry."""

    def test_set_client_initializes_registry(
        self, client: FreshServiceClient
    ) -> None:
        """Verify set_client initializes the registry client."""
        Locations._client = None
        Locations.set_client(client)

        assert Locations._client is client

    def test_registry_requires_client(
        self, sample_location_data: dict
    ) -> None:
        """Verify Locations[1234] requires client to be set."""
        Locations._client = None
        Locations._registry.clear()

        # Error should be raised when trying to fetch without client
        with pytest.raises(RegistryClientNotInitializedError, match="Locations registry client not initialized"):
            _ = Locations[1234]


class TestLocationProperties:
    """Tests for Location computed properties."""

    def test_full_address_property(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify full_address property works."""
        Locations.set_client(client)
        Locations._registry.clear()

        with patch.object(client, "get_location", return_value=sample_location_data):
            location = Locations[1234]
            address = location.full_address

            assert "123 Main St" in address
            assert "Seattle" in address
            assert "WA" in address
            assert "98101" in address
            assert "USA" in address

    def test_is_child_location_property(
        self, client: FreshServiceClient, sample_location_data: dict
    ) -> None:
        """Verify is_child_location property works."""
        Locations.set_client(client)
        Locations._registry.clear()

        # Test with no parent
        with patch.object(client, "get_location", return_value=sample_location_data):
            location = Locations[1234]
            assert location.is_child_location is False

        # Test with parent
        sample_location_data["parent_location_id"] = 9999
        with patch.object(client, "get_location", return_value=sample_location_data):
            location2 = Locations[5678]
            assert location2.is_child_location is True

