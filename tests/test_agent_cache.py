"""
Tests for Agent caching and registry operations.

These tests verify the registry-based caching system for agents,
including cache hits, full list loading, __class_getitem__ behavior,
and lazy loading properties (groups, roles, departments, location).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from freshops import FreshServiceClient, FreshServiceConfig
from freshops.exceptions import EntityNotFoundError, RegistryClientNotInitializedError
from freshops.models.agent import Agent, Agents


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
def sample_agent_data() -> dict:
    """Sample agent data from API."""
    return {
        "id": 4001,
        "email": "john.doe@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "active": True,
        "occasional": False,
        "job_title": "Support Engineer",
        "work_phone_number": "555-0100",
        "mobile_phone_number": "555-0101",
        "address": "123 Main St",
        "department_ids": [1001, 1002],
        "can_see_all_tickets_from_associated_departments": True,
        "reporting_manager_id": 4000,
        "location_id": 1234,
        "time_zone": "America/Los_Angeles",
        "time_format": "12h",
        "language": "en",
        "background_information": "Experienced support engineer",
        "scoreboard_level_id": 3,
        "member_of": [2001, 2002],
        "observer_of": [2003],
        "member_of_pending_approval": [],
        "observer_of_pending_approval": [],
        "roles": [
            {
                "role_id": 3001,
                "assignment_scope": "entire_helpdesk",
                "groups": [],
            }
        ],
        "last_login_at": "2024-01-15T10:00:00Z",
        "last_active_at": "2024-01-15T14:30:00Z",
        "has_logged_in": True,
        "workspace_ids": [1],
        "api_key_enabled": False,
        "workspace_info": [],
        "custom_fields": {"employee_id": "EMP-4001"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-15T14:30:00Z",
    }


@pytest.fixture
def sample_agent_data_2() -> dict:
    """Second sample agent data."""
    return {
        "id": 4002,
        "email": "jane.smith@example.com",
        "first_name": "Jane",
        "last_name": "Smith",
        "active": True,
        "occasional": True,
        "job_title": "Part-time Support",
        "work_phone_number": "",
        "mobile_phone_number": "",
        "address": "",
        "department_ids": [],
        "can_see_all_tickets_from_associated_departments": False,
        "reporting_manager_id": None,
        "location_id": None,
        "time_zone": "",
        "time_format": "",
        "language": "en",
        "background_information": "",
        "scoreboard_level_id": None,
        "member_of": [],
        "observer_of": [],
        "member_of_pending_approval": [],
        "observer_of_pending_approval": [],
        "roles": [],
        "last_login_at": None,
        "last_active_at": None,
        "has_logged_in": False,
        "workspace_ids": [1],
        "api_key_enabled": False,
        "workspace_info": [],
        "custom_fields": {},
        "created_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }


@pytest.fixture
def sample_group_data() -> dict:
    """Sample group data for lazy loading tests."""
    return {
        "id": 2001,
        "name": "IT Support",
        "description": "IT Support group",
        "workspace_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_group_data_2() -> dict:
    """Second sample group data for lazy loading tests."""
    return {
        "id": 2002,
        "name": "Engineering",
        "description": "Engineering group",
        "workspace_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_role_data() -> dict:
    """Sample role data for lazy loading tests."""
    return {
        "id": 3001,
        "name": "Administrator",
        "description": "Full administrative access",
        "default": False,
        "role_type": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_department_data() -> dict:
    """Sample department data for lazy loading tests."""
    return {
        "id": 1001,
        "workspace_id": 2,
        "name": "Engineering",
        "description": "Engineering department",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_department_data_2() -> dict:
    """Second sample department data for lazy loading tests."""
    return {
        "id": 1002,
        "workspace_id": 2,
        "name": "Support",
        "description": "Support department",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_location_data() -> dict:
    """Sample location data for lazy loading tests."""
    return {
        "id": 1234,
        "name": "Main Office",
        "city": "Seattle",
        "state": "WA",
        "country": "USA",
        "workspace_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def clean_registry():
    """
    Automatically clean the Agents registry before each test.

    Ensures test isolation by clearing the cache and resetting flags.
    """
    # Clear registry before test
    Agents._registry.clear()
    Agents._full_list_loaded = False
    Agents._client = None
    yield
    # Clean up after test
    Agents._registry.clear()
    Agents._full_list_loaded = False
    Agents._client = None


class TestAgentsRegistry:
    """Tests for Agents registry operations."""

    def test_registry_returns_cached_agent(
        self, client: FreshServiceClient, sample_agent_data: dict
    ) -> None:
        """Verify Agents[4001] returns cached agent after loading."""
        Agents.set_client(client)

        # Load agent into cache first
        with patch.object(
            client, "get_agent", return_value=sample_agent_data
        ):
            agent1 = Agents[4001]

        # Second access should return same instance
        agent2 = Agents[4001]

        assert agent1 is agent2
        assert agent1.id == 4001
        assert agent1.email == "john.doe@example.com"

    def test_registry_loads_single_agent(
        self, client: FreshServiceClient, sample_agent_data: dict
    ) -> None:
        """Verify Agents[agent_id] uses single-fetch pattern."""
        Agents.set_client(client)

        with patch.object(
            client, "get_agent", return_value=sample_agent_data
        ) as mock_get:
            agent = Agents[4001]

            # Should have called get_agent (single-fetch pattern)
            assert mock_get.call_count == 1
            assert agent.id == 4001
            assert agent.email == "john.doe@example.com"
            assert len(Agents._registry) == 1

    def test_registry_raises_when_not_found(
        self, client: FreshServiceClient
    ) -> None:
        """Verify Agents[9999] raises ValueError when agent doesn't exist."""
        Agents.set_client(client)

        with patch.object(
            client, "get_agent", side_effect=ValueError("Agent not found")
        ):
            with pytest.raises(EntityNotFoundError, match="Agent 9999 not found"):
                _ = Agents[9999]

    def test_registry_requires_client(self) -> None:
        """Verify Agents[agent_id] requires client to be set."""
        Agents._client = None

        with pytest.raises(RegistryClientNotInitializedError, match="Agents registry client not initialized"):
            _ = Agents[4001]


