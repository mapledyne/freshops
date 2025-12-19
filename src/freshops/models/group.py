"""
Group model for FreshService agent groups.

Provides typed access to group data returned by the FreshService API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from freshops.exceptions import InvalidEntityIdError
from freshops.models.base import CachedCollection, FreshModel
from loguru import logger


@dataclass(eq=False, repr=False)  # Use FreshModel.__eq__ and __repr__ instead
class Group(FreshModel):
    """
    Represents a FreshService agent group.

    Groups organize agents for ticket assignment and permissions.

    :ivar id: Unique group identifier
    :ivar name: Group name (mandatory)
    :ivar description: Group description
    :ivar workspace_id: ID of the workspace this group belongs to
    :ivar unassigned_for: Time string before escalation ("30m", "1h", "2h", "4h", "8h", "12h", "1d", "2d", "3d")
    :ivar business_hours_id: Unique ID of business hours configuration
    :ivar escalate_to: User ID to escalate to if ticket is unassigned (null for none)
    :ivar leaders: List of agent IDs who are group leaders
    :ivar members: List of agent IDs who are group members (approved)
    :ivar observers: List of agent IDs who are group observers (approved)
    :ivar restricted: Whether this is a restricted group
    :ivar approval_required: Whether the restricted group requires approvals
    :ivar auto_ticket_assign: Whether automatic ticket assignment is enabled
    :ivar members_pending_approval: Agent IDs whose member access is pending (read-only)
    :ivar observers_pending_approval: Agent IDs whose observer access is pending (read-only)
    :ivar leaders_pending_approval: Agent IDs whose leader access is pending (read-only)
    :ivar created_at: When the group was created
    :ivar updated_at: When the group was last updated
    :ivar raw_data: The original API response dictionary

    Example::

        group = Group.from_api_response(api_data)
        print(f"{group.name} ({len(group.members)} members)")
    """

    _id: int
    _name: str = ""

    @property
    def id(self) -> int:
        """Get the group's unique identifier."""
        return self._id

    @property
    def name(self) -> str:
        """Get the group name."""
        return self._name

    description: str = ""
    workspace_id: int | None = None
    # TODO: Convert unassigned_for to use timedelta internally, parsing from string format ("30m", "1h", etc.)
    unassigned_for: str | None = None
    business_hours_id: int | None = None
    escalate_to: int | None = None
    leaders: list[int] = field(default_factory=list)
    members: list[int] = field(default_factory=list)
    observers: list[int] = field(default_factory=list)
    restricted: bool = False
    approval_required: bool = False
    auto_ticket_assign: bool = False
    members_pending_approval: list[int] = field(default_factory=list)
    observers_pending_approval: list[int] = field(default_factory=list)
    leaders_pending_approval: list[int] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Group:
        """
        Create a Group instance from an API response dictionary.

        Always creates a new instance from the API data and updates the cache.
        This ensures the cache always contains the authoritative data from the API.

        :param data: Dictionary from the FreshService API
        :returns: A new Group instance (cached in registry)
        """
        # Import here to avoid circular dependency at module load time
        from freshops.models.group import Groups

        group_id = data.get("id", 0)
        if not group_id or group_id <= 0:
            raise InvalidEntityIdError("Group", group_id)

        # Validate required fields
        name = cls._validate_required_field(data.get("name"), "name")

        # Validate list fields
        leaders = cls._validate_list_of_type(data.get("leaders", []), int, "leaders")
        members = cls._validate_list_of_type(data.get("members", []), int, "members")
        observers = cls._validate_list_of_type(data.get("observers", []), int, "observers")
        members_pending_approval = cls._validate_list_of_type(
            data.get("members_pending_approval", []), int, "members_pending_approval"
        )
        observers_pending_approval = cls._validate_list_of_type(
            data.get("observers_pending_approval", []), int, "observers_pending_approval"
        )
        leaders_pending_approval = cls._validate_list_of_type(
            data.get("leaders_pending_approval", []), int, "leaders_pending_approval"
        )

        # Always create a new instance from API data (authoritative source)
        group = cls(
            _id=group_id,
            _name=name,
            description=data.get("description", "") or "",
            workspace_id=data.get("workspace_id"),
            unassigned_for=data.get("unassigned_for"),
            business_hours_id=data.get("business_hours_id"),
            escalate_to=data.get("escalate_to"),
            leaders=leaders,
            members=members,
            observers=observers,
            restricted=cls._validate_type(data.get("restricted", False), bool, "restricted"),
            approval_required=cls._validate_type(
                data.get("approval_required", False), bool, "approval_required"
            ),
            auto_ticket_assign=cls._validate_type(
                data.get("auto_ticket_assign", False), bool, "auto_ticket_assign"
            ),
            members_pending_approval=members_pending_approval,
            observers_pending_approval=observers_pending_approval,
            leaders_pending_approval=leaders_pending_approval,
            created_at=cls.parse_datetime(data.get("created_at")),
            updated_at=cls.parse_datetime(data.get("updated_at")),
            raw_data=data,
        )
        # Update cache with authoritative data (replaces existing if present)
        Groups._registry[group_id] = group
        logger.debug(f"Group {group_id} created/updated in cache")
        return group

    @property
    def is_restricted(self) -> bool:
        """Check if this is a restricted group."""
        return self.restricted

    @property
    def member_count(self) -> int:
        """Get the number of members in the group."""
        return len(self.members)

    @property
    def all_agent_ids(self) -> list[int]:
        """Get all agent IDs associated with this group."""
        return list(set(self.leaders + self.members + self.observers))

    @property
    def member_objects(self) -> list[Any]:
        """
        Get the group's member agents (lazy loading via registry).

        Returns a list of Agent objects from the Agents registry.
        Accessing agent.id works immediately. Accessing other
        fields triggers an API call to load the full data for that agent.

        Missing or deleted agents are skipped with a warning log.

        :returns: List of Agent objects for agents who are members

        Example::

            group = Groups[1234]
            for agent in group.member_objects:
                print(agent.id)  # Works immediately
                print(agent.full_name)  # Triggers API call, then works
        """
        from freshops.exceptions import EntityNotFoundError
        from freshops.models.agent import Agents

        agents_list: list[Any] = []
        for agent_id in self.members:
            try:
                # Get Agent from registry - handles caching and lazy loading
                # Type checker doesn't understand __class_getitem__ returns Agent
                agent = Agents[agent_id]  # type: ignore[return-value]
                agents_list.append(agent)
            except EntityNotFoundError:
                logger.warning(
                    f"Group {self.id} references Agent {agent_id} which does not exist, skipping"
                )
                continue
        return agents_list

    @property
    def leader_objects(self) -> list[Any]:
        """
        Get the group's leader agents (lazy loading via registry).

        Returns a list of Agent objects from the Agents registry.
        Accessing agent.id works immediately. Accessing other
        fields triggers an API call to load the full data for that agent.

        Missing or deleted agents are skipped with a warning log.

        :returns: List of Agent objects for agents who are leaders

        Example::

            group = Groups[1234]
            for agent in group.leader_objects:
                print(agent.full_name)
        """
        from freshops.exceptions import EntityNotFoundError
        from freshops.models.agent import Agents

        agents_list: list[Any] = []
        for agent_id in self.leaders:
            try:
                # Get Agent from registry - handles caching and lazy loading
                # Type checker doesn't understand __class_getitem__ returns Agent
                agent = Agents[agent_id]  # type: ignore[return-value]
                agents_list.append(agent)
            except EntityNotFoundError:
                logger.warning(
                    f"Group {self.id} references Agent {agent_id} which does not exist, skipping"
                )
                continue
        return agents_list

    @property
    def observer_objects(self) -> list[Any]:
        """
        Get the group's observer agents (lazy loading via registry).

        Returns a list of Agent objects from the Agents registry.
        Accessing agent.id works immediately. Accessing other
        fields triggers an API call to load the full data for that agent.

        Missing or deleted agents are skipped with a warning log.

        :returns: List of Agent objects for agents who are observers

        Example::

            group = Groups[1234]
            for agent in group.observer_objects:
                print(agent.full_name)
        """
        from freshops.exceptions import EntityNotFoundError
        from freshops.models.agent import Agents

        agents_list: list[Any] = []
        for agent_id in self.observers:
            try:
                # Get Agent from registry - handles caching and lazy loading
                # Type checker doesn't understand __class_getitem__ returns Agent
                agent = Agents[agent_id]  # type: ignore[return-value]
                agents_list.append(agent)
            except EntityNotFoundError:
                logger.warning(
                    f"Group {self.id} references Agent {agent_id} which does not exist, skipping"
                )
                continue
        return agents_list

    def has_member(self, agent_id: int) -> bool:
        """
        Check if an agent is a member of this group.

        :param agent_id: Agent ID to check
        :returns: True if agent is a member
        """
        return agent_id in self.members

    def has_leader(self, agent_id: int) -> bool:
        """
        Check if an agent is a leader of this group.

        :param agent_id: Agent ID to check
        :returns: True if agent is a leader
        """
        return agent_id in self.leaders

    def has_observer(self, agent_id: int) -> bool:
        """
        Check if an agent is an observer of this group.

        :param agent_id: Agent ID to check
        :returns: True if agent is an observer
        """
        return agent_id in self.observers



