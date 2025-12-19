"""
Tests for Group caching and registry operations.

These tests verify the registry-based caching system for groups,
including cache hits, full list loading, and __class_getitem__ behavior.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from freshops import FreshServiceClient, FreshServiceConfig
from freshops.exceptions import EntityNotFoundError, RegistryClientNotInitializedError
from freshops.models.group import Group, Groups


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
def sample_group_data() -> dict:
    """Sample group data from API."""
    return {
        "id": 2001,
        "name": "IT Support",
        "description": "IT Support group",
        "workspace_id": 1,
        "unassigned_for": "2h",
        "business_hours_id": 100,
        "escalate_to": 5001,
        "leaders": [1001, 1002],
        "members": [2001, 2002, 2003],
        "observers": [3001],
        "restricted": False,
        "approval_required": False,
        "auto_ticket_assign": True,
        "members_pending_approval": [],
        "observers_pending_approval": [],
        "leaders_pending_approval": [],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_group_data_2() -> dict:
    """Second sample group data."""
    return {
        "id": 2002,
        "name": "Engineering",
        "description": "Engineering group",
        "workspace_id": 1,
        "unassigned_for": "4h",
        "business_hours_id": None,
        "escalate_to": None,
        "leaders": [1003],
        "members": [2004, 2005],
        "observers": [],
        "restricted": True,
        "approval_required": True,
        "auto_ticket_assign": False,
        "members_pending_approval": [2006],
        "observers_pending_approval": [3002],
        "leaders_pending_approval": [],
        "created_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def clean_registry():
    """
    Automatically clean the Groups registry before each test.

    Ensures test isolation by clearing the cache and resetting flags.
    """
    # Clear registry before test
    Groups._registry.clear()
    Groups._full_list_loaded = False
    Groups._client = None
    yield
    # Clean up after test
    Groups._registry.clear()
    Groups._full_list_loaded = False
    Groups._client = None


class TestGroupsRegistry:
    """Tests for Groups registry operations."""

    def test_registry_returns_cached_group(
        self, client: FreshServiceClient, sample_group_data: dict
    ) -> None:
        """Verify Groups[2001] returns cached group after loading."""
        Groups.set_client(client)

        # Load group into cache first
        with patch.object(
            client, "list_groups", return_value=[sample_group_data]
        ):
            group1 = Groups[2001]

        # Second access should return same instance
        group2 = Groups[2001]

        assert group1 is group2
        assert group1.id == 2001
        assert group1.name == "IT Support"

    def test_registry_loads_all_when_not_found(
        self,
        client: FreshServiceClient,
        sample_group_data: dict,
        sample_group_data_2: dict,
    ) -> None:
        """Verify Groups[group_id] loads all groups if not in cache."""
        Groups.set_client(client)

        with patch.object(
            client,
            "list_groups",
            return_value=[sample_group_data, sample_group_data_2],
        ) as mock_list:
            group = Groups[2001]

            # Should have loaded all groups
            assert mock_list.call_count == 1
            assert group.id == 2001
            assert group.name == "IT Support"
            assert len(Groups._registry) == 2

    def test_registry_raises_when_not_found(
        self, client: FreshServiceClient, sample_group_data: dict
    ) -> None:
        """Verify Groups[9999] raises ValueError when group doesn't exist."""
        Groups.set_client(client)

        with patch.object(
            client, "list_groups", return_value=[sample_group_data]
        ):
            with pytest.raises(EntityNotFoundError, match="Group 9999 not found"):
                _ = Groups[9999]

    def test_registry_requires_client(self) -> None:
        """Verify Groups[group_id] requires client to be set."""
        Groups._client = None

        with pytest.raises(RegistryClientNotInitializedError, match="Groups registry client not initialized"):
            _ = Groups[2001]


