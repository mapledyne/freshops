"""
Role model for FreshService roles.

Provides typed access to role data returned by the FreshService API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from freshops.models.base import CachedCollection, FreshModel

from loguru import logger

if TYPE_CHECKING:
    from freshops.client import FreshServiceClient


@dataclass(eq=False, repr=False)  # Use FreshModel.__eq__ and __repr__ instead
class Role(FreshModel):
    """
    Represents a FreshService role.

    Roles define permissions and access levels for agents.

    :ivar id: Unique role identifier
    :ivar name: Role name
    :ivar description: Role description
    :ivar default: True if this is a default role, False otherwise
    :ivar role_type: Role type ID (1 for admin, 2 for agent)
    :ivar created_at: When the role was created
    :ivar updated_at: When the role was last updated
    :ivar raw_data: The original API response dictionary

    Example::

        role = Role.from_api_response(api_data)
        print(f"{role.name}: {role.description}")
        if role.is_default:
            print("This is a default role")
        if role.is_admin_role:
            print("This is an admin role")
    """

    _id: int
    _name: str = ""

    @property
    def id(self) -> int:
        """Get the role's unique identifier."""
        return self._id

    @property
    def name(self) -> str:
        """Get the role name."""
        return self._name

    description: str = ""
    default: bool = False
    role_type: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_default(self) -> bool:
        """
        Check if this is a default role.

        :returns: True if this is a default role, False otherwise
        """
        return self.default

    @property
    def is_admin_role(self) -> bool:
        """
        Check if this is an admin role (role_type == 1).

        :returns: True if role_type is 1 (admin), False otherwise
        """
        return self.role_type == 1

    @property
    def is_agent_role(self) -> bool:
        """
        Check if this is an agent role (role_type == 2).

        :returns: True if role_type is 2 (agent), False otherwise
        """
        return self.role_type == 2

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Role:
        """
        Create a Role instance from an API response dictionary.

        Always creates a new instance from the API data and updates the cache.
        This ensures the cache always contains the authoritative data from the API.

        :param data: Dictionary from the FreshService API
        :returns: A new Role instance (cached in registry)
        """
        # Import here to avoid circular dependency at module load time
        from freshops.models.role import Roles

        role_id = data.get("id", 0)
        if not role_id or role_id <= 0:
            raise InvalidEntityIdError("Role", role_id)

        # Validate required fields (name is required per API, but we allow empty for now)
        # Validate type for boolean and int fields
        default = cls._validate_type(data.get("default", False), bool, "default")

        # Always create a new instance from API data (authoritative source)
        role = cls(
            _id=role_id,
            _name=data.get("name", "") or "",
            description=data.get("description", "") or "",
            default=default,
            role_type=data.get("role_type"),
            created_at=cls.parse_datetime(data.get("created_at")),
            updated_at=cls.parse_datetime(data.get("updated_at")),
            raw_data=data,
        )
        # Update cache with authoritative data (replaces existing if present)
        Roles._registry[role_id] = role
        logger.debug(f"Role {role_id} created/updated in cache")
        return role



class Roles(CachedCollection[Role]):
    """
    A collection of Role objects with registry-based caching.

    Acts as both a collection and a registry for Role instances.
    Use Roles[1234] to get a Role by ID (from cache or API).

    :param roles: List of Role objects
    """

    _entity_name = "roles"

    # TODO: Rich Output - Consider adding custom Rich table output
    # Currently uses base implementation (ID/Name only).
    # Options:
    # 1. Add custom Rich output with additional columns (e.g., role_type, default)
    # 2. Document that base implementation is sufficient for simple entities
    # See HOLISTIC_IMPROVEMENTS.md suggestion #8 for details.

    @classmethod
    def _get_list_method_name_static(cls) -> str:
        """Get the client method name for listing roles."""
        return "list_roles"

    @classmethod
    def _get_entity_class_static(cls) -> type[Role]:
        """Get the Role entity class."""
        return Role


    def _create_filtered(self, items: list[Role]) -> Roles:
        """Create a new Roles collection with filtered items."""
        return Roles(items, client=self._client)

    def find_by_name(self, name: str) -> Role | None:
        """
        Find a role by name (case-insensitive).

        Loads full list into registry if not already loaded, then searches locally.

        :param name: The role name to search for
        :returns: The Role if found, None otherwise
        """
        self._ensure_cache_loaded()
        # Search in registry (all roles)
        name_lower = name.lower()
        for role in self._registry.values():
            if role and role.name.lower() == name_lower:
                return role
        return None

