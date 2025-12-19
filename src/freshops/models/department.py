"""
Department model for FreshService departments.

Provides typed access to department data returned by the FreshService API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from freshops.exceptions import InvalidEntityIdError
from freshops.models.base import CachedCollection, FreshModel
from loguru import logger

if TYPE_CHECKING:
    from freshops.client import FreshServiceClient


@dataclass(eq=False, repr=False)  # Use FreshModel.__eq__ and __repr__ instead
class Department(FreshModel):
    """
    Represents a FreshService department.

    Departments organize agents and can be used for ticket routing.

    :ivar id: Unique department identifier
    :ivar workspace_id: Client ID/workspace ID the department belongs to (mandatory, default 2)
    :ivar name: Department name (mandatory)
    :ivar description: Department description
    :ivar head_user_id: User ID of the department head (Freshservice/Freshservice for Business Teams)
    :ivar prime_user_id: User ID of the primary contact (Freshservice/Freshservice for Business Teams)
    :ivar domains: List of email domains associated with the department (Freshservice/Freshservice for Business Teams)
    :ivar custom_fields: Custom fields associated with the department
    :ivar created_at: When the department was created (read-only)
    :ivar updated_at: When the department was last updated (read-only)
    :ivar raw_data: The original API response dictionary

    Example::

        dept = Department.from_api_response(api_data)
        print(f"{dept.name}")
    """

    _id: int
    _name: str = ""

    @property
    def id(self) -> int:
        """Get the department's unique identifier."""
        return self._id

    @property
    def name(self) -> str:
        """Get the department name."""
        return self._name
    workspace_id: int = 2  # Default value per API spec
    description: str = ""
    head_user_id: int | None = None
    prime_user_id: int | None = None
    domains: list[str] = field(default_factory=list)
    custom_fields: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Department:
        """
        Create a Department instance from an API response dictionary.

        Always creates a new instance from the API data and updates the cache.
        This ensures the cache always contains the authoritative data from the API.

        :param data: Dictionary from the FreshService API
        :returns: A new Department instance (cached in registry)
        """
        # Import here to avoid circular dependency at module load time
        from freshops.models.department import Departments

        dept_id = data.get("id", 0)
        if not dept_id or dept_id <= 0:
            raise InvalidEntityIdError("Department", dept_id)

        # Validate required fields
        name = cls._validate_required_field(data.get("name"), "name")

        # Validate list and dict fields
        domains = cls._validate_list_of_type(data.get("domains", []), str, "domains")
        custom_fields = cls._validate_dict(data.get("custom_fields", {}), "custom_fields")

        # Always create a new instance from API data (authoritative source)
        dept = cls(
            _id=dept_id,
            _name=name,
            workspace_id=data.get("workspace_id", 2),
            description=data.get("description", "") or "",
            head_user_id=data.get("head_user_id"),
            prime_user_id=data.get("prime_user_id"),
            domains=domains,
            custom_fields=custom_fields,
            created_at=cls.parse_datetime(data.get("created_at")),
            updated_at=cls.parse_datetime(data.get("updated_at")),
            raw_data=data,
        )
        # Update cache with authoritative data (replaces existing if present)
        Departments._registry[dept_id] = dept
        logger.debug(f"Department {dept_id} created/updated in cache")
        return dept



class Departments(CachedCollection[Department]):
    """
    A collection of Department objects with registry-based caching.

    Acts as both a collection and a registry for Department instances.
    Use Departments[1234] to get a Department by ID (from cache or API).

    :param departments: List of Department objects
    """

    _entity_name = "departments"

    # TODO: Rich Output - Consider adding custom Rich table output
    # Currently uses base implementation (ID/Name only).
    # Options:
    # 1. Add custom Rich output with additional columns (e.g., description, head_id)
    # 2. Document that base implementation is sufficient for simple entities
    # See HOLISTIC_IMPROVEMENTS.md suggestion #8 for details.

    @classmethod
    def _get_list_method_name_static(cls) -> str:
        """Get the client method name for listing departments."""
        return "list_departments"

    @classmethod
    def _get_entity_class_static(cls) -> type[Department]:
        """Get the Department entity class."""
        return Department


    def _create_filtered(self, items: list[Department]) -> Departments:
        """Create a new Departments collection with filtered items."""
        return Departments(items, client=self._client)

    def find_by_name(self, name: str) -> Department | None:
        """
        Find a department by name (case-insensitive).

        Loads full list into registry if not already loaded, then searches locally.

        :param name: The department name to search for
        :returns: The Department if found, None otherwise
        """
        self._ensure_cache_loaded()
        # Search in registry (all departments)
        name_lower = name.lower()
        for dept in self._registry.values():
            if dept and dept.name.lower() == name_lower:
                return dept
        return None

