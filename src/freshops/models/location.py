"""
Location model for FreshService locations.

Provides typed access to location data returned by the FreshService API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from freshops.exceptions import InvalidEntityIdError
from freshops.models.base import CachedCollection, FreshModel

if TYPE_CHECKING:
    from freshops.client import FreshServiceClient

from loguru import logger


@dataclass(eq=False, repr=False)  # Use FreshModel.__eq__ and __repr__ instead
class Location(FreshModel):
    """
    Represents a FreshService location.

    Locations refer to cities, campuses, offices and rooms where
    assets and users can be found.

    Locations are cached in the Locations collection registry.

    :ivar id: Unique location identifier
    :ivar name: Location name (mandatory)
    :ivar workspace_id: Client ID/workspace ID the location belongs to
    :ivar parent_location_id: ID of parent location (for hierarchy)
    :ivar primary_contact_id: User ID of the primary contact
    :ivar line1: Address line 1
    :ivar line2: Address line 2
    :ivar city: City name
    :ivar state: State/Province name
    :ivar country: Country name
    :ivar zipcode: ZIP/Postal code
    :ivar contact_name: Name of the contact person
    :ivar email: Email address of the contact
    :ivar phone: Phone number of the contact
    :ivar created_at: When the location was created
    :ivar updated_at: When the location was last updated
    :ivar raw_data: The original API response dictionary

    Example::

        # From full API data
        location = Location.from_api_response(api_data)

        # From registry (loads immediately)
        location = Locations[1234]
        print(location.name)
    """

    # Required fields
    _id: int
    _name: str

    @property
    def id(self) -> int:
        """Get the location's unique identifier."""
        return self._id

    @property
    def name(self) -> str:
        """Get the location name."""
        return self._name

    # Location details
    workspace_id: int | None = None
    parent_location_id: int | None = None
    primary_contact_id: int | None = None

    # Address fields
    line1: str = ""
    line2: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    zipcode: str = ""

    # Contact info
    contact_name: str = ""
    email: str = ""
    phone: str = ""

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Raw data for accessing unlisted fields
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Location:
        """
        Create a Location instance from an API response dictionary.

        Always creates a new instance from the API data and updates the cache.
        This ensures the cache always contains the authoritative data from the API.

        :param data: Dictionary from the FreshService API
        :returns: A new Location instance (cached in registry)

        Example::

            response = client._get("/locations/123")
            location = Location.from_api_response(response["location"])
        """
        location_id = data.get("id", 0)
        if not location_id or location_id <= 0:
            raise InvalidEntityIdError("Location", location_id)

        # Validate required fields
        name = cls._validate_required_field(data.get("name"), "name")

        # Always create a new instance from API data (authoritative source)
        location = cls(
            _id=location_id,
            _name=name,
            workspace_id=data.get("workspace_id"),
            parent_location_id=data.get("parent_location_id"),
            primary_contact_id=data.get("primary_contact_id"),
            line1=data.get("line1", "") or "",
            line2=data.get("line2", "") or "",
            city=data.get("city", "") or "",
            state=data.get("state", "") or "",
            country=data.get("country", "") or "",
            zipcode=str(data.get("zipcode", "") or ""),
            contact_name=data.get("contact_name", "") or "",
            email=data.get("email", "") or "",
            phone=str(data.get("phone", "") or ""),
            created_at=cls.parse_datetime(data.get("created_at")),
            updated_at=cls.parse_datetime(data.get("updated_at")),
            raw_data=data,
        )

        # Update cache with authoritative data (replaces existing if present)
        Locations._registry[location_id] = location
        logger.debug(f"Location {location_id} created/updated in cache")
        return location

    @property
    def full_address(self) -> str:
        """
        Get the full formatted address.

        :returns: Combined address components
        """
        parts = []
        if self.line1:
            parts.append(self.line1)
        if self.line2:
            parts.append(self.line2)
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.zipcode:
            parts.append(self.zipcode)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)

    @property
    def is_child_location(self) -> bool:
        """
        Check if this is a child location (has a parent).

        :returns: True if has a parent location
        """
        return self.parent_location_id is not None

    @property
    def is_top_level(self) -> bool:
        """
        Check if this is a top-level location (no parent).

        :returns: True if no parent location
        """
        return self.parent_location_id is None

    def to_detail(self) -> str:
        """
        Return a detailed multi-line string representation.

        :returns: Multi-line detailed view of the location
        """
        lines = [
            f"Location: {self.name}",
            f"{'=' * 40}",
            f"ID:              {self.id}",
        ]

        if self.workspace_id:
            lines.append(f"Workspace ID:    {self.workspace_id}")

        address = self.full_address
        if address:
            lines.append(f"Address:         {address}")

        if self.city:
            lines.append(f"City:            {self.city}")

        if self.state:
            lines.append(f"State:           {self.state}")

        if self.country:
            lines.append(f"Country:         {self.country}")

        if self.zipcode:
            lines.append(f"ZIP Code:        {self.zipcode}")

        if self.parent_location_id:
            lines.append(f"Parent Location: {self.parent_location_id}")

        if self.primary_contact_id:
            lines.append(f"Primary Contact: {self.primary_contact_id}")

        if self.contact_name:
            lines.append(f"Contact Name:    {self.contact_name}")

        if self.email:
            lines.append(f"Contact Email:   {self.email}")

        if self.phone:
            lines.append(f"Contact Phone:   {self.phone}")

        if self.created_at:
            lines.append(f"Created:         {self.created_at}")

        if self.updated_at:
            lines.append(f"Updated:         {self.updated_at}")

        return "\n".join(lines)

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        if self.city and self.country:
            return f"Location({self.id}: {self.name}, {self.city}, {self.country})"
        elif self.city:
            return f"Location({self.id}: {self.name}, {self.city})"
        return f"Location({self.id}: {self.name})"


