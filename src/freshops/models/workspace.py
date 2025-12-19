"""
Workspace model for FreshService workspaces.

Provides typed access to workspace data returned by the FreshService API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from freshops.models.base import Collection, FreshModel

if TYPE_CHECKING:
    from freshops.client import FreshServiceClient


@dataclass(eq=False, repr=False)  # Use FreshModel.__eq__ and __repr__ instead
class Workspace(FreshModel):
    """
    Represents a FreshService workspace.

    Workspaces segment a FreshService instance for different teams
    or business units.

    :ivar id: Unique workspace identifier
    :ivar name: Workspace name
    :ivar description: Workspace description
    :ivar primary: Whether this is the primary workspace
    :ivar created_at: When the workspace was created
    :ivar updated_at: When the workspace was last updated
    :ivar raw_data: The original API response dictionary

    Example::

        workspace = Workspace.from_api_response(api_data)
        print(f"{workspace.name}")
    """

    _id: int
    _name: str = ""

    @property
    def id(self) -> int:
        """Get the workspace's unique identifier."""
        return self._id

    @property
    def name(self) -> str:
        """Get the workspace name."""
        return self._name
    description: str = ""
    primary: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Workspace:
        """
        Create a Workspace instance from an API response dictionary.

        :param data: Dictionary from the FreshService API
        :returns: A new Workspace instance
        """
        return cls(
            _id=data.get("id", 0),
            _name=data.get("name", "") or "",
            description=data.get("description", "") or "",
            primary=data.get("primary", False),
            created_at=cls.parse_datetime(data.get("created_at")),
            updated_at=cls.parse_datetime(data.get("updated_at")),
            raw_data=data,
        )

    @property
    def is_primary(self) -> bool:
        """Check if this is the primary workspace."""
        return self.primary

    def __str__(self) -> str:
        """Return a human-readable string representation of the Workspace."""
        suffix = " [primary]" if self.primary else ""
        return f"{self.name} ({self.id}){suffix}"


class Workspaces(Collection[Workspace]):
    """
    A collection of Workspace objects.

    :param workspaces: List of Workspace objects
    """

    _entity_name = "workspaces"

    def __init__(
        self,
        workspaces: list[Workspace] | None = None,
        *,
        total: int | None = None,
        page: int = 1,
        per_page: int = 100,
        has_more: bool = False,
        client: FreshServiceClient | None = None,
    ) -> None:
        """Initialize the Workspaces collection."""
        super().__init__(
            workspaces,
            total=total,
            page=page,
            per_page=per_page,
            has_more=has_more,
            client=client,
        )

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
    ) -> Workspaces:
        """
        Create a Workspaces collection from an API response.

        :param data: List of workspace dictionaries from the API
        :returns: A new Workspaces collection
        """
        workspaces = [Workspace.from_api_response(w) for w in data]
        return cls(
            workspaces,
            total=total,
            page=page,
            per_page=per_page,
            has_more=has_more,
            client=client,
        )

    def _create_filtered(self, items: list[Workspace]) -> Workspaces:
        """Create a new Workspaces collection with filtered items."""
        return Workspaces(items, client=self._client)

    def find_by_name(self, name: str) -> Workspace | None:
        """
        Find a workspace by name (case-insensitive).

        :param name: The workspace name to search for
        :returns: The Workspace if found, None otherwise
        """
        name_lower = name.lower()
        for ws in self._items:
            if ws.name.lower() == name_lower:
                return ws
        return None

    def get_primary(self) -> Workspace | None:
        """
        Get the primary workspace.

        :returns: The primary Workspace if found, None otherwise
        """
        for ws in self._items:
            if ws.primary:
                return ws
        return None

