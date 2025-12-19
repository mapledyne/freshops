"""
FreshOps - FreshService API library and CLI tool.

A Python library for interacting with the FreshService API,
with an optional CLI for command-line usage.

Usage as a library::

    from freshops import FreshServiceClient, load_config

    # Load config from environment/.env
    config = load_config()
    client = FreshServiceClient(config)
    agents = client.list_agents()

    # Or create client directly
    client = FreshServiceClient.from_credentials(
        domain="company.freshservice.com",
        api_key="your_api_key"
    )

Usage as CLI::

    freshops agents list
    freshops tickets list --status open
"""

from freshops.__about__ import (
    __author__,
    __author_email__,
    __description__,
    __license__,
    __title__,
    __url__,
    __version__,
)
from freshops.client import FreshServiceClient
from freshops.config import (
    FreshServiceConfig,
    check_config,
    configure_logging,
    load_config,
)
from freshops.models import Agent, Agents
from freshops.exceptions import (
    EntityNotFoundError,
    FreshOpsError,
    InvalidEntityIdError,
    MissingReferenceError,
    MissingRequiredFieldError,
    RegistryClientNotInitializedError,
    RegistryError,
    ValidationError,
)

__all__ = [
    # Metadata
    "__author__",
    "__author_email__",
    "__description__",
    "__license__",
    "__title__",
    "__url__",
    "__version__",
    # Core classes
    "FreshServiceClient",
    "FreshServiceConfig",
    # Models
    "Agent",
    "Agents",
    # Config functions
    "load_config",
    "check_config",
    "configure_logging",
    # Exceptions
    "FreshOpsError",
    "ValidationError",
    "InvalidEntityIdError",
    "MissingRequiredFieldError",
    "RegistryError",
    "RegistryClientNotInitializedError",
    "EntityNotFoundError",
    "MissingReferenceError",
]
