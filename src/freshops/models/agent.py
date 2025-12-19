"""
Agent model for FreshService agents.

Provides typed access to agent data returned by the FreshService API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from freshops.exceptions import InvalidEntityIdError
from freshops.models.base import CachedCollection, FreshModel
from freshops.models.location import Locations

if TYPE_CHECKING:
    from freshops.client import FreshServiceClient
    from freshops.models.department import Department
    from freshops.models.group import Group
    from freshops.models.location import Location
    from freshops.models.role import Role
    from rich.panel import Panel
    from rich.table import Table
else:
    Panel = Any
    Table = Any

from loguru import logger


@dataclass
class AgentRole:
    """
    Represents a role assignment for an agent.

    :ivar role_id: Unique ID of the role assigned
    :ivar assignment_scope: Scope of permissions. Values:
        - 'entire_helpdesk': All plans
        - 'member_groups': All plans (Pro/Enterprise includes observer groups)
        - 'specified_groups': Pro and Enterprise only
        - 'assigned_items': All plans
    :ivar groups: Group IDs where role applies (only for 'specified_groups' scope)
    """

    role_id: int
    assignment_scope: str
    groups: list[int] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> AgentRole:
        """Create an AgentRole from API response data."""
        return cls(
            role_id=data.get("role_id", 0),
            assignment_scope=data.get("assignment_scope", ""),
            groups=data.get("groups", []) or [],
        )


@dataclass
class WorkspaceInfo:
    """
    Workspace information for an agent.

    :ivar workspace_id: The workspace ID
    :ivar scoreboard_level_id: Agent's level in the Arcade (1-6)
    :ivar points: Scoreboard points (null for MSP)
    """

    workspace_id: int
    scoreboard_level_id: int | None = None
    points: int | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> WorkspaceInfo:
        """Create WorkspaceInfo from API response data."""
        return cls(
            workspace_id=data.get("workspace_id", 0),
            scoreboard_level_id=data.get("scoreboard_level_id"),
            points=data.get("points"),
        )


@dataclass(eq=False, repr=False)  # Use FreshModel.__eq__ and __repr__ instead
class Agent(FreshModel):
    """
    Represents a FreshService agent (support staff member).

    Agents can be "full-time" or "occasional". Full-time agents are core
    support team members. Occasional agents log in infrequently.

    :ivar id: Unique agent identifier
    :ivar email: Email address (mandatory)
    :ivar first_name: First name (mandatory)
    :ivar last_name: Last name
    :ivar active: True if agent is active, False if deactivated
    :ivar occasional: True if occasional agent, False if full-time
    :ivar job_title: Job title
    :ivar work_phone_number: Work phone number
    :ivar mobile_phone_number: Mobile phone number
    :ivar department_ids: IDs of associated departments
    :ivar can_see_all_tickets_from_associated_departments: Can view dept tickets
    :ivar reporting_manager_id: User ID of reporting manager
    :ivar address: Address
    :ivar time_zone: Time zone (e.g., 'America/Los_Angeles')
    :ivar time_format: '12h' or '24h'
    :ivar language: Language code (default 'en')
    :ivar location: Location object (lazy loaded from registry)
    :ivar background_information: Background info text
    :ivar scoreboard_level_id: Arcade level (1=Beginner to 6=Guru)
    :ivar member_of: Group IDs the agent is a member of
    :ivar observer_of: Group IDs the agent is an observer of
    :ivar member_of_pending_approval: Groups pending member approval (read-only)
    :ivar observer_of_pending_approval: Groups pending observer approval (read-only)
    :ivar roles: List of role assignments
    :ivar last_login_at: Last successful login timestamp
    :ivar last_active_at: Recent activity timestamp
    :ivar custom_fields: Custom field key-value pairs
    :ivar has_logged_in: True if agent has ever logged in
    :ivar workspace_ids: Workspace IDs the agent belongs to
    :ivar api_key_enabled: True if API key is enabled
    :ivar workspace_info: Workspace details with scoreboard info
    :ivar created_at: Creation timestamp
    :ivar updated_at: Last update timestamp
    :ivar raw_data: Original API response dictionary

    Example::

        agent = Agent.from_api_response(api_data)
        print(f"{agent.full_name} - {agent.email}")
        if agent.is_active:
            print("Agent is active")
        if agent.is_occasional:
            print("Occasional agent")
    """

    # Required fields
    _id: int
    email: str
    first_name: str

    @property
    def id(self) -> int:
        """Get the agent's unique identifier."""
        return self._id

    # Basic info
    last_name: str = ""
    active: bool = True
    occasional: bool = False
    job_title: str = ""

    # Contact info
    work_phone_number: str = ""
    mobile_phone_number: str = ""
    address: str = ""

    # Organization
    department_ids: list[int] = field(default_factory=list)
    can_see_all_tickets_from_associated_departments: bool = False
    reporting_manager_id: int | None = None
    # Location stored as ID in raw_data, accessed via location property

    # Preferences
    time_zone: str = ""
    time_format: str = ""  # '12h' or '24h'
    language: str = "en"
    background_information: str = ""

    # Gamification
    scoreboard_level_id: int | None = None  # 1-6, None for MSP

    # Group membership
    member_of: list[int] = field(default_factory=list)
    observer_of: list[int] = field(default_factory=list)
    member_of_pending_approval: list[int] = field(default_factory=list)
    observer_of_pending_approval: list[int] = field(default_factory=list)

    # Roles
    roles: list[AgentRole] = field(default_factory=list)

    # Activity tracking
    last_login_at: datetime | None = None
    last_active_at: datetime | None = None
    has_logged_in: bool = False

    # Workspace
    workspace_ids: list[int] = field(default_factory=list)
    workspace_info: list[WorkspaceInfo] = field(default_factory=list)

    # API access
    api_key_enabled: bool = False

    # Custom fields
    custom_fields: dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Raw data for accessing unlisted fields
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    # Client reference for lazy loading (set by collection)
    _client: FreshServiceClient | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Agent:
        """
        Create an Agent instance from an API response dictionary.

        Always creates a new instance from the API data and updates the cache.
        This ensures the cache always contains the authoritative data from the API.

        :param data: Dictionary from the FreshService API
        :returns: A new Agent instance (cached in registry)

        Example::

            response = client._get("/agents/123")
            agent = Agent.from_api_response(response["agent"])
        """
        agent_id = data.get("id", 0)
        if not agent_id or agent_id <= 0:
            raise InvalidEntityIdError("Agent", agent_id)

        # Validate required fields
        email = cls._validate_required_field(data.get("email"), "email")
        first_name = cls._validate_required_field(data.get("first_name"), "first_name")

        # Validate and parse roles
        roles_data = cls._validate_list_of_type(
            data.get("roles", []), dict, "roles"
        )
        roles = [AgentRole.from_api_response(r) for r in roles_data]

        # Validate and parse workspace info
        ws_info_data = cls._validate_list_of_type(
            data.get("workspace_info", []), dict, "workspace_info"
        )
        workspace_info = [WorkspaceInfo.from_api_response(w) for w in ws_info_data]

        # Validate type for list fields
        department_ids = cls._validate_list_of_type(
            data.get("department_ids", []), int, "department_ids"
        )
        member_of = cls._validate_list_of_type(
            data.get("member_of", []), int, "member_of"
        )
        observer_of = cls._validate_list_of_type(
            data.get("observer_of", []), int, "observer_of"
        )
        member_of_pending_approval = cls._validate_list_of_type(
            data.get("member_of_pending_approval", []), int, "member_of_pending_approval"
        )
        observer_of_pending_approval = cls._validate_list_of_type(
            data.get("observer_of_pending_approval", []), int, "observer_of_pending_approval"
        )
        workspace_ids = cls._validate_list_of_type(
            data.get("workspace_ids", []), int, "workspace_ids"
        )

        # Validate dict fields
        custom_fields = cls._validate_dict(data.get("custom_fields", {}), "custom_fields")

        agent = cls(
            # Required
            _id=agent_id,
            email=email,
            first_name=first_name,
            # Basic info
            last_name=data.get("last_name", "") or "",
            active=cls._validate_type(data.get("active", True), bool, "active"),
            occasional=cls._validate_type(data.get("occasional", False), bool, "occasional"),
            job_title=data.get("job_title", "") or "",
            # Contact
            work_phone_number=str(data.get("work_phone_number", "") or ""),
            mobile_phone_number=str(data.get("mobile_phone_number", "") or ""),
            address=data.get("address", "") or "",
            # Organization
            department_ids=department_ids,
            can_see_all_tickets_from_associated_departments=cls._validate_type(
                data.get("can_see_all_tickets_from_associated_departments", False),
                bool,
                "can_see_all_tickets_from_associated_departments",
            ),
            reporting_manager_id=data.get("reporting_manager_id"),
            # Location handled separately via registry
            # Preferences
            time_zone=data.get("time_zone", "") or "",
            time_format=data.get("time_format", "") or "",
            language=data.get("language", "en") or "en",
            background_information=data.get("background_information", "") or "",
            # Gamification
            scoreboard_level_id=data.get("scoreboard_level_id"),
            # Groups
            member_of=member_of,
            observer_of=observer_of,
            member_of_pending_approval=member_of_pending_approval,
            observer_of_pending_approval=observer_of_pending_approval,
            # Roles
            roles=roles,
            # Activity
            last_login_at=cls.parse_datetime(data.get("last_login_at")),
            last_active_at=cls.parse_datetime(data.get("last_active_at")),
            has_logged_in=cls._validate_type(data.get("has_logged_in", False), bool, "has_logged_in"),
            # Workspace
            workspace_ids=workspace_ids,
            workspace_info=workspace_info,
            # API
            api_key_enabled=cls._validate_type(data.get("api_key_enabled", False), bool, "api_key_enabled"),
            # Custom fields
            custom_fields=custom_fields,
            # Timestamps
            created_at=cls.parse_datetime(data.get("created_at")),
            updated_at=cls.parse_datetime(data.get("updated_at")),
            # Raw
            raw_data=data,
        )
        # Store in registry
        # Update cache with authoritative data (replaces existing if present)
        Agents._registry[agent_id] = agent
        logger.debug(f"Agent {agent_id} ({agent.full_name}) created/updated in cache")
        return agent

    # -------------------------------------------------------------------------
    # Computed properties
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Get the agent's full name for display."""
        return self.full_name

    @property
    def full_name(self) -> str:
        """
        Get the agent's full name.

        :returns: Combined first and last name
        """
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_active(self) -> bool:
        """
        Check if the agent is active.

        :returns: True if agent is active
        """
        return self.active

    @property
    def is_occasional(self) -> bool:
        """
        Check if the agent is an occasional (part-time) agent.

        :returns: True if occasional, False if full-time
        """
        return self.occasional

    @property
    def is_full_time(self) -> bool:
        """
        Check if the agent is a full-time agent.

        :returns: True if full-time, False if occasional
        """
        return not self.occasional

    @property
    def scoreboard_level(self) -> str:
        """
        Get the agent's scoreboard level name.

        :returns: Level name or 'Unknown'
        """
        levels = {
            1: "Beginner",
            2: "Intermediate",
            3: "Professional",
            4: "Expert",
            5: "Master",
            6: "Guru",
        }
        return levels.get(self.scoreboard_level_id or 0, "Unknown")

    @property
    def role_ids(self) -> list[int]:
        """
        Get list of role IDs assigned to this agent.

        :returns: List of role IDs
        """
        return [r.role_id for r in self.roles]

    @property
    def group_ids(self) -> list[int]:
        """
        Get all group IDs the agent is associated with (member + observer).

        :returns: Combined list of group IDs
        """
        return list(set(self.member_of + self.observer_of))

    def has_role(self, role_id: int) -> bool:
        """
        Check if agent has a specific role.

        :param role_id: Role ID to check
        :returns: True if agent has the role
        """
        return role_id in self.role_ids

    def is_member_of(self, group_id: int) -> bool:
        """
        Check if agent is a member of a specific group.

        :param group_id: Group ID to check
        :returns: True if agent is a member
        """
        return group_id in self.member_of

    def is_observer_of(self, group_id: int) -> bool:
        """
        Check if agent is an observer of a specific group.

        :param group_id: Group ID to check
        :returns: True if agent is an observer
        """
        return group_id in self.observer_of

    def get_custom_field(self, field_name: str, default: Any = None) -> Any:
        """
        Get a custom field value.

        :param field_name: Name of the custom field
        :param default: Default value if field not found
        :returns: Field value or default
        """
        return self.custom_fields.get(field_name, default)

    @property
    def location(self) -> Location | None:
        """
        Get the agent's location (lazy loading via registry).

        Returns a Location object from the Locations registry.
        Accessing location.id works immediately. Accessing other
        fields (like location.name) triggers an API call to load
        the full data.

        Missing or deleted locations return None with a warning log.

        :returns: Location object if location_id exists and is valid, None otherwise

        Example::

            agent = agents[0]
            if agent.location:
                print(agent.location.id)  # Works immediately
                print(agent.location.name)  # Triggers API call, then works
                print(agent.location.city)  # Uses already-loaded data
        """
        from freshops.exceptions import EntityNotFoundError

        location_id = self.raw_data.get("location_id")
        if location_id is None:
            return None

        try:
            # Get Location from registry - handles caching and lazy loading
            # Type checker doesn't understand __class_getitem__ returns Location
            return Locations[location_id]  # type: ignore[return-value]
        except EntityNotFoundError:
            logger.warning(
                f"Agent {self.id} references Location {location_id} which does not exist"
            )
            return None

    @property
    def groups(self) -> list[Group]:
        """
        Get the agent's groups (lazy loading via registry).

        Returns a list of Group objects from the Groups registry.
        Accessing group.id works immediately. Accessing other
        fields (like group.name) triggers an API call to load
        the full data for that group.

        Missing or deleted groups are skipped with a warning log.

        :returns: List of Group objects for groups the agent is a member of

        Example::

            agent = agents[0]
            for group in agent.groups:
                print(group.id)  # Works immediately
                print(group.name)  # Triggers API call, then works
        """
        from freshops.exceptions import EntityNotFoundError
        from freshops.models.group import Groups

        groups_list: list[Group] = []
        for group_id in self.member_of:
            try:
                # Get Group from registry - handles caching and lazy loading
                # Type checker doesn't understand __class_getitem__ returns Group
                group: Group = Groups[group_id]  # type: ignore[return-value, assignment]
                groups_list.append(group)
            except EntityNotFoundError:
                logger.warning(
                    f"Agent {self.id} references Group {group_id} which does not exist, skipping"
                )
                continue
        return groups_list

    @property
    def role_objects(self) -> list[Role]:
        """
        Get the agent's roles (lazy loading via registry).

        Returns a list of Role objects from the Roles registry.
        Accessing role.id works immediately. Accessing other
        fields (like role.name) triggers an API call to load
        the full data for that role.

        Note: This property is named `role_objects` to avoid conflict
        with the `roles` field which contains AgentRole objects.

        Missing or deleted roles are skipped with a warning log.

        :returns: List of Role objects for roles assigned to the agent

        Example::

            agent = agents[0]
            for role in agent.role_objects:
                print(role.id)  # Works immediately
                print(role.name)  # Triggers API call, then works
        """
        from freshops.exceptions import EntityNotFoundError
        from freshops.models.role import Roles

        roles_list: list[Role] = []
        for role_id in self.role_ids:
            try:
                # Get Role from registry - handles caching and lazy loading
                # Type checker doesn't understand __class_getitem__ returns Role
                role: Role = Roles[role_id]  # type: ignore[return-value, assignment]
                roles_list.append(role)
            except EntityNotFoundError:
                logger.warning(
                    f"Agent {self.id} references Role {role_id} which does not exist, skipping"
                )
                continue
        return roles_list

    @property
    def departments(self) -> list["Department"]:
        """
        Get the agent's departments (lazy loading via registry).

        Returns a list of Department objects from the Departments registry.
        Accessing department.id works immediately. Accessing other
        fields (like department.name) triggers an API call to load
        the full data for that department.

        Missing or deleted departments are skipped with a warning log.

        :returns: List of Department objects for departments the agent belongs to

        Example::

            agent = agents[0]
            for dept in agent.departments:
                print(dept.id)  # Works immediately
                print(dept.name)  # Triggers API call, then works
        """
        from freshops.exceptions import EntityNotFoundError
        from freshops.models.department import Departments

        departments_list: list["Department"] = []
        for dept_id in self.department_ids:
            try:
                # Get Department from registry - handles caching and lazy loading
                # Type checker doesn't understand __class_getitem__ returns Department
                dept: "Department" = Departments[dept_id]  # type: ignore[return-value, assignment]
                departments_list.append(dept)
            except EntityNotFoundError:
                logger.warning(
                    f"Agent {self.id} references Department {dept_id} which does not exist, skipping"
                )
                continue
        return departments_list

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        status = "active" if self.active else "inactive"
        agent_type = "occasional" if self.occasional else "full-time"
        return (
            f"Agent({self.id}: {self.full_name} <{self.email}> "
            f"[{status}, {agent_type}])"
        )

    def to_detail(self) -> str:
        """
        Return a detailed multi-line string representation.

        :returns: Multi-line detailed view of the agent
        """
        status = "Active" if self.active else "Inactive"
        agent_type = "Occasional" if self.occasional else "Full-time"

        lines = [
            f"Agent: {self.full_name}",
            f"{'=' * 40}",
            f"ID:         {self.id}",
            f"Email:      {self.email}",
            f"Status:     {status}",
            f"Type:       {agent_type}",
        ]

        if self.job_title:
            lines.append(f"Job Title:  {self.job_title}")

        if self.work_phone_number:
            lines.append(f"Work Phone: {self.work_phone_number}")

        if self.mobile_phone_number:
            lines.append(f"Mobile:     {self.mobile_phone_number}")

        if self.address:
            lines.append(f"Address:    {self.address}")

        if self.department_ids:
            lines.append(f"Depts:      {', '.join(map(str, self.department_ids))}")

        if self.groups:
            group_names = [g.name or str(g.id) for g in self.groups]
            lines.append(f"Groups:     {', '.join(group_names)}")

        if self.role_objects:
            role_names = [r.name or str(r.id) for r in self.role_objects]
            lines.append(f"Roles:      {', '.join(role_names)}")

        if self.location:
            lines.append(f"Location:   {self.location.name or self.location.id}")

        if self.time_zone:
            lines.append(f"Timezone:   {self.time_zone}")

        if self.language and self.language != "en":
            lines.append(f"Language:   {self.language}")

        if self.scoreboard_level_id:
            lines.append(f"Level:      {self.scoreboard_level}")

        if self.last_login_at:
            last_login_display = self.format_datetime_display(self.last_login_at)
            lines.append(f"Last Login: {last_login_display}")

        if self.created_at:
            created_display = self.format_datetime_display(self.created_at, relative=False)
            lines.append(f"Created:    {created_display}")

        return "\n".join(lines)

    #region Rich Protocol

    def _get_rich_sections(self) -> list[Any]:
        """
        Get Rich renderable sections for agent detail view.

        :returns: List of Rich renderables (Panels, Groups, Text, etc.)
        """
        try:
            from rich.panel import Panel
        except ImportError:
            return []

        sections = []

        # Basic Info Section
        basic_lines = [
            f"ID:    {self.id}",
            f"Email: 📧 {self.email}",
        ]

        # Status badges with icons
        if self.active:
            status_badge = "[green]✅ Active[/green]"
        else:
            status_badge = "[red]❌ Inactive[/red]"

        agent_type = "Occasional" if self.occasional else "Full-time"
        type_badge = f"[cyan]{agent_type}[/cyan]"

        basic_lines.append(f"Status: {status_badge}")
        basic_lines.append(f"Type:   {type_badge}")

        if self.job_title:
            basic_lines.append(f"Title:  {self.job_title}")

        sections.append(
            Panel(
                "\n".join(basic_lines),
                title="[bold]Basic Info[/bold]",
                border_style="blue",
            )
        )

        # Contact Info Section
        contact_lines = []
        if self.work_phone_number:
            contact_lines.append(f"Work:   {self.work_phone_number}")
        if self.mobile_phone_number:
            contact_lines.append(f"Mobile: {self.mobile_phone_number}")
        if self.address:
            contact_lines.append(f"Address: {self.address}")

        if contact_lines:
            sections.append(
                Panel(
                    "\n".join(contact_lines),
                    title="[bold]Contact[/bold]",
                    border_style="cyan",
                )
            )

        # Organization Section
        org_lines = []
        # Always show these fields, use em-dash (—) if missing
        if self.departments:
            dept_names = [d.name or str(d.id) for d in self.departments]
            org_lines.append(f"Departments: {', '.join(dept_names)}")
        else:
            org_lines.append("Departments: —")

        if self.groups:
            group_names = [g.name or str(g.id) for g in self.groups]
            org_lines.append(f"Groups:      {', '.join(group_names)}")
        else:
            org_lines.append("Groups:      —")

        if self.role_objects:
            role_names = [r.name or str(r.id) for r in self.role_objects]
            org_lines.append(f"Roles:       {', '.join(role_names)}")
        else:
            org_lines.append("Roles:       —")

        if self.location:
            loc_name = self.location.name or str(self.location.id)
            org_lines.append(f"Location:    {loc_name}")
        else:
            org_lines.append("Location:    —")

        if org_lines:
            sections.append(
                Panel(
                    "\n".join(org_lines),
                    title="[bold]Organization[/bold]",
                    border_style="magenta",
                )
            )

        # Preferences Section
        pref_lines = []
        if self.time_zone:
            pref_lines.append(f"Timezone: {self.time_zone}")
        if self.language and self.language != "en":
            pref_lines.append(f"Language: {self.language}")

        if pref_lines:
            sections.append(
                Panel(
                    "\n".join(pref_lines),
                    title="[bold]Preferences[/bold]",
                    border_style="yellow",
                )
            )

        # Activity Section
        activity_lines = []
        if self.scoreboard_level_id:
            activity_lines.append(f"Level:      {self.scoreboard_level}")
        if self.last_login_at:
            last_login_display = self.format_datetime_display(self.last_login_at)
            activity_lines.append(f"Last Login: {last_login_display}")
        if self.created_at:
            created_display = self.format_datetime_display(self.created_at, relative=False)
            activity_lines.append(f"Created:    {created_display}")

        if activity_lines:
            sections.append(
                Panel(
                    "\n".join(activity_lines),
                    title="[bold]Activity[/bold]",
                    border_style="green",
                )
            )

        return sections

    def __rich__(self) -> Any:  # Returns Panel when Rich available, str otherwise
        """
        Rich protocol - returns a Rich Panel object for agent detail view.

        Provides agent-specific detail panel with organized sections.

        :returns: Rich Panel object (or str fallback if Rich not available)
        """
        try:
            from rich.console import Group
            from rich.panel import Panel
            from rich.text import Text
        except ImportError:
            # Fallback to plain text if Rich not installed
            return str(self)

        # Get sections from hook method
        sections = self._get_rich_sections()

        if sections:
            # Combine sections into a Group
            content = Group(*sections)
        else:
            # Default: basic info
            content = Text(f"{self.name} ({self.id})")

        # Create main panel with agent name as title
        return Panel(
            content,
            title=f"[bold magenta]Agent: {self.full_name}[/bold magenta]",
            border_style="bright_blue",
            padding=(1, 2),
        )

    #endregion