class Locations(CachedCollection[Location]):
    """
    A collection of Location objects with registry-based caching.

    Acts as both a collection and a registry for Location instances.
    Use Locations[1234] to get a Location by ID (from cache or creates new).

    :param locations: List of Location objects
    """

    _entity_name = "locations"

    #region Rich Protocol
    def _get_rich_table_title(self) -> str:
        """
        Get the title for the Rich locations table.

        :returns: Table title string
        """
        if self.total is not None and self.total != len(self._items):
            return f"Locations ({len(self._items)} of {self.total})"
        return f"Locations ({len(self._items)})"

    def _get_rich_columns(self) -> list[Any]:
        """
        Get Rich table columns for locations.

        :returns: List of Rich Column objects
        """
        try:
            from rich.table import Column
        except ImportError:
            return []

        return [
            Column("ID", style="cyan", no_wrap=True, justify="right"),
            Column("Name", style="magenta", overflow="fold"),
            Column("City", style="blue", overflow="fold"),
            Column("Country", style="green", overflow="fold"),
        ]

    def __rich__(self) -> Any:  # Returns Table when Rich available, str otherwise
        """
        Rich protocol - returns a Rich Table object for locations.

        Provides location-specific table with ID, Name, City, and Country columns.

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
            table.add_column("City", style="blue")
            table.add_column("Country", style="green")

        # Add rows with location data
        if not self._items:
            table.add_row(Text("No locations found.", justify="center", style="dim"), span_columns=True)
        else:
            for location in self._items:
                # Ensure location data is loaded for display
                # Use em-dash (—) for missing values
                city = location.city if location.city else "—"
                country = location.country if location.country else "—"
                table.add_row(
                    str(location.id),
                    location.name,
                    city,
                    country,
                )
        return table
    #endregion


    @classmethod
    def _get_list_method_name_static(cls) -> str:
        """Get the client method name for listing locations."""
        return "list_locations"

    @classmethod
    def _get_entity_class_static(cls) -> type[Location]:
        """Get the Location entity class."""
        return Location

    @classmethod
    def _get_single_fetch_method_name_static(cls) -> str | None:
        """
        Return "get_location" to use single-fetch pattern for Locations.

        Locations uses single-fetch because get_location() is more efficient
        than loading all locations when looking up a single location.
        """
        return "get_location"


    def _create_filtered(self, items: list[Location]) -> Locations:
        """Create a new Locations collection with filtered items."""
        return Locations(items, client=self._client)


    def to_table(self) -> str:
        """
        Render the locations as a formatted text table.

        :returns: Formatted table string
        """
        # Column widths
        id_w, name_w, city_w = 10, 40, 30

        # Header
        lines = [
            f"{'ID':<{id_w}} {'Name':<{name_w}} {'City':<{city_w}}",
            "-" * (id_w + name_w + city_w + 2),
        ]

        # Rows
        for location in self._items:
            name = location.name[:name_w]
            city = location.city[:city_w] if location.city else ""
            lines.append(
                f"{location.id:<{id_w}} {name:<{name_w}} {city:<{city_w}}"
            )

        # Footer
        lines.append("")
        if self.total is not None and self.total != len(self._items):
            lines.append(f"Showing {len(self._items)} of {self.total} locations")
        else:
            lines.append(f"Total: {len(self._items)} locations")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Location-specific lookups
    # -------------------------------------------------------------------------

    def find_by_name(self, name: str) -> Location | None:
        """
        Find a location by name (case-insensitive).

        Loads full list into registry if not already loaded, then searches locally.

        :param name: The location name to search for
        :returns: The Location if found, None otherwise
        """
        self._ensure_cache_loaded()
        # Search in registry (all locations)
        name_lower = name.lower()
        for location in self._registry.values():
            if location and location.name.lower() == name_lower:
                return location
        return None

    # -------------------------------------------------------------------------
    # Location-specific filters
    # -------------------------------------------------------------------------

    def in_country(self, country: str) -> Locations:
        """
        Get locations in a specific country (case-insensitive).

        Loads full list into cache if not already loaded, then filters locally.

        :param country: Country name to filter by
        :returns: A new Locations collection with matching locations

        Example::

            us_locations = locations.in_country("United States")
        """
        self._ensure_cache_loaded()
        country_lower = country.lower()
        # Filter from registry (all locations)
        filtered = [
            loc for loc in self._registry.values()
            if loc and loc.country.lower() == country_lower
        ]
        return self._create_filtered(filtered)

    def in_city(self, city: str) -> Locations:
        """
        Get locations in a specific city (case-insensitive).

        Loads full list into cache if not already loaded, then filters locally.

        :param city: City name to filter by
        :returns: A new Locations collection with matching locations

        Example::

            seattle_locs = locations.in_city("Seattle")
        """
        self._ensure_cache_loaded()
        city_lower = city.lower()
        # Filter from registry (all locations)
        filtered = [
            loc for loc in self._registry.values()
            if loc and loc.city.lower() == city_lower
        ]
        return self._create_filtered(filtered)

    def in_state(self, state: str) -> Locations:
        """
        Get locations in a specific state/province (case-insensitive).

        Loads full list into cache if not already loaded, then filters locally.

        :param state: State name to filter by
        :returns: A new Locations collection with matching locations

        Example::

            wa_locations = locations.in_state("Washington")
        """
        self._ensure_cache_loaded()
        state_lower = state.lower()
        # Filter from registry (all locations)
        filtered = [
            loc for loc in self._registry.values()
            if loc and loc.state.lower() == state_lower
        ]
        return self._create_filtered(filtered)

    def top_level(self) -> Locations:
        """
        Get only top-level locations (no parent).

        Loads full list into cache if not already loaded, then filters locally.

        :returns: A new Locations collection with only top-level locations

        Example::

            root_locations = locations.top_level()
        """
        self._ensure_cache_loaded()
        # Filter from registry (all locations)
        filtered = [
            loc for loc in self._registry.values()
            if loc and loc.parent_location_id is None
        ]
        return self._create_filtered(filtered)

    def children_of(self, parent_id: int) -> Locations:
        """
        Get child locations of a specific parent.

        Loads full list into cache if not already loaded, then filters locally.

        :param parent_id: Parent location ID
        :returns: A new Locations collection with child locations

        Example::

            building_rooms = locations.children_of(building_id)
        """
        self._ensure_cache_loaded()
        # Filter from registry (all locations)
        filtered = [
            loc for loc in self._registry.values()
            if loc and loc.parent_location_id == parent_id
        ]
        return self._create_filtered(filtered)

    def in_workspace(self, workspace_id: int) -> Locations:
        """
        Get locations in a specific workspace/client.

        Loads full list into cache if not already loaded, then filters locally.

        :param workspace_id: Workspace/client ID to filter by
        :returns: A new Locations collection with matching locations
        """
        self._ensure_cache_loaded()
        # Filter from registry (all locations)
        filtered = [
            loc for loc in self._registry.values()
            if loc and loc.workspace_id == workspace_id
        ]
        return self._create_filtered(filtered)
