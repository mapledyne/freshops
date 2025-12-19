"""
Configuration management for FreshOps.

Handles loading credentials and settings from environment variables
and optional .env files.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Environment variable names
ENV_DOMAIN = "FRESHSERVICE_DOMAIN"
ENV_API_KEY = "FRESHSERVICE_API_KEY"
ENV_LOG_LEVEL = "FRESHOPS_LOG_LEVEL"

# Track if logging has been configured to avoid duplicate handlers
_logging_configured = False


@dataclass
class FreshServiceConfig:
    """
    Configuration container for FreshService API connection.

    :ivar domain: The FreshService domain (e.g., 'company.freshservice.com')
    :ivar api_key: The API key for authentication
    :ivar log_level: Logging verbosity level
    """

    domain: str
    api_key: str
    log_level: str = "INFO"


def configure_logging(level: str = "INFO") -> None:
    """
    Configure loguru logging for the application.

    Sets up loguru with appropriate format and level for CLI output.
    Removes the default handler and adds a custom one with cleaner formatting.

    :param level: The logging level (DEBUG, INFO, WARNING, ERROR)

    Example::

        configure_logging("DEBUG")
        logger.debug("Detailed logging enabled")
    """
    global _logging_configured

    if _logging_configured:
        return

    # Remove default handler
    logger.remove()

    # Define format based on level
    if level == "DEBUG":
        # Detailed format for debugging
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
    else:
        # Clean format for normal usage
        log_format = "<level>{level: <8}</level> | <level>{message}</level>"

    # Add stderr handler with custom format
    logger.add(
        sys.stderr,
        format=log_format,
        level=level,
        colorize=True,
    )

    _logging_configured = True
    logger.debug(f"Logging configured at {level} level")


def get_api_key_from_env() -> str | None:
    """
    Retrieve the API key from environment variables.

    Checks for FRESHSERVICE_API_KEY in the environment.

    :returns: The API key if found, None otherwise
    """
    return os.environ.get(ENV_API_KEY)


def get_domain_from_env() -> str | None:
    """
    Retrieve the FreshService domain from environment variables.

    Checks for FRESHSERVICE_DOMAIN in the environment.

    :returns: The domain if found, None otherwise
    """
    return os.environ.get(ENV_DOMAIN)


def load_config() -> FreshServiceConfig:
    """
    Load configuration from environment variables.

    Attempts to load from a .env file first, then reads required
    environment variables for FreshService API access.

    :returns: A populated FreshServiceConfig instance

    Example::

        config = load_config()
        print(config.domain)
    """
    # Try to load .env file from current directory or parent directories
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug(f"Loaded environment from {env_path.absolute()}")
    else:
        # Still call load_dotenv to check default locations
        load_dotenv()

    domain = get_domain_from_env()
    api_key = get_api_key_from_env()
    log_level = os.environ.get(ENV_LOG_LEVEL, "INFO").upper()

    # Validation happens in check_config(), not here
    # This allows partial configs for --help, --version, etc.
    return FreshServiceConfig(
        domain=domain or "",
        api_key=api_key or "",
        log_level=log_level,
    )


def check_config(config: FreshServiceConfig) -> tuple[bool, list[str]]:
    """
    Validate that required configuration is present and valid.

    :param config: The configuration to validate
    :returns: Tuple of (is_valid, list of error messages)
    """
    errors = []

    if not config.domain:
        errors.append(f"Missing {ENV_DOMAIN}")
    elif "." in config.domain:
        errors.append(
            f"Invalid {ENV_DOMAIN}: '{config.domain}' - "
            "use just the company name (e.g., 'mycompany' "
            "not 'mycompany.freshservice.com')"
        )

    if not config.api_key:
        errors.append(f"Missing {ENV_API_KEY}")

    return (len(errors) == 0, errors)


def get_config_help() -> str:
    """
    Get help text for configuring the application.

    :returns: Formatted help string explaining how to set up credentials
    """
    return f"""
Configuration Required
======================

FreshOps requires FreshService API credentials to be set.

Option 1: Environment Variables
-------------------------------
Set the following environment variables:

    set {ENV_DOMAIN}=yourcompany
    set {ENV_API_KEY}=your_api_key_here

Option 2: .env File
-------------------
Create a .env file in your working directory:

    {ENV_DOMAIN}=yourcompany
    {ENV_API_KEY}=your_api_key_here

NOTE: Use just the company name for the domain, not the full URL.
      Example: 'evergreen' (not 'evergreen.freshservice.com')

Getting Your API Key
--------------------
1. Log in to your FreshService instance
2. Click your profile icon -> Profile Settings
3. Find "Your API Key" on the right side
4. Copy the key (you may need to click "View" first)

Example .env file is provided: .env.example
"""
