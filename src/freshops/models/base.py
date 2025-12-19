"""
Base classes for FreshService entities and collections.

Provides common functionality for all FreshService data models,
including date/time parsing and formatting, and generic collection handling.


TODO: Consider a mixin pattern for caching
    If some collections need caching and others don't, consider a
    CachedCollectionMixin instead of inheritance, allowing more flexibility
    in the class hierarchy.

TODO: Add type safety for registry access
    Consider adding type guards or assertions when accessing _registry to
    ensure type safety, especially when items might be lazily loaded.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from loguru import logger

from freshops.client import FreshServiceClient
from freshops.constants import CACHE_MAX_LOAD, DATETIME_RECENT_DAYS_THRESHOLD
from freshops.exceptions import (
    EntityNotFoundError,
    RegistryClientNotInitializedError,
)

# Rich type hints (optional dependency)
if TYPE_CHECKING:
    from rich.console import RenderableType
    from rich.panel import Panel
    from rich.table import Table
else:
    Panel = Any
    RenderableType = Any
    Table = Any

# Type variable for the entity type in collections
T = TypeVar("T", bound="FreshModel")

# Type variable for cached collections
C = TypeVar("C", bound="CachedCollection")


class FreshModel(ABC):
    """
    Base class for FreshService data models.

    Provides shared utility methods for parsing and formatting
    data from/to the FreshService API.

    All FreshService models should inherit from this class to
    gain access to common functionality.

    Subclasses must:
    - Implement the `id` property: Returns the unique identifier (int)
    - Implement the `name` property: Returns a human-readable name (str)
    """

    #region Abstract Properties

    @property
    @abstractmethod
    def id(self) -> int:
        """
        Get the unique identifier for this model.

        :returns: The model's unique ID
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get a human-readable name for this model.

        This should return the primary display name for the entity.
        For example, Agent returns full_name, Location returns name.

        :returns: A human-readable name string
        """
        ...

    #endregion

    #region Date/Time Utilities

    @staticmethod
    def parse_datetime(value: str | None) -> datetime | None:
        """
        Parse an ISO datetime string from the FreshService API.

        FreshService returns datetimes in ISO 8601 format with 'Z' suffix
        for UTC (e.g., '2024-01-15T10:30:00Z').

        :param value: ISO format datetime string or None
        :returns: Timezone-aware datetime object (UTC) or None

        Example::

            created = FreshModel.parse_datetime("2024-01-15T10:30:00Z")
            # datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        """
        if not value:
            return None
        try:
            # FreshService uses ISO format: 2024-01-15T10:30:00Z
            # Replace 'Z' with +00:00 for fromisoformat compatibility
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def format_datetime(dt: datetime | None) -> str | None:
        """
        Format a datetime for FreshService API requests.

        Converts a datetime to the ISO 8601 format expected by FreshService.

        :param dt: datetime object or None
        :returns: ISO format string with 'Z' suffix for UTC, or None

        Example::

            date_str = FreshModel.format_datetime(datetime.now(timezone.utc))
            # "2024-01-15T10:30:00Z"
        """
        if not dt:
            return None
        # Ensure we're working with UTC
        if dt.tzinfo is None:
            # Assume naive datetimes are UTC
            dt = dt.replace(tzinfo=timezone.utc)
        # Convert to UTC and format
        utc_dt = dt.astimezone(timezone.utc)
        # Format as ISO 8601 with Z suffix
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def format_datetime_display(dt: datetime | None, *, relative: bool = True) -> str:
        """
        Format a datetime for human-readable display in local timezone.

        Converts UTC datetime to local timezone and formats in a friendly way.
        For recent dates (within 24 hours), shows relative time like "2 hours ago".
        For older dates, shows formatted date/time like "Dec 18, 2025 at 1:08 PM".

        :param dt: datetime object (assumed UTC) or None
        :param relative: If True, show relative time for recent dates (default: True)
        :returns: Formatted string in local timezone, or "Never" if None

        Example::

            # Recent date (within 24 hours)
            display = FreshModel.format_datetime_display(datetime.now(timezone.utc) - timedelta(hours=2))
            # "2 hours ago"

            # Older date
            display = FreshModel.format_datetime_display(datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc))
            # "Jan 15, 2024 at 10:30 AM" (in local timezone)
        """
        if not dt:
            return "Never"

        # Ensure we have a timezone-aware datetime
        if dt.tzinfo is None:
            # Assume naive datetimes are UTC
            dt = dt.replace(tzinfo=timezone.utc)

        # Convert to local timezone
        local_dt = dt.astimezone()

        # For relative time (recent dates)
        if relative:
            now = datetime.now(local_dt.tzinfo)
            diff = now - local_dt

            # Show relative time for dates within 24 hours
            if diff < timedelta(hours=1):
                minutes = int(diff.total_seconds() / 60)
                if minutes < 1:
                    return "Just now"
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            if diff < timedelta(hours=24):
                hours = int(diff.total_seconds() / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            if diff < timedelta(days=DATETIME_RECENT_DAYS_THRESHOLD):
                days = diff.days
                return f"{days} day{'s' if days != 1 else ''} ago"

        # Format older dates: "Dec 18, 2025 at 1:08 PM"
        # Use 12-hour format with AM/PM
        time_str = local_dt.strftime("%I:%M %p").lstrip("0")  # Remove leading zero from hour
        date_str = local_dt.strftime("%b %d, %Y")
        return f"{date_str} at {time_str}"

    @staticmethod
    def parse_date(value: str | None) -> datetime | None:
        """
        Parse a date-only string from the FreshService API.

        Some FreshService fields return just dates (e.g., '2024-01-15').

        :param value: Date string in YYYY-MM-DD format or None
        :returns: datetime object (at midnight UTC) or None

        Example::

            due_date = FreshModel.parse_date("2024-01-15")
            # datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        """
        if not value:
            return None
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def format_date(dt: datetime | None) -> str | None:
        """
        Format a datetime as a date-only string for API requests.

        :param dt: datetime object or None
        :returns: Date string in YYYY-MM-DD format, or None

        Example::

            date_str = FreshModel.format_date(datetime(2024, 1, 15))
            # "2024-01-15"
        """
        if not dt:
            return None
        return dt.strftime("%Y-%m-%d")

    #endregion

    #region Validation Helpers

    @classmethod
    def _validate_required_field(
        cls, value: Any, field_name: str, allow_empty: bool = False
    ) -> Any:
        """
        Validate that a required field is present and not empty.

        :param value: The field value to validate
        :param field_name: The name of the field (for error messages)
        :param allow_empty: If True, allow empty strings (default: False)
        :returns: The validated value
        :raises MissingRequiredFieldError: If field is missing or empty

        Example::

            email = cls._validate_required_field(data.get("email"), "email")
        """
        from freshops.exceptions import MissingRequiredFieldError

        if value is None:
            raise MissingRequiredFieldError(cls.__name__, field_name)
        if isinstance(value, str) and not allow_empty and not value.strip():
            raise MissingRequiredFieldError(cls.__name__, field_name)
        return value

    @classmethod
    def _validate_type(
        cls, value: Any, expected_type: type | tuple[type, ...], field_name: str
    ) -> Any:
        """
        Validate that a field matches the expected type.

        :param value: The field value to validate
        :param expected_type: The expected type(s) (can be a tuple for multiple types)
        :param field_name: The name of the field (for error messages)
        :returns: The validated value
        :raises TypeError: If field type doesn't match

        Example::

            active = cls._validate_type(data.get("active", True), bool, "active")
        """
        if value is None:
            return None
        if not isinstance(value, expected_type):
            type_names = (
                expected_type.__name__
                if isinstance(expected_type, type)
                else " | ".join(t.__name__ for t in expected_type)
            )
            raise TypeError(
                f"{cls.__name__}.{field_name} must be {type_names}, "
                f"got {type(value).__name__}"
            )
        return value

    @classmethod
    def _validate_list_of_type(
        cls,
        value: Any,
        item_type: type,
        field_name: str,
        allow_none: bool = False,
    ) -> list[Any]:
        """
        Validate that a field is a list and optionally validate item types.

        :param value: The field value to validate
        :param item_type: The expected type for list items
        :param field_name: The name of the field (for error messages)
        :param allow_none: If True, allow None values (default: False)
        :returns: The validated list
        :raises TypeError: If field is not a list or items don't match type

        Example::

            department_ids = cls._validate_list_of_type(
                data.get("department_ids", []), int, "department_ids"
            )
        """
        if value is None:
            if allow_none:
                return []
            raise TypeError(f"{cls.__name__}.{field_name} cannot be None")
        if not isinstance(value, list):
            raise TypeError(
                f"{cls.__name__}.{field_name} must be a list, "
                f"got {type(value).__name__}"
            )
        if item_type and not all(isinstance(item, item_type) for item in value):
            raise TypeError(
                f"{cls.__name__}.{field_name} must contain only {item_type.__name__} items"
            )
        return value

    @classmethod
    def _validate_dict(
        cls, value: Any, field_name: str, allow_none: bool = False
    ) -> dict[str, Any]:
        """
        Validate that a field is a dictionary.

        :param value: The field value to validate
        :param field_name: The name of the field (for error messages)
        :param allow_none: If True, allow None values (default: False)
        :returns: The validated dictionary
        :raises TypeError: If field is not a dict

        Example::

            custom_fields = cls._validate_dict(
                data.get("custom_fields", {}), "custom_fields"
            )
        """
        if value is None:
            if allow_none:
                return {}
            raise TypeError(f"{cls.__name__}.{field_name} cannot be None")
        if not isinstance(value, dict):
            raise TypeError(
                f"{cls.__name__}.{field_name} must be a dict, "
                f"got {type(value).__name__}"
            )
        return value

    #endregion

    #region String Representation

    def __str__(self) -> str:
        """
        Return a human-readable string representation.

        Default format: "name (id)". Subclasses can override for
        entity-specific formatting.

        :returns: Human-readable string

        Example::

            Agent(id=123, name="John Doe") -> "John Doe (123)"
            Location(id=456, name="Seattle") -> "Seattle (456)"
        """
        return f"{self.name} ({self.id})"

    def to_detail(self) -> str:
        """
        Return a detailed multi-line string representation.

        Subclasses should override this to provide entity-specific
        detailed formatting.

        :returns: Multi-line detailed string

        Example override::

            def to_detail(self) -> str:
                return f'''
            Agent: {self.full_name}
            Email: {self.email}
            Status: {'Active' if self.active else 'Inactive'}
            '''
        """
        return str(self)

    def _get_rich_sections(self) -> list["RenderableType"]:
        """
        Get Rich renderable sections for detail view.

        Subclasses should override to define their specific sections.
        Default implementation returns basic info.

        :returns: List of Rich renderables (Panels, Groups, Text, etc.)

        Example::

            def _get_rich_sections(self) -> list[RenderableType]:
                from rich.panel import Panel
                from rich.text import Text
                return [
                    Panel(f"ID: {self.id}\\nName: {self.name}", title="Basic Info"),
                    Panel(f"Email: {self.email}", title="Contact"),
                ]
        """
        # Default: basic info
        try:
            from rich.text import Text
        except ImportError:
            # If Rich not available, return empty (will fallback in __rich__)
            return []

        try:
            from rich.text import Text
            return [
                Text(f"ID: {self.id}"),
                Text(f"Name: {self.name}"),
            ]
        except ImportError:
            return []

    def __rich__(self) -> "Panel":
        """
        Rich protocol - returns a Rich Panel object.

        Provides graceful degradation: if Rich is not installed,
        falls back to plain text representation.

        Subclasses can override to customize panel appearance.

        :returns: Rich Panel object (or Text fallback if Rich not available)

        Example::

            from rich.console import Console
            console = Console()
            console.print(agent)  # Automatically calls __rich__()
        """
        try:
            from rich.panel import Panel
            from rich.text import Text
        except ImportError:
            # Fallback to plain text if Rich not installed
            from rich.text import Text
            return Text(str(self))

        # Get sections from subclass hook
        sections = self._get_rich_sections()

        if sections:
            # Use Rich Group to combine sections
            try:
                from rich.console import Group
                content = Group(*sections)
            except ImportError:
                # Fallback if Group not available
                content = sections[0] if sections else Text(str(self))
        else:
            # Default: basic info
            content = Text(f"{self.name} ({self.id})")

        # Create panel
        panel = Panel(
            content,
            title=f"{self.__class__.__name__}: {self.name}",
            border_style="blue",
        )

        return panel

    def __repr__(self) -> str:
        """
        Return a developer-friendly string representation.

        Shows the class name, ID, and name for debugging.

        :returns: Developer-friendly representation

        Example::

            Agent(id=123, name="John Doe")
            Location(id=456, name="Seattle Office")
        """
        class_name = self.__class__.__name__
        return f"{class_name}(id={self.id}, name={self.name!r})"

    #endregion

    #region Equality, Hashing, and Comparison Operators

    def __bool__(self) -> bool:
        """
        Return True if the model has a valid ID.

        A model is considered "truthy" if it has a valid (positive) ID.
        This allows checking model validity in boolean contexts.

        :returns: True if id > 0, False otherwise

        Example::

            agent = Agent(id=123, ...)
            if agent:  # True, has valid ID
                print("Agent is valid")

            # Useful for optional models
            if agent.location:  # True if location exists and has valid ID
                print(f"Location: {agent.location.name}")
        """
        return self.id > 0

    def __eq__(self, other: object) -> bool:
        """
        Compare two models for equality by ID.

        Two models are equal if they are the same class and have the same ID.

        :param other: Another object to compare
        :returns: True if same class and same ID, False otherwise

        Example::

            agent1 = Agent(id=123, ...)
            agent2 = Agent(id=123, ...)
            agent1 == agent2  # True

            agent1 = Agent(id=123, ...)
            agent2 = Agent(id=456, ...)
            agent1 == agent2  # False
        """
        if not isinstance(other, FreshModel):
            return NotImplemented
        if self.__class__ != other.__class__:
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """
        Return hash based on class and ID.

        Allows models to be used in sets and as dictionary keys.
        Note: This requires that subclasses are either frozen dataclasses
        or explicitly set `__hash__ = FreshModel.__hash__` in their definition.

        :returns: Hash value based on class name and ID

        Example::

            agents = {agent1, agent2, agent3}  # Set of agents
            agent_dict = {agent1: "data"}  # Agent as dict key
        """
        return hash((self.__class__.__name__, self.id))

    def __lt__(self, other: object) -> bool:
        """
        Compare models for less-than ordering.

        Compares by name first, then by ID if names are equal.

        :param other: Another FreshModel to compare
        :returns: True if self < other, False otherwise

        Example::

            agent1 = Agent(id=1, name="Alice")
            agent2 = Agent(id=2, name="Bob")
            agent1 < agent2  # True (alphabetical by name)
        """
        if not isinstance(other, FreshModel):
            return NotImplemented
        if self.__class__ != other.__class__:
            return NotImplemented
        # Compare by name, then by ID if names are equal
        if self.name != other.name:
            return self.name < other.name
        return self.id < other.id

    def __le__(self, other: object) -> bool:
        """
        Compare models for less-than-or-equal ordering.

        :param other: Another FreshModel to compare
        :returns: True if self <= other, False otherwise
        """
        if not isinstance(other, FreshModel):
            return NotImplemented
        if self.__class__ != other.__class__:
            return NotImplemented
        # Compare by name, then by ID if names are equal
        if self.name != other.name:
            return self.name <= other.name
        return self.id <= other.id

    def __gt__(self, other: object) -> bool:
        """
        Compare models for greater-than ordering.

        :param other: Another FreshModel to compare
        :returns: True if self > other, False otherwise
        """
        if not isinstance(other, FreshModel):
            return NotImplemented
        if self.__class__ != other.__class__:
            return NotImplemented
        # Compare by name, then by ID if names are equal
        if self.name != other.name:
            return self.name > other.name
        return self.id > other.id

    def __ge__(self, other: object) -> bool:
        """
        Compare models for greater-than-or-equal ordering.

        :param other: Another FreshModel to compare
        :returns: True if self >= other, False otherwise
        """
        if not isinstance(other, FreshModel):
            return NotImplemented
        if self.__class__ != other.__class__:
            return NotImplemented
        # Compare by name, then by ID if names are equal
        if self.name != other.name:
            return self.name >= other.name
        return self.id >= other.id

    #endregion

class Collection(Generic[T]):
    """
    Generic base class for collections of FreshService entities.

    Provides common iteration, lookup, filtering, and pagination
    support for all entity collections (Agents, Tickets, etc.).

    Subclasses should override :meth:`_create_filtered` to return
    the correct subclass type when filtering.

    :param items: List of entity objects
    :param total: Total count across all pages (if known from API)
    :param page: Current page number (1-indexed)
    :param per_page: Number of items per page
    :param has_more: Whether more pages are available
    :param client: Optional client reference for pagination/refresh

    Example::

        # Subclass for specific entity types
        class Agents(Collection[Agent]):
            def active(self) -> Agents:
                return self._create_filtered([a for a in self if a.active])
    """

    #region Initialization

    # Subclasses should set this to their entity name for repr
    _entity_name: str = "items"

    def __init__(
        self,
        items: list[T] | None = None,
        *,
        total: int | None = None,
        page: int = 1,
        per_page: int = 100,
        has_more: bool = False,
        client: FreshServiceClient | None = None,
    ) -> None:
        """
        Initialize the collection.

        :param items: List of entity objects
        :param total: Total count across all pages (from API)
        :param page: Current page number (1-indexed)
        :param per_page: Items per page
        :param has_more: Whether more pages exist
        :param client: Client reference for future pagination/caching
        """
        self._items: list[T] = items or []
        self.total = total
        self.page = page
        self.per_page = per_page
        self.has_more = has_more
        # Client reference for pagination, refresh, caching (future)
        self._client = client
        # Reserved for future caching - lookup indexes
        self._index_by_id: dict[int, T] | None = None

    #endregion

    #region Sequence Protocol (Dunder Methods)

    def __iter__(self) -> Iterator[T]:
        """Iterate over items in the collection."""
        return iter(self._items)

    def __len__(self) -> int:
        """Return the number of items in this page of the collection."""
        return len(self._items)

    def __getitem__(self, index: int | slice) -> T | Collection[T]:
        """
        Get an item by index or a slice of items.

        Supports both integer indexing and slicing:
        - `collection[0]` - Returns a single item
        - `collection[0:5]` - Returns a new collection with sliced items

        :param index: Integer index or slice object
        :returns: Single item (if int) or new collection (if slice)
        """
        if isinstance(index, slice):
            sliced_items = self._items[index]
            return self._create_filtered(sliced_items)
        return self._items[index]

    def __bool__(self) -> bool:
        """Return True if collection has any items."""
        return len(self._items) > 0

    def __contains__(self, item: T) -> bool:
        """Check if an item is in the collection."""
        return item in self._items

    def __reversed__(self) -> Iterator[T]:
        """
        Return a reverse iterator over the collection.

        :returns: Iterator that yields items in reverse order

        Example::

            for agent in reversed(agents):
                print(agent.name)
        """
        return reversed(self._items)

    def __eq__(self, other: object) -> bool:
        """
        Compare two collections for equality.

        Two collections are equal if they contain the same items
        in the same order (using item equality).

        :param other: Another object to compare
        :returns: True if collections have same items in same order

        Example::

            agents1 = Agents([agent1, agent2])
            agents2 = Agents([agent1, agent2])
            agents1 == agents2  # True

            agents1 = Agents([agent1, agent2])
            agents2 = Agents([agent2, agent1])
            agents1 == agents2  # False (different order)
        """
        if not isinstance(other, Collection):
            return NotImplemented
        if self.__class__ != other.__class__:
            return False
        if len(self) != len(other):
            return False
        return all(a == b for a, b in zip(self._items, other._items, strict=True))

    #endregion

    #region Item Access and Lookups

    def first(self) -> T | None:
        """
        Get the first item in the collection.

        :returns: First item or None if empty
        """
        return self._items[0] if self._items else None

    def last(self) -> T | None:
        """
        Get the last item in the collection.

        :returns: Last item or None if empty
        """
        return self._items[-1] if self._items else None

    def find_by_id(self, entity_id: int) -> T | None:
        """
        Find an item by its ID.

        This method is designed to support future caching - the first
        call will build an index for O(1) subsequent lookups.

        :param entity_id: The ID to search for
        :returns: The item if found, None otherwise
        """
        # Build index on first use (cache-friendly design)
        if self._index_by_id is None:
            self._index_by_id = {}
            for item in self._items:
                if hasattr(item, "id"):
                    self._index_by_id[item.id] = item

        return self._index_by_id.get(entity_id)

    def find(self, predicate: Callable[[T], bool]) -> T | None:
        """
        Find the first item matching a predicate.

        :param predicate: Function that takes an item and returns bool
        :returns: First matching item or None

        Example::

            agent = agents.find(lambda a: a.email == "user@example.com")
        """
        for item in self._items:
            if predicate(item):
                return item
        return None

    #endregion

    #region Filtering and Transformation

    def _create_filtered(self, items: list[T]) -> Collection[T]:
        """
        Create a new collection of the same type with filtered items.

        Subclasses should override this to return their specific type.
        This is a factory method that preserves the collection type
        through filter operations.

        :param items: Filtered list of items
        :returns: New collection instance

        Example override::

            def _create_filtered(self, items: list[Agent]) -> "Agents":
                return Agents(items, client=self._client)
        """
        return self.__class__(items, client=self._client)

    def filter(self, predicate: Callable[[T], bool]) -> Collection[T]:
        """
        Filter items using a predicate function.

        Returns a new collection containing only items where
        the predicate returns True.

        :param predicate: Function that takes an item and returns bool
        :returns: New filtered collection (same type as self)

        Example::

            high_priority = tickets.filter(lambda t: t.priority == 1)
        """
        filtered = [item for item in self._items if predicate(item)]
        return self._create_filtered(filtered)

    def exclude(self, predicate: Callable[[T], bool]) -> Collection[T]:
        """
        Exclude items matching a predicate function.

        Returns a new collection containing only items where
        the predicate returns False (inverse of filter).

        :param predicate: Function that takes an item and returns bool
        :returns: New filtered collection (same type as self)

        Example::

            non_admins = agents.exclude(lambda a: a.is_admin)
        """
        filtered = [item for item in self._items if not predicate(item)]
        return self._create_filtered(filtered)

    #endregion

    #region Data Conversion

    def to_list(self) -> list[T]:
        """
        Get items as a plain Python list.

        :returns: List of entity objects
        """
        return list(self._items)

    def to_dict_list(self) -> list[dict[str, Any]]:
        """
        Get items as a list of dictionaries (raw data).

        Requires items to have a `raw_data` attribute.

        :returns: List of raw API response dictionaries
        """
        result = []
        for item in self._items:
            if hasattr(item, "raw_data"):
                result.append(item.raw_data)  # type: ignore[attr-defined]
        return result

    #endregion

    #region Pagination Properties

    @property
    def is_paginated(self) -> bool:
        """Check if this collection represents paginated results."""
        return self.has_more or self.page > 1

    @property
    def count(self) -> int:
        """
        Get the count of items in this collection.

        Alias for len() for API consistency.
        """
        return len(self._items)

    #endregion

    #region String Representation

    def __repr__(self) -> str:
        """
        Return a developer-friendly string representation.

        Shows the class name, count of items, and optionally total/pagination info.

        :returns: Developer-friendly representation

        Example::

            Agents(10 of 25 agents)  # With pagination info
            Locations(5 locations)   # Without pagination info
        """
        name = self.__class__.__name__
        count = len(self._items)
        if self.total is not None:
            return f"{name}({count} of {self.total} {self._entity_name})"
        return f"{name}({count} {self._entity_name})"

    def __str__(self) -> str:
        """
        Return a user-friendly string representation.

        Delegates to to_table() for formatted output.

        :returns: Formatted table string
        """
        return self.to_table()

    def to_table(self) -> str:
        """
        Render the collection as a formatted text table.

        Subclasses should override this to provide entity-specific
        column formatting. The default implementation uses str() on each item.

        :returns: Formatted table string

        Example override::

            def to_table(self) -> str:
                lines = [f"{'ID':<10} {'Name':<30}"]
                lines.append("-" * 40)
                for item in self._items:
                    lines.append(f"{item.id:<10} {item.name:<30}")
                return "\\n".join(lines)
        """
        lines = [f"{self._entity_name.title()}:"]
        lines.append("-" * 40)
        for item in self._items:
            lines.append(str(item))
        lines.append("")
        lines.append(f"Total: {len(self._items)} {self._entity_name}")
        return "\n".join(lines)

    #endregion

    #region Rich Protocol

    def _get_rich_table_title(self) -> str:
        """
        Get the title for the Rich table.

        Subclasses can override for custom titles.

        :returns: Table title string

        Example::

            class Agents(Collection[Agent]):
                def _get_rich_table_title(self) -> str:
                    return "Active Agents"
        """
        return f"{self._entity_name.title()}"

    def _get_rich_columns(self) -> list[Any]:
        """
        Get Rich table columns for this collection.

        Subclasses should override to define their specific columns.
        Default implementation returns empty list (subclasses must implement).

        :returns: List of Rich Column objects

        Example::

            def _get_rich_columns(self) -> list[Column]:
                from rich.table import Column
                return [
                    Column("ID", style="cyan"),
                    Column("Name", style="magenta"),
                ]
        """
        # Default: empty - subclasses must override
        return []

    def __rich__(self) -> "Table":
        """
        Rich protocol - returns a Rich Table object.

        Provides graceful degradation: if Rich is not installed,
        falls back to plain text representation.

        Subclasses can override to customize table appearance.

        :returns: Rich Table object (or Text fallback if Rich not available)

        Example::

            from rich.console import Console
            console = Console()
            console.print(agents)  # Automatically calls __rich__()
        """
        try:
            from rich.table import Table
            from rich.text import Text
        except ImportError:
            # Fallback to plain text if Rich not installed
            from rich.text import Text
            return Text(str(self))

        # Create table with title
        table = Table(title=self._get_rich_table_title(), show_header=True)

        # Get columns from subclass hook
        columns = self._get_rich_columns()
        if columns:
            for col in columns:
                table.add_column(
                    col.header if hasattr(col, "header") else str(col),
                    style=getattr(col, "style", None),
                    **{k: v for k, v in col.__dict__.items() if k not in ("header", "style")}
                )
        else:
            # Default columns if subclass didn't provide any
            table.add_column("Item", style="cyan")
            for item in self._items:
                table.add_row(str(item))

        # Add rows
        if columns:
            # Subclass should handle rows in override
            # Default: just show string representation
            for item in self._items:
                table.add_row(str(item))
        else:
            for item in self._items:
                table.add_row(str(item))

        return table

    #endregion


class CachedCollection(Collection[T], ABC, Generic[T]):
    """
    Base class for collections with registry-based caching.

    Provides common caching infrastructure including:
    - Registry storage (_registry)
    - Client management (_client)
    - Full list loading tracking (_full_list_loaded)
    - set_client() method
    - from_api_response() with automatic full list loading
    - _ensure_cache_loaded() method
    - Cache management (clear_cache(), invalidate_item(), get_cache_size())

    Subclasses must implement:
    - _get_list_method_name_static() - returns client method name (e.g., "list_agents")
    - _get_entity_class_static() - returns the entity class (e.g., Agent)

    Subclasses may override:
    - _get_single_fetch_method_name_static() - return method name for single-fetch pattern
      (default: None, uses load-all pattern)
    - __class_getitem__() - only if custom behavior is needed (base implementation
      handles both single-fetch and load-all patterns)

    The entity name is automatically derived from the class name (e.g., "Agents" -> "agent").
    Override _get_entity_name_static() if your class name doesn't follow this pattern.

    :param items: List of entity objects
    :param total: Total count across all pages
    :param page: Current page number
    :param per_page: Items per page
    :param has_more: Whether more pages exist
    :param client: Client reference for API calls

    Example::

        class Agents(CachedCollection[Agent]):
            @classmethod
            def _get_list_method_name_static(cls) -> str:
                return "list_agents"

            @classmethod
            def _get_entity_class_static(cls) -> type[Agent]:
                return Agent

            def __class_getitem__(cls, agent_id: int) -> Agent:
                # Check cache first
                if agent_id in cls._registry:
                    return cls._registry[agent_id]
                # Fetch from API if not cached
                if cls._client is None:
                    raise ValueError("Client not initialized")
                agent_data = cls._client.get_agent(agent_id)
                return Agent.from_api_response(agent_data)

        # Usage:
        Agents.set_client(client)
        agents = Agents.from_api_response(api_data)  # Auto-caches all agents
        agent = Agents[1234]  # Uses cache or fetches from API
        Agents.clear_cache()  # Clear all cached agents
        Agents.invalidate_item(1234)  # Remove specific agent from cache
    """

    #region Class Attributes

    # Class-level registry (cache) and client
    _registry: dict[int, T] = {}
    _client: FreshServiceClient | None = None
    _full_list_loaded: bool = False

    # Maximum items to load when populating cache (for load-all pattern)
    # Loaded from constants.toml
    _MAX_CACHE_LOAD: int = CACHE_MAX_LOAD

    #endregion

    #region Client Management

    @classmethod
    def set_client(cls, client: FreshServiceClient) -> None:
        """
        Set the client for all operations.

        Should be called once at startup with the FreshServiceClient instance.

        :param client: The FreshServiceClient to use for API calls
        """
        cls._client = client
        entity_name = cls._get_entity_name_static()
        logger.debug(f"{entity_name.capitalize()}s registry client initialized")

    @staticmethod
    def initialize_all_registries(client: FreshServiceClient) -> None:
        """
        Initialize all CachedCollection registries with the given client.

        This is a convenience function to initialize all collection registries
        at once, typically called at CLI startup. Add new collections to the
        list below when they're created.

        :param client: The FreshServiceClient to use for all registries

        Example::

            from freshops.models.base import CachedCollection
            from freshops import FreshServiceClient, load_config

            client = FreshServiceClient(load_config())
            CachedCollection.initialize_all_registries(client)
        """
        # Import here to avoid circular dependencies
        from freshops.models.agent import Agents
        from freshops.models.department import Departments
        from freshops.models.group import Groups
        from freshops.models.location import Locations
        from freshops.models.role import Roles

        collections = [
            Agents,
            Departments,
            Groups,
            Locations,
            Roles,
        ]

        for collection in collections:
            collection.set_client(client)

        logger.info(
            f"Initialized {len(collections)} CachedCollection registries: "
            f"{', '.join(c.__name__ for c in collections)}"
        )

    @classmethod
    def _get_entity_name_static(cls) -> str:
        """
        Get the entity name for logging (e.g., "agent", "location").

        Default implementation derives entity name from collection class name.
        Override if the class name doesn't follow the pattern (e.g., "Agents" -> "agent").

        :returns: Entity name string

        Example::

            Agents._get_entity_name_static()  # Returns "agent"
            Locations._get_entity_name_static()  # Returns "location"
        """
        # Derive from class name: "Agents" -> "agent", "Locations" -> "location"
        class_name = cls.__name__
        # Remove trailing 's' if plural, then lowercase
        if class_name.endswith("s") and len(class_name) > 1:
            return class_name[:-1].lower()
        return class_name.lower()

    #endregion

    #region Helper Methods

    def _get_list_method_name(self) -> str:
        """
        Get the client method name for listing all items (instance method).

        Default implementation calls the static method. Override if needed.

        :returns: Method name (e.g., "list_agents", "list_locations")
        """
        return type(self)._get_list_method_name_static()

    def _get_entity_class(self) -> type[T]:
        """
        Get the entity class for creating instances (instance method).

        Default implementation calls the static method. Override if needed.

        :returns: The entity class (e.g., Agent, Location)
        """
        return type(self)._get_entity_class_static()

    @classmethod
    def _get_single_fetch_method_name_static(cls) -> str | None:
        """
        Get the client method name for fetching a single item (class method).

        If this returns a method name (e.g., "get_agent"), __class_getitem__
        will use single-fetch pattern. If None, uses load-all pattern.

        Default: None (use load-all pattern)
        Override to return method name for single-fetch (e.g., "get_agent")

        :returns: Method name (e.g., "get_agent") or None for load-all pattern

        Example::

            class Agents(CachedCollection[Agent]):
                @classmethod
                def _get_single_fetch_method_name_static(cls) -> str | None:
                    return "get_agent"  # Use single fetch
        """
        return None

    #endregion

    #region Initialization

    def __init__(
        self,
        items: list[T] | None = None,
        *,
        total: int | None = None,
        page: int = 1,
        per_page: int = 100,
        has_more: bool = False,
        client: FreshServiceClient | None = None,
    ) -> None:
        """Initialize the cached collection."""
        super().__init__(
            items,
            total=total,
            page=page,
            per_page=per_page,
            has_more=has_more,
            client=client,
        )
        # Set client in registry if provided
        if client:
            self.set_client(client)

    #endregion

    #region Factory Methods

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
    ) -> Any:  # Returns subclass instance, not base class
        """
        Create a collection from an API response.

        If full list hasn't been loaded yet, loads all items and
        caches them. If already loaded, uses cached data (no API call).

        :param data: List of entity dictionaries from the API
        :param total: Total count from API response
        :param page: Current page number
        :param per_page: Items per page
        :param has_more: Whether more pages exist
        :param client: Client reference for pagination
        :returns: A new collection instance
        """
        # Set client if provided
        if client:
            cls.set_client(client)

        # If full list not loaded, load it now
        if not cls._full_list_loaded and cls._client:
            entity_name = cls._get_entity_name_static()
            logger.info(f"Loading full {entity_name} list into cache")
            # Clear registry and load all
            cls._registry.clear()
            # Get the list method from client
            list_method_name = cls._get_list_method_name_static()
            list_method = getattr(cls._client, list_method_name)
            all_data = list_method(limit=cls._MAX_CACHE_LOAD)
            logger.debug(f"Loading {len(all_data)} {entity_name}s into registry")
            # Get entity class and create instances
            entity_class = cls._get_entity_class_static()
            for item_data in all_data:
                entity_class.from_api_response(item_data)
            cls._full_list_loaded = True
            logger.info(
                f"{entity_name.capitalize()} cache populated with "
                f"{len(cls._registry)} {entity_name}s"
            )

        # Get items from registry (or create from provided data)
        if cls._full_list_loaded:
            # Use registry
            items = list(cls._registry.values())
        else:
            # Not loaded yet - create from provided data
            entity_class = cls._get_entity_class_static()
            items = [
                entity_class.from_api_response(item_data) for item_data in data
            ]

        collection = cls(
            items,
            total=total,
            page=page,
            per_page=per_page,
            has_more=has_more,
            client=client,
        )
        # Allow subclasses to perform post-initialization (e.g., inject client)
        collection._post_init_from_api_response()
        return collection

    def _post_init_from_api_response(self) -> None:
        """
        Hook for subclasses to perform post-initialization after from_api_response.

        Called after collection is created. Override to inject client into items
        or perform other setup.

        Default implementation does nothing.
        """
        pass

    #endregion

    #region Cache Loading

    def _ensure_cache_loaded(self) -> None:
        """
        Ensure the full list is loaded in registry before filtering.

        If not already loaded, fetches all items and stores them in registry.
        """
        cls = type(self)
        if not cls._full_list_loaded and cls._client:
            entity_name = cls._get_entity_name_static()
            logger.info(f"Loading full {entity_name} list for filtering")
            # Clear registry and load all
            cls._registry.clear()
            # Get the list method from client
            list_method_name = cls._get_list_method_name_static()
            list_method = getattr(cls._client, list_method_name)
            all_data = list_method(limit=cls._MAX_CACHE_LOAD)
            logger.debug(f"Loading {len(all_data)} {entity_name}s into registry")
            # Get entity class and create instances
            entity_class = cls._get_entity_class_static()
            for item_data in all_data:
                entity_class.from_api_response(item_data)
            cls._full_list_loaded = True
            logger.debug(
                f"{entity_name.capitalize()} cache populated with "
                f"{len(cls._registry)} {entity_name}s for filtering"
            )

    #endregion

    #region Abstract Methods

    @classmethod
    @abstractmethod
    def _get_list_method_name_static(cls) -> str:
        """
        Get the client method name for listing all items (class method).

        :returns: Method name (e.g., "list_agents", "list_locations")
        """
        pass

    @classmethod
    @abstractmethod
    def _get_entity_class_static(cls) -> type[T]:
        """
        Get the entity class for creating instances (class method).

        :returns: The entity class (e.g., Agent, Location)
        """
        pass

    def __class_getitem__(cls, item: int | type) -> T | type:  # type: ignore[return-value]
        """
        Get an entity by ID from the registry (cache), or handle generic type parameters.

        When called with an int (e.g., `Groups[1234]`), performs registry lookup.
        When called with a type (e.g., `CachedCollection[Location]`), handles generic type resolution.

        Default implementation handles two patterns:
        1. **Single-fetch pattern**: If `_get_single_fetch_method_name_static()` returns
           a method name, fetches that single item from API.
        2. **Load-all pattern**: Otherwise, loads all items into cache, then checks again.

        Subclasses can override for custom behavior, but this default should work
        for most cases.

        :param item: The entity ID (int) or type parameter (for generics)
        :returns: Entity instance (from cache or fetched from API) or class (for generics)
        :raises ValueError: If client not initialized or entity not found

        Example::

            Groups.set_client(client)
            group = Groups[1234]  # Uses cache or loads all groups
        """
        # Handle generic type parameters (e.g., CachedCollection[Location])
        # When Python evaluates the generic during class definition, it passes a type, not an int
        if isinstance(item, type):
            # For generics, create a GenericAlias to properly handle type parameterization
            # This is called during class definition (e.g., class Locations(CachedCollection[Location]))
            # not during runtime lookup (e.g., Locations[1234])
            from typing import _GenericAlias  # type: ignore[attr-defined]
            return _GenericAlias(cls, (item,))  # type: ignore[no-any-return]

        # At this point, item should be an int (entity ID) for runtime lookups
        item_id: int = item  # type: ignore[assignment]

        # Check registry first
        if item_id in cls._registry:
            cached = cls._registry[item_id]
            entity_name = cls._get_entity_name_static()
            logger.debug(f"{entity_name.capitalize()} {item_id} retrieved from registry")
            return cached

        # Not in registry - check if client is initialized
        if cls._client is None:
            raise RegistryClientNotInitializedError(cls.__name__)

        # Check if this collection uses single-fetch pattern
        single_fetch_method = cls._get_single_fetch_method_name_static()
        if single_fetch_method:
            # Single-fetch pattern: call get_agent(), get_ticket(), etc.
            entity_name = cls._get_entity_name_static()
            logger.debug(f"Fetching {entity_name} {item_id} from API (single fetch)")

            try:
                # Get the method from client
                get_method = getattr(cls._client, single_fetch_method)
                entity_data = get_method(item_id)
                entity_class = cls._get_entity_class_static()
                entity = entity_class.from_api_response(entity_data)
                logger.debug(
                    f"{entity_name.capitalize()} {item_id} fetched and cached"
                )
                return entity
            except (ValueError, AttributeError) as e:
                # If it's already an EntityNotFoundError, re-raise it
                if isinstance(e, EntityNotFoundError):
                    raise
                logger.warning(
                    f"{entity_name.capitalize()} {item_id} not found: {e}"
                )
                raise EntityNotFoundError(entity_name, item_id) from e
        else:
            # Load-all pattern: load all items, then check cache again
            entity_name = cls._get_entity_name_static()
            logger.debug(
                f"{entity_name.capitalize()} {item_id} not in cache, "
                f"loading all {entity_name}s"
            )

            # Load all items into cache
            list_method_name = cls._get_list_method_name_static()
            list_method = getattr(cls._client, list_method_name)
            all_items_data = list_method(limit=cls._MAX_CACHE_LOAD)
            logger.debug(f"Loading {len(all_items_data)} {entity_name}s into registry")

            # Create instances (which will cache themselves)
            entity_class = cls._get_entity_class_static()
            for item_data in all_items_data:
                entity_class.from_api_response(item_data)

            # Check registry again after loading
            if item_id in cls._registry:
                cached = cls._registry[item_id]
                logger.debug(
                    f"{entity_name.capitalize()} {item_id} retrieved from "
                    f"registry after loading"
                )
                return cached

            # Still not found after loading all items
            raise EntityNotFoundError(entity_name, item_id)

    #endregion

    #region Cache Management

    @classmethod
    def clear_cache(cls) -> None:
        """
        Clear the entire registry cache.

        Useful for forcing a refresh of all cached data or freeing memory.

        Example::

            Agents.clear_cache()  # Clears all cached agents
        """
        cls._registry.clear()
        cls._full_list_loaded = False
        entity_name = cls._get_entity_name_static()
        logger.info(f"{cls.__name__} cache cleared")

    @classmethod
    def invalidate_item(cls, item_id: int) -> None:
        """
        Remove a specific item from the cache.

        The next access to this item will trigger a fresh API call.

        :param item_id: The ID of the item to invalidate

        Example::

            Agents.invalidate_item(1234)  # Remove agent 1234 from cache
        """
        if item_id in cls._registry:
            del cls._registry[item_id]
            entity_name = cls._get_entity_name_static()
            logger.debug(f"{entity_name.capitalize()} {item_id} invalidated from cache")

    @classmethod
    def get_cache_size(cls) -> int:
        """
        Get the number of items currently in the cache.

        :returns: Number of cached items

        Example::

            size = Agents.get_cache_size()
            print(f"Cache contains {size} agents")
        """
        return len(cls._registry)

    #endregion

    #region String Representation
    # __repr__ and __str__ are inherited from Collection base class
    #endregion