class Groups(CachedCollection[Group]):
    """
    A collection of Group objects with registry-based caching.

    Acts as both a collection and a registry for Group instances.
    Use Groups[1234] to get a Group by ID (from cache or API).

    :param groups: List of Group objects
    """

    _entity_name = "groups"

    # TODO: Rich Output - Consider adding custom Rich table output
    # Currently uses base implementation (ID/Name only).
    # Options:
    # 1. Add custom Rich output with additional columns (e.g., description, member_count)
    # 2. Document that base implementation is sufficient for simple entities
    # See HOLISTIC_IMPROVEMENTS.md suggestion #8 for details.

    @classmethod
    def _get_list_method_name_static(cls) -> str:
        """Get the client method name for listing groups."""
        return "list_groups"

    @classmethod
    def _get_entity_class_static(cls) -> type[Group]:
        """Get the Group entity class."""
        return Group


    def _create_filtered(self, items: list[Group]) -> Groups:
        """Create a new Groups collection with filtered items."""
        return Groups(items, client=self._client)

    def find_by_name(self, name: str) -> Group | None:
        """
        Find a group by name (case-insensitive).

        Loads full list into registry if not already loaded, then searches locally.

        :param name: The group name to search for
        :returns: The Group if found, None otherwise
        """
        self._ensure_cache_loaded()
        # Search in registry (all groups)
        name_lower = name.lower()
        for group in self._registry.values():
            if group and group.name.lower() == name_lower:
                return group
        return None

    def restricted(self) -> Groups:
        """
        Get only restricted groups.

        Loads full list into registry if not already loaded, then filters locally.

        :returns: A new Groups collection with only restricted groups
        """
        self._ensure_cache_loaded()
        filtered = [g for g in self._registry.values() if g and g.restricted]
        return self._create_filtered(filtered)

    def with_member(self, agent_id: int) -> Groups:
        """
        Get groups that have a specific agent as a member.

        Loads full list into registry if not already loaded, then filters locally.

        :param agent_id: Agent ID to filter by
        :returns: A new Groups collection with matching groups
        """
        self._ensure_cache_loaded()
        filtered = [
            g for g in self._registry.values()
            if g and g.has_member(agent_id)
        ]
        return self._create_filtered(filtered)

    def with_leader(self, agent_id: int) -> Groups:
        """
        Get groups that have a specific agent as a leader.

        Loads full list into registry if not already loaded, then filters locally.

        :param agent_id: Agent ID to filter by
        :returns: A new Groups collection with matching groups
        """
        self._ensure_cache_loaded()
        filtered = [
            g for g in self._registry.values()
            if g and g.has_leader(agent_id)
        ]
        return self._create_filtered(filtered)

    def with_auto_assign(self) -> Groups:
        """
        Get groups with auto-ticket-assign enabled.

        Loads full list into registry if not already loaded, then filters locally.

        :returns: A new Groups collection with auto-assign groups
        """
        self._ensure_cache_loaded()
        filtered = [
            g for g in self._registry.values()
            if g and g.auto_ticket_assign
        ]
        return self._create_filtered(filtered)