class TestAgentFromApiResponse:
    """Tests for Agent.from_api_response caching."""

    def test_from_api_response_caches_agent(
        self, client: FreshServiceClient, sample_agent_data: dict
    ) -> None:
        """Verify from_api_response stores agent in registry."""
        Agents.set_client(client)
        Agents._registry.clear()

        agent = Agent.from_api_response(sample_agent_data)

        assert agent.id == 4001
        assert agent.email == "john.doe@example.com"
        assert agent.first_name == "John"
        assert 4001 in Agents._registry
        assert Agents._registry[4001] is agent

    def test_from_api_response_updates_existing(
        self, client: FreshServiceClient, sample_agent_data: dict
    ) -> None:
        """Verify from_api_response replaces existing cached agent."""
        Agents.set_client(client)
        Agents._registry.clear()

        # Create agent with just ID (via registry) - mock the API call
        with patch.object(
            client, "get_agent", return_value=sample_agent_data
        ):
            agent1 = Agents[4001]
            assert agent1.email == "john.doe@example.com"  # Loaded from API

        # Now update it with full data (creates new instance and replaces in cache)
        updated_data = sample_agent_data.copy()
        updated_data["email"] = "john.updated@example.com"
        agent2 = Agent.from_api_response(updated_data)

        # from_api_response creates a new instance (authoritative source)
        # but it replaces the old one in the registry
        assert agent2.id == agent1.id
        assert agent2.email == "john.updated@example.com"
        # Registry should now point to the new instance
        assert Agents._registry[4001] is agent2

    def test_from_api_response_handles_missing_fields(
        self, client: FreshServiceClient
    ) -> None:
        """Verify from_api_response handles missing optional fields."""
        Agents.set_client(client)
        Agents._registry.clear()

        minimal_data = {
            "id": 4003,
            "email": "minimal@example.com",
            "first_name": "Minimal",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        agent = Agent.from_api_response(minimal_data)

        assert agent.id == 4003
        assert agent.email == "minimal@example.com"
        assert agent.first_name == "Minimal"
        assert agent.last_name == ""
        assert agent.active is True
        assert agent.department_ids == []
        assert agent.member_of == []


class TestAgentModel:
    """Tests for Agent model fields and properties."""

    def test_agent_full_name(
        self, client: FreshServiceClient, sample_agent_data: dict
    ) -> None:
        """Verify agent full_name property."""
        Agents.set_client(client)
        Agents._registry.clear()

        agent = Agent.from_api_response(sample_agent_data)

        assert agent.full_name == "John Doe"

    def test_agent_is_active(
        self, client: FreshServiceClient, sample_agent_data: dict
    ) -> None:
        """Verify agent is_active property."""
        Agents.set_client(client)
        Agents._registry.clear()

        agent = Agent.from_api_response(sample_agent_data)

        assert agent.active is True
        assert agent.is_active is True

    def test_agent_is_occasional(
        self, client: FreshServiceClient, sample_agent_data_2: dict
    ) -> None:
        """Verify agent is_occasional property."""
        Agents.set_client(client)
        Agents._registry.clear()

        agent = Agent.from_api_response(sample_agent_data_2)

        assert agent.occasional is True
        assert agent.is_occasional is True

    def test_agent_role_ids(
        self, client: FreshServiceClient, sample_agent_data: dict
    ) -> None:
        """Verify agent role_ids property extracts role IDs."""
        Agents.set_client(client)
        Agents._registry.clear()

        agent = Agent.from_api_response(sample_agent_data)

        assert agent.role_ids == [3001]

    def test_agent_has_role(
        self, client: FreshServiceClient, sample_agent_data: dict
    ) -> None:
        """Verify agent has_role method."""
        Agents.set_client(client)
        Agents._registry.clear()

        agent = Agent.from_api_response(sample_agent_data)

        assert agent.has_role(3001) is True
        assert agent.has_role(9999) is False


class TestAgentLazyLoading:
    """Tests for Agent lazy loading properties."""

    def test_agent_groups_property(
        self,
        client: FreshServiceClient,
        sample_agent_data: dict,
        sample_group_data: dict,
        sample_group_data_2: dict,
    ) -> None:
        """Verify agent.groups property lazy loads groups."""
        Agents.set_client(client)
        Agents._registry.clear()

        # Import Groups to set up its registry
        from freshops.models.group import Groups

        Groups.set_client(client)
        Groups._registry.clear()

        # Create agent (mock list_agents to prevent full list loading)
        with patch.object(client, "list_agents", return_value=[sample_agent_data]):
            agent = Agent.from_api_response(sample_agent_data)

        # Mock Groups registry lookup (load-all pattern)
        # Must return all groups that the agent references (2001, 2002)
        with patch.object(
            client, "list_groups", return_value=[sample_group_data, sample_group_data_2]
        ):
            groups = agent.groups

            assert len(groups) == 2  # member_of has 2 IDs
            # Groups are loaded from registry
            assert all(group.id in [2001, 2002] for group in groups)

    def test_agent_role_objects_property(
        self,
        client: FreshServiceClient,
        sample_agent_data: dict,
        sample_role_data: dict,
    ) -> None:
        """Verify agent.role_objects property lazy loads roles."""
        Agents.set_client(client)
        Agents._registry.clear()

        # Import Roles to set up its registry
        from freshops.models.role import Roles

        Roles.set_client(client)
        Roles._registry.clear()

        # Create agent (mock list_agents to prevent full list loading)
        with patch.object(client, "list_agents", return_value=[sample_agent_data]):
            agent = Agent.from_api_response(sample_agent_data)

        # Mock Roles registry lookup (load-all pattern)
        with patch.object(
            client, "list_roles", return_value=[sample_role_data]
        ):
            roles = agent.role_objects

            assert len(roles) == 1
            assert roles[0].id == 3001

    def test_agent_departments_property(
        self,
        client: FreshServiceClient,
        sample_agent_data: dict,
        sample_department_data: dict,
        sample_department_data_2: dict,
    ) -> None:
        """Verify agent.departments property lazy loads departments."""
        Agents.set_client(client)
        Agents._registry.clear()

        # Import Departments to set up its registry
        from freshops.models.department import Departments

        Departments.set_client(client)
        Departments._registry.clear()

        # Create agent (mock list_agents to prevent full list loading)
        with patch.object(client, "list_agents", return_value=[sample_agent_data]):
            agent = Agent.from_api_response(sample_agent_data)

        # Mock Departments registry lookup (load-all pattern)
        # Must return all departments that the agent references (1001, 1002)
        with patch.object(
            client,
            "list_departments",
            return_value=[sample_department_data, sample_department_data_2],
        ):
            departments = agent.departments

            assert len(departments) == 2  # department_ids has 2 IDs
            # Departments are loaded from registry
            assert all(dept.id in [1001, 1002] for dept in departments)

    def test_agent_location_property(
        self,
        client: FreshServiceClient,
        sample_agent_data: dict,
        sample_location_data: dict,
    ) -> None:
        """Verify agent.location property lazy loads location."""
        Agents.set_client(client)
        Agents._registry.clear()

        # Import Locations to set up its registry
        from freshops.models.location import Locations

        Locations.set_client(client)
        Locations._registry.clear()

        # Create agent (mock list_agents to prevent full list loading)
        with patch.object(client, "list_agents", return_value=[sample_agent_data]):
            agent = Agent.from_api_response(sample_agent_data)

        # Mock Locations registry lookup (single-fetch pattern)
        with patch.object(
            client, "get_location", return_value=sample_location_data
        ):
            location = agent.location

            assert location is not None
            assert location.id == 1234
            assert location.name == "Main Office"

    def test_agent_location_property_none(
        self, client: FreshServiceClient, sample_agent_data_2: dict
    ) -> None:
        """Verify agent.location property returns None when no location_id."""
        Agents.set_client(client)
        Agents._registry.clear()

        # Create agent without location_id (mock list_agents to prevent full list loading)
        with patch.object(client, "list_agents", return_value=[sample_agent_data_2]):
            agent = Agent.from_api_response(sample_agent_data_2)

            assert agent.location is None


class TestAgentsCollection:
    """Tests for Agents collection operations."""

    def test_from_api_response_creates_collection(
        self,
        client: FreshServiceClient,
        sample_agent_data: dict,
        sample_agent_data_2: dict,
    ) -> None:
        """Verify from_api_response creates Agents collection."""
        Agents.set_client(client)

        # Mock list_agents to prevent real API call during full list loading
        with patch.object(
            client,
            "list_agents",
            return_value=[sample_agent_data, sample_agent_data_2],
        ):
            agents = Agents.from_api_response(
                [sample_agent_data, sample_agent_data_2], client=client
            )

            assert len(agents) == 2
            assert agents[0].email == "john.doe@example.com"
            assert agents[1].email == "jane.smith@example.com"


class TestAgentsClientInitialization:
    """Tests for client initialization in registry."""

    def test_set_client_initializes_registry(
        self, client: FreshServiceClient
    ) -> None:
        """Verify set_client initializes the registry client."""
        Agents._client = None
        Agents.set_client(client)

        assert Agents._client is client