class TestGroupFromApiResponse:
    """Tests for Group.from_api_response caching."""

    def test_from_api_response_caches_group(
        self, client: FreshServiceClient, sample_group_data: dict
    ) -> None:
        """Verify from_api_response stores group in registry."""
        Groups.set_client(client)
        Groups._registry.clear()

        group = Group.from_api_response(sample_group_data)

        assert group.id == 2001
        assert group.name == "IT Support"
        assert group.workspace_id == 1
        assert 2001 in Groups._registry
        assert Groups._registry[2001] is group

    def test_from_api_response_updates_existing(
        self, client: FreshServiceClient, sample_group_data: dict
    ) -> None:
        """Verify from_api_response replaces existing cached group."""
        Groups.set_client(client)
        Groups._registry.clear()

        # Create group with just ID (via registry) - mock the API call
        with patch.object(
            client, "list_groups", return_value=[sample_group_data]
        ):
            group1 = Groups[2001]
            assert group1.name == "IT Support"  # Loaded from API

        # Now update it with full data (creates new instance and replaces in cache)
        updated_data = sample_group_data.copy()
        updated_data["name"] = "Updated IT Support"
        group2 = Group.from_api_response(updated_data)

        # from_api_response creates a new instance (authoritative source)
        # but it replaces the old one in the registry
        assert group2.id == group1.id
        assert group2.name == "Updated IT Support"
        assert group2.workspace_id == 1
        # Registry should now point to the new instance
        assert Groups._registry[2001] is group2

    def test_from_api_response_handles_missing_fields(
        self, client: FreshServiceClient
    ) -> None:
        """Verify from_api_response handles missing optional fields."""
        Groups.set_client(client)
        Groups._registry.clear()

        minimal_data = {
            "id": 2003,
            "name": "Minimal Group",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        group = Group.from_api_response(minimal_data)

        assert group.id == 2003
        assert group.name == "Minimal Group"
        assert group.description == ""
        assert group.workspace_id is None
        assert group.leaders == []
        assert group.members == []
        assert group.observers == []
        assert group.restricted is False


class TestGroupModel:
    """Tests for Group model fields."""

    def test_group_member_lists(
        self, client: FreshServiceClient, sample_group_data: dict
    ) -> None:
        """Verify group stores member lists correctly."""
        Groups.set_client(client)
        Groups._registry.clear()

        group = Group.from_api_response(sample_group_data)

        assert isinstance(group.leaders, list)
        assert group.leaders == [1001, 1002]
        assert isinstance(group.members, list)
        assert group.members == [2001, 2002, 2003]
        assert isinstance(group.observers, list)
        assert group.observers == [3001]

    def test_group_pending_approval_lists(
        self, client: FreshServiceClient, sample_group_data_2: dict
    ) -> None:
        """Verify group stores pending approval lists correctly."""
        Groups.set_client(client)
        Groups._registry.clear()

        group = Group.from_api_response(sample_group_data_2)

        assert isinstance(group.members_pending_approval, list)
        assert group.members_pending_approval == [2006]
        assert isinstance(group.observers_pending_approval, list)
        assert group.observers_pending_approval == [3002]
        assert isinstance(group.leaders_pending_approval, list)
        assert group.leaders_pending_approval == []

    def test_group_restricted_flag(
        self, client: FreshServiceClient, sample_group_data_2: dict
    ) -> None:
        """Verify group restricted and approval_required flags."""
        Groups.set_client(client)
        Groups._registry.clear()

        group = Group.from_api_response(sample_group_data_2)

        assert group.restricted is True
        assert group.approval_required is True
        assert group.auto_ticket_assign is False

    def test_group_all_agent_ids(
        self, client: FreshServiceClient, sample_group_data: dict
    ) -> None:
        """Verify all_agent_ids property combines leaders, members, observers."""
        Groups.set_client(client)
        Groups._registry.clear()

        group = Group.from_api_response(sample_group_data)

        all_ids = group.all_agent_ids
        assert isinstance(all_ids, list)
        # Should contain all unique IDs from leaders, members, observers
        assert 1001 in all_ids  # leader
        assert 1002 in all_ids  # leader
        assert 2001 in all_ids  # member
        assert 2002 in all_ids  # member
        assert 2003 in all_ids  # member
        assert 3001 in all_ids  # observer
        # Should not have duplicates
        assert len(all_ids) == len(set(all_ids))


class TestGroupsCollection:
    """Tests for Groups collection operations."""

    def test_from_api_response_creates_collection(
        self,
        client: FreshServiceClient,
        sample_group_data: dict,
        sample_group_data_2: dict,
    ) -> None:
        """Verify from_api_response creates Groups collection."""
        Groups.set_client(client)

        # Mock the list_groups call that happens in from_api_response
        with patch.object(
            client,
            "list_groups",
            return_value=[sample_group_data, sample_group_data_2],
        ):
            groups = Groups.from_api_response(
                [sample_group_data, sample_group_data_2], client=client
            )

            assert len(groups) == 2
            assert groups[0].name == "IT Support"
            assert groups[1].name == "Engineering"

    def test_find_by_name_uses_cache(
        self,
        client: FreshServiceClient,
        sample_group_data: dict,
        sample_group_data_2: dict,
    ) -> None:
        """Verify find_by_name loads cache and searches registry."""
        Groups.set_client(client)
        Groups._registry.clear()

        with patch.object(
            client,
            "list_groups",
            return_value=[sample_group_data, sample_group_data_2],
        ):
            groups = Groups.from_api_response([], client=client)
            group = groups.find_by_name("IT Support")

            assert group is not None
            assert group.id == 2001
            assert group.name == "IT Support"

    def test_find_by_name_case_insensitive(
        self,
        client: FreshServiceClient,
        sample_group_data: dict,
    ) -> None:
        """Verify find_by_name is case-insensitive."""
        Groups.set_client(client)
        Groups._registry.clear()

        with patch.object(
            client, "list_groups", return_value=[sample_group_data]
        ):
            groups = Groups.from_api_response([], client=client)
            group1 = groups.find_by_name("it support")
            group2 = groups.find_by_name("IT SUPPORT")
            group3 = groups.find_by_name("IT Support")

            assert group1 is not None
            assert group1 is group2
            assert group2 is group3

    def test_find_by_name_returns_none_when_not_found(
        self,
        client: FreshServiceClient,
        sample_group_data: dict,
    ) -> None:
        """Verify find_by_name returns None when group not found."""
        Groups.set_client(client)
        Groups._registry.clear()

        with patch.object(
            client, "list_groups", return_value=[sample_group_data]
        ):
            groups = Groups.from_api_response([], client=client)
            group = groups.find_by_name("NonExistent")

            assert group is None

    def test_restricted_filter(
        self,
        client: FreshServiceClient,
        sample_group_data: dict,
        sample_group_data_2: dict,
    ) -> None:
        """Verify restricted() filter returns only restricted groups."""
        Groups.set_client(client)
        Groups._registry.clear()

        with patch.object(
            client,
            "list_groups",
            return_value=[sample_group_data, sample_group_data_2],
        ):
            groups = Groups.from_api_response([], client=client)
            restricted_groups = groups.restricted()

            assert len(restricted_groups) == 1
            assert restricted_groups[0].id == 2002
            assert restricted_groups[0].restricted is True


class TestGroupsClientInitialization:
    """Tests for client initialization in registry."""

    def test_set_client_initializes_registry(
        self, client: FreshServiceClient
    ) -> None:
        """Verify set_client initializes the registry client."""
        Groups._client = None
        Groups.set_client(client)

        assert Groups._client is client

