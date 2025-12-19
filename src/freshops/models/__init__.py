"""
FreshOps data models.

This module provides typed Python objects for FreshService entities,
making it easier to work with API responses in a structured way.

Example::

    from freshops import FreshServiceClient, load_config
    from freshops.models import Agent, Agents

    client = FreshServiceClient(load_config())
    agents = client.list_agents()

    for agent in agents:
        print(f"{agent.full_name} ({agent.email})")
"""

from freshops.models.agent import Agent, AgentRole, Agents, WorkspaceInfo
from freshops.models.base import CachedCollection, Collection, FreshModel
from freshops.models.department import Department, Departments
from freshops.models.group import Group, Groups
from freshops.models.location import Location, Locations
from freshops.models.role import Role, Roles
from freshops.models.workspace import Workspace, Workspaces

__all__ = [
    # Base classes
    "FreshModel",
    "Collection",
    "CachedCollection",
    # Agent
    "Agent",
    "Agents",
    "AgentRole",
    "WorkspaceInfo",
    # Role
    "Role",
    "Roles",
    # Department
    "Department",
    "Departments",
    # Location
    "Location",
    "Locations",
    # Group
    "Group",
    "Groups",
    # Workspace
    "Workspace",
    "Workspaces",
]