class Agents(CachedCollection[Agent]):
    """
    A collection of Agent objects with agent-specific helper methods.

    Inherits common functionality from CachedCollection and adds
    agent-specific filtering and lookup methods.

    :param agents: List of Agent objects
    :param total: Total agents across all pages
    :param page: Current page number
    :param per_page: Agents per page
    :param has_more: Whether more pages exist
    :param client: Client reference for pagination

    Example::

        agents = Agents.from_api_response(api_data)

        # Iterate over all agents
        for agent in agents:
            print(agent.full_name)

        # Filter active agents
        active = agents.active()

        # Find by email
        agent = agents.find_by_email("user@example.com")

        # Chain filters
        it_active = agents.active().in_department(5)

        # Filter by type
        full_time = agents.full_time()
        occasional = agents.occasional()
    """

    _entity_name = "agents"


    @classmethod
    def _get_list_method_name_static(cls) -> str:
        """Get the client method name for listing agents."""
        return "list_agents"

    @classmethod
    def _get_entity_class_static(cls) -> type[Agent]:
        """Get the Agent entity class."""
        return Agent


    @classmethod
    def _get_single_fetch_method_name_static(cls) -> str | None:
        """
        Return "get_agent" to use single-fetch pattern for Agents.

        Agents uses single-fetch because get_agent() is more efficient
        than loading all agents when looking up a single agent.
        """
        return "get_agent"

    @classmethod
    def from_api_response(
        cls,
        data: list[dict[str, Any]],
        *,
        total: int | None = None,
        page: int = 1,
        per_page: int = 100,
        has_more: bool = False,
        client: FreshServiceClient | None = None,
    ) -> Agents:
        """
        Create an Agents collection from an API response.

        If full list hasn't been loaded yet, loads all agents and
        caches them. If already loaded, uses cached data (no API call).

        :param data: List of agent dictionaries from the API
        :param total: Total count from API response
        :param page: Current page number
        :param per_page: Items per page
        :param has_more: Whether more pages exist
        :param client: Client reference for pagination
        :returns: A new Agents collection
        """
        # Call parent to handle caching
        return super().from_api_response(
            data,
            total=total,
            page=page,
            per_page=per_page,
            has_more=has_more,
            client=client,
        )

    def _post_init_from_api_response(self) -> None:
        """Inject client into all agents for lazy loading (e.g., location)."""
        if self._client:
            for agent in self._items:
                agent._client = self._client

    def _create_filtered(self, items: list[Agent]) -> Agents:
        """Create a new Agents collection with filtered items."""
        return Agents(items, client=self._client)


    # -------------------------------------------------------------------------
    # Output formatting
    # -------------------------------------------------------------------------

    def to_table(self) -> str:
        """
        Render the agents as a formatted text table.

        :returns: Formatted table string
        """
        # Column widths
        id_w, name_w, email_w, status_w = 10, 30, 35, 8

        # Header
        lines = [
            f"{'ID':<{id_w}} {'Name':<{name_w}} {'Email':<{email_w}} "
            f"{'Active':<{status_w}}",
            "-" * (id_w + name_w + email_w + status_w + 3),
        ]

        # Rows
        for agent in self._items:
            active = "Yes" if agent.active else "No"
            # Truncate long values
            name = agent.full_name[:name_w]
            email = agent.email[:email_w]
            lines.append(
                f"{agent.id:<{id_w}} {name:<{name_w}} {email:<{email_w}} "
                f"{active:<{status_w}}"
            )

        # Footer
        lines.append("")
        if self.total is not None and self.total != len(self._items):
            lines.append(f"Showing {len(self._items)} of {self.total} agents")
        else:
            lines.append(f"Total: {len(self._items)} agents")

        return "\n".join(lines)

    #region Rich Protocol

    def _get_rich_table_title(self) -> str:
        """
        Get the title for the Rich agents table.

        :returns: Table title string
        """
        if self.total is not None and self.total != len(self._items):
            return f"Agents ({len(self._items)} of {self.total})"
        return f"Agents ({len(self._items)})"

    def _get_rich_columns(self) -> list[Any]:
        """
        Get Rich table columns for agents.

        :returns: List of Rich Column objects
        """
        try:
            from rich.table import Column
        except ImportError:
            return []

        return [
            Column("ID", style="cyan", no_wrap=True, justify="right"),
            Column("Name", style="magenta", overflow="fold"),
            Column("Email", style="blue", overflow="fold"),
            Column("Status", style="green", no_wrap=True),
        ]

    def __rich__(self) -> Any:  # Returns Table when Rich available, str otherwise
        """
        Rich protocol - returns a Rich Table object for agents.

        Provides agent-specific table with ID, Name, Email, and Status columns.
        Applies styling: active agents are normal, inactive agents are dimmed.

        :returns: Rich Table object (or str fallback if Rich not available)
        """
        try:
            from rich.table import Table
            from rich.text import Text
        except ImportError:
            # Fallback to plain text if Rich not installed
            return str(self)

        # Create table with title
        table = Table(
            title=self._get_rich_table_title(),
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
        )

        # Add columns
        columns = self._get_rich_columns()
        if columns:
            for col in columns:
                col_kwargs: dict[str, Any] = {
                    "style": getattr(col, "style", None),
                    "no_wrap": getattr(col, "no_wrap", False),
                }
                # Only add overflow/justify if they're not None
                overflow = getattr(col, "overflow", None)
                if overflow is not None:
                    col_kwargs["overflow"] = overflow
                justify = getattr(col, "justify", None)
                if justify is not None:
                    col_kwargs["justify"] = justify

                table.add_column(
                    col.header if hasattr(col, "header") else str(col),
                    **col_kwargs,
                )
        else:
            # Fallback if columns not available
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="magenta")
            table.add_column("Email", style="blue")
            table.add_column("Status", style="green")

        # Add rows with agent data
        for agent in self._items:
            # Status with icon: ✅ Active or ❌ Inactive
            if agent.active:
                status = Text("✅ Active", style="green")
            else:
                status = Text("❌ Inactive", style="red dim")

            # Row style: dim inactive agents
            row_style = None if agent.active else "dim"

            # Add row
            table.add_row(
                str(agent.id),
                agent.full_name,
                f"📧 {agent.email}",
                status,
                style=row_style,
            )

        return table

    #endregion

    # -------------------------------------------------------------------------
    # Agent-specific lookups
    # -------------------------------------------------------------------------

    def find_by_email(self, email: str) -> Agent | None:
        """
        Find an agent by their email address (case-insensitive).

        Loads full list into registry if not already loaded, then searches locally.

        :param email: The email address to search for
        :returns: The Agent if found, None otherwise
        """
        self._ensure_cache_loaded()
        email_lower = email.lower()
        # Search in registry (all agents)
        for agent in Agents._registry.values():
            if agent and agent.email.lower() == email_lower:
                return agent
        return None

    # -------------------------------------------------------------------------
    # Status filters
    # -------------------------------------------------------------------------

    def active(self) -> Agents:
        """
        Get only active agents.

        :returns: A new Agents collection with only active agents
        """
        return self._create_filtered([a for a in self._items if a.active])

    def inactive(self) -> Agents:
        """
        Get only inactive agents.

        :returns: A new Agents collection with only inactive agents
        """
        return self._create_filtered([a for a in self._items if not a.active])

    # -------------------------------------------------------------------------
    # Type filters
    # -------------------------------------------------------------------------

    def full_time(self) -> Agents:
        """
        Get only full-time agents.

        :returns: A new Agents collection with only full-time agents
        """
        return self._create_filtered([a for a in self._items if not a.occasional])

    def occasional(self) -> Agents:
        """
        Get only occasional (part-time) agents.

        :returns: A new Agents collection with only occasional agents
        """
        return self._create_filtered([a for a in self._items if a.occasional])

    # -------------------------------------------------------------------------
    # Organization filters
    # -------------------------------------------------------------------------

    def in_department(self, department_id: int) -> Agents:
        """
        Get agents in a specific department.

        :param department_id: The department ID to filter by
        :returns: A new Agents collection with matching agents
        """
        return self._create_filtered(
            [a for a in self._items if department_id in a.department_ids]
        )

    def at_location(self, location_id: int) -> Agents:
        """
        Get agents at a specific location.

        :param location_id: The location ID to filter by
        :returns: A new Agents collection with matching agents
        """
        return self._create_filtered(
            [
                a for a in self._items
                if a.raw_data.get("location_id") == location_id
            ]
        )

    def reporting_to(self, manager_id: int) -> Agents:
        """
        Get agents reporting to a specific manager.

        :param manager_id: The manager's agent ID
        :returns: A new Agents collection with matching agents
        """
        return self._create_filtered(
            [a for a in self._items if a.reporting_manager_id == manager_id]
        )

    # -------------------------------------------------------------------------
    # Group/Role filters
    # -------------------------------------------------------------------------

    def members_of(self, group_id: int) -> Agents:
        """
        Get agents who are members of a specific group.

        :param group_id: The group ID to filter by
        :returns: A new Agents collection with matching agents
        """
        return self._create_filtered(
            [a for a in self._items if group_id in a.member_of]
        )

    def observers_of(self, group_id: int) -> Agents:
        """
        Get agents who are observers of a specific group.

        :param group_id: The group ID to filter by
        :returns: A new Agents collection with matching agents
        """
        return self._create_filtered(
            [a for a in self._items if group_id in a.observer_of]
        )

    def in_group(self, group_id: int) -> Agents:
        """
        Get agents in a specific group (member or observer).

        :param group_id: The group ID to filter by
        :returns: A new Agents collection with matching agents
        """
        return self._create_filtered(
            [a for a in self._items if group_id in a.group_ids]
        )

    def with_role(self, role_id: int) -> Agents:
        """
        Get agents with a specific role.

        :param role_id: The role ID to filter by
        :returns: A new Agents collection with matching agents
        """
        return self._create_filtered([a for a in self._items if a.has_role(role_id)])

    # -------------------------------------------------------------------------
    # Activity filters
    # -------------------------------------------------------------------------

    def logged_in(self) -> Agents:
        """
        Get agents who have logged in at least once.

        :returns: A new Agents collection with agents who have logged in
        """
        return self._create_filtered([a for a in self._items if a.has_logged_in])

    def never_logged_in(self) -> Agents:
        """
        Get agents who have never logged in.

        :returns: A new Agents collection with agents who haven't logged in
        """
        return self._create_filtered([a for a in self._items if not a.has_logged_in])

    def with_api_access(self) -> Agents:
        """
        Get agents with API access enabled.

        :returns: A new Agents collection with API-enabled agents
        """
        return self._create_filtered([a for a in self._items if a.api_key_enabled])
