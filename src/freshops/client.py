"""
FreshService API client.

Provides a client for interacting with the FreshService REST API.
"""

from __future__ import annotations

from typing import Any

import requests
from loguru import logger

from freshops.config import FreshServiceConfig


class FreshServiceClient:
    """
    Client for FreshService API operations.

    Provides read-only access to FreshService resources with
    integrated loguru logging for all API calls.

    :param config: The FreshServiceConfig containing connection details

    Example::

        from freshops import FreshServiceClient, load_config

        config = load_config()
        client = FreshServiceClient(config)
        agents = client.list_agents()

    Or with direct parameters::

        client = FreshServiceClient.from_credentials(
            domain="company.freshservice.com",
            api_key="your_api_key"
        )
    """

    def __init__(self, config: FreshServiceConfig) -> None:
        """
        Initialize the FreshService client.

        :param config: Configuration object with domain (company name only) and API key
        """
        self.config = config

        # Domain should be just the company name (e.g., "evergreen")
        # We always use .freshservice.com as the suffix
        self.base_url = f"https://{config.domain}.freshservice.com/api/v2"

        # FreshService uses API key as username, 'X' as password
        self.auth = (config.api_key, "X")
        self.headers = {"Content-Type": "application/json"}
        logger.debug(f"FreshService client initialized: {self.base_url}")

    @classmethod
    def from_credentials(
        cls, domain: str, api_key: str, log_level: str = "INFO"
    ) -> FreshServiceClient:
        """
        Create a client directly from credentials.

        :param domain: FreshService company name (e.g., 'mycompany', not the full URL)
        :param api_key: FreshService API key
        :param log_level: Logging level (default: INFO)
        :returns: Configured FreshServiceClient instance

        Example::

            client = FreshServiceClient.from_credentials(
                domain="mycompany",
                api_key="your_api_key"
            )
        """
        config = FreshServiceConfig(
            domain=domain,
            api_key=api_key,
            log_level=log_level,
        )
        return cls(config)

    def _get(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make a GET request to the FreshService API.

        :param endpoint: API endpoint (e.g., '/agents')
        :param params: Optional query parameters
        :returns: JSON response as dictionary
        :raises requests.HTTPError: If the request fails
        :raises ValueError: If response is invalid
        """
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"GET {url} params={params}")

        response = requests.get(
            url,
            auth=self.auth,
            headers=self.headers,
            params=params,
            timeout=30,
        )

        logger.debug(f"Response status: {response.status_code}")

        # Log rate limit info if available
        rate_total = response.headers.get("X-Ratelimit-Total")
        rate_remaining = response.headers.get("X-Ratelimit-Remaining")
        if rate_total and rate_remaining:
            logger.debug(f"Rate limit: {rate_remaining}/{rate_total} remaining")

        if response.status_code != 200:
            logger.error(f"API error: {response.status_code} - {response.text}")
            response.raise_for_status()

        # Handle empty response
        if not response.text:
            logger.error("API returned empty response")
            raise ValueError("API returned empty response")

        try:
            return response.json()
        except requests.exceptions.JSONDecodeError as e:
            # HTML response usually means auth failure or wrong domain
            if "<html" in response.text.lower():
                logger.error("API returned HTML instead of JSON - likely auth issue")
                raise ValueError(
                    "Authentication failed or wrong domain. "
                    "Check FRESHSERVICE_DOMAIN (should be just 'mycompany', "
                    "not full URL) and FRESHSERVICE_API_KEY in your .env file."
                ) from e
            logger.error(f"Failed to parse JSON: {response.text[:500]}")
            raise ValueError(f"Invalid JSON response: {e}") from e

    # -------------------------------------------------------------------------
    # Ticket Operations
    # -------------------------------------------------------------------------

    def list_tickets(
        self,
        status: str | None = None,
        priority: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        List tickets with optional filtering.

        :param status: Filter by ticket status (open, pending, resolved, closed)
        :param priority: Filter by priority (low, medium, high, urgent)
        :param limit: Maximum number of tickets to return
        :returns: List of ticket dictionaries

        Example::

            tickets = client.list_tickets(status="open", limit=10)
            for ticket in tickets:
                print(ticket["id"], ticket["subject"])
        """
        raise NotImplementedError("list_tickets not yet implemented")

    def get_ticket(self, ticket_id: int) -> dict[str, Any]:
        """
        Get a specific ticket by ID.

        :param ticket_id: The ticket ID to retrieve
        :returns: Ticket data as a dictionary
        :raises ValueError: If ticket is not found

        Example::

            ticket = client.get_ticket(12345)
            print(ticket["subject"])
        """
        raise NotImplementedError("get_ticket not yet implemented")

    # -------------------------------------------------------------------------
    # Agent Operations
    # -------------------------------------------------------------------------

    def list_agents(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        List all agents in the FreshService instance.

        :param limit: Maximum number of agents to return
        :returns: List of agent dictionaries

        Example::

            agents = client.list_agents()
            for agent in agents:
                print(agent["first_name"], agent["email"])
        """
        logger.debug(f"Listing agents (limit={limit})")
        params = {"per_page": min(limit, 100)}  # API max is 100 per page

        response = self._get("/agents", params=params)
        agents = response.get("agents", [])

        logger.info(f"Retrieved {len(agents)} agents")
        return agents

    def get_agent(self, agent_id: int) -> dict[str, Any]:
        """
        Get a specific agent by ID.

        :param agent_id: The agent ID to retrieve
        :returns: Agent data as a dictionary
        :raises ValueError: If agent is not found
        """
        logger.debug(f"Getting agent {agent_id}")
        response = self._get(f"/agents/{agent_id}")
        agent = response.get("agent", response)
        logger.info(f"Retrieved agent {agent_id}")
        return agent

    # -------------------------------------------------------------------------
    # Requester Operations
    # -------------------------------------------------------------------------

    def list_requesters(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        List requesters in the FreshService instance.

        :param limit: Maximum number of requesters to return
        :returns: List of requester dictionaries

        Example::

            requesters = client.list_requesters()
            for req in requesters:
                print(req["name"], req["email"])
        """
        raise NotImplementedError("list_requesters not yet implemented")

    def search_requesters(
        self,
        email: str | None = None,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for requesters by email or name.

        :param email: Email address to search for
        :param name: Name to search for
        :returns: List of matching requester dictionaries

        Example::

            matches = client.search_requesters(email="user@example.com")
        """
        raise NotImplementedError("search_requesters not yet implemented")

    # -------------------------------------------------------------------------
    # Location Operations
    # -------------------------------------------------------------------------

    def list_locations(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        List all locations in the FreshService instance.

        :param limit: Maximum number of locations to return
        :returns: List of location dictionaries

        Example::

            locations = client.list_locations()
            for location in locations:
                print(location["name"], location["city"])
        """
        logger.debug(f"Listing locations (limit={limit})")
        params = {"per_page": min(limit, 100)}  # API max is 100 per page

        response = self._get("/locations", params=params)
        locations = response.get("locations", [])

        logger.info(f"Retrieved {len(locations)} locations")
        return locations

    def get_location(self, location_id: int) -> dict[str, Any]:
        """
        Get a specific location by ID.

        :param location_id: The location ID to retrieve
        :returns: Location data as a dictionary
        :raises ValueError: If location is not found
        """
        logger.debug(f"Getting location {location_id}")
        response = self._get(f"/locations/{location_id}")
        location = response.get("location", response)
        logger.info(f"Retrieved location {location_id}")
        return location

    # -------------------------------------------------------------------------
    # Group Operations
    # -------------------------------------------------------------------------

    def list_groups(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        List all agent groups in the FreshService instance.

        :param limit: Maximum number of groups to return
        :returns: List of group dictionaries

        Example::

            groups = client.list_groups()
            for group in groups:
                print(group["name"], len(group.get("members", [])))
        """
        logger.debug(f"Listing groups (limit={limit})")
        params = {"per_page": min(limit, 100)}  # API max is 100 per page

        response = self._get("/groups", params=params)
        groups = response.get("groups", [])

        logger.info(f"Retrieved {len(groups)} groups")
        return groups

    # -------------------------------------------------------------------------
    # Role Operations
    # -------------------------------------------------------------------------

    def list_roles(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        List all agent roles in the FreshService instance.

        :param limit: Maximum number of roles to return
        :returns: List of role dictionaries

        Example::

            roles = client.list_roles()
            for role in roles:
                print(role["name"], role.get("role_type"))
        """
        logger.debug(f"Listing roles (limit={limit})")
        params = {"per_page": min(limit, 100)}  # API max is 100 per page

        response = self._get("/roles", params=params)
        roles = response.get("roles", [])

        logger.info(f"Retrieved {len(roles)} roles")
        return roles

    # -------------------------------------------------------------------------
    # Department Operations
    # -------------------------------------------------------------------------

    def list_departments(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        List all departments in the FreshService instance.

        :param limit: Maximum number of departments to return
        :returns: List of department dictionaries

        Example::

            departments = client.list_departments()
            for dept in departments:
                print(dept["name"], dept.get("workspace_id"))
        """
        logger.debug(f"Listing departments (limit={limit})")
        params = {"per_page": min(limit, 100)}  # API max is 100 per page

        response = self._get("/departments", params=params)
        departments = response.get("departments", [])

        logger.info(f"Retrieved {len(departments)} departments")
        return departments

    # -------------------------------------------------------------------------
    # Asset Operations
    # -------------------------------------------------------------------------

    def list_assets(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        List assets in the FreshService instance.

        :param limit: Maximum number of assets to return
        :returns: List of asset dictionaries

        Example::

            assets = client.list_assets()
            for asset in assets:
                print(asset["name"], asset["asset_type"])
        """
        raise NotImplementedError("list_assets not yet implemented")

    def search_assets(self, name: str | None = None) -> list[dict[str, Any]]:
        """
        Search for assets by name.

        :param name: Asset name to search for
        :returns: List of matching asset dictionaries

        Example::

            laptops = client.search_assets(name="laptop")
        """
        raise NotImplementedError("search_assets not yet implemented")

    def get_asset(self, asset_id: int) -> dict[str, Any]:
        """
        Get a specific asset by ID.

        :param asset_id: The asset ID to retrieve
        :returns: Asset data as a dictionary
        :raises ValueError: If asset is not found
        """
        raise NotImplementedError("get_asset not yet implemented")
