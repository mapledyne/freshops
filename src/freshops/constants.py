"""
Constants and magic numbers for FreshOps.

Loads constants from constants.toml file, providing a centralized location
for all magic numbers and configuration values used throughout the library.

Constants are organized by category and can be accessed via attributes:
    from freshops.constants import CACHE_MAX_LOAD, API_DEFAULT_PER_PAGE

All constants are loaded at module import time from constants.toml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# tomllib is in stdlib for Python 3.11+, use tomli for Python 3.10
try:
    import tomllib  # type: ignore[import-untyped]
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[import-untyped]
    except ImportError:
        raise ImportError(
            "tomllib (Python 3.11+) or tomli package required for loading constants.toml. "
            "Install with: pip install tomli"
        )

# Path to constants.toml file (in same directory as this module)
_CONSTANTS_FILE = Path(__file__).parent / "constants.toml"


def _load_constants() -> dict[str, dict[str, Any]]:
    """
    Load constants from constants.toml file.

    :returns: Dictionary of constants organized by category
    :raises FileNotFoundError: If constants.toml doesn't exist
    :raises tomllib.TOMLDecodeError: If constants.toml is invalid
    """
    if not _CONSTANTS_FILE.exists():
        raise FileNotFoundError(
            f"Constants file not found: {_CONSTANTS_FILE}. "
            "Please ensure constants.toml exists in the freshops package directory."
        )

    with _CONSTANTS_FILE.open("rb") as f:
        return tomllib.load(f)


# Load constants at module import time
_constants = _load_constants()

# -----------------------------------------------------------------------------
# Caching Constants
# -----------------------------------------------------------------------------

# Maximum number of items to load when populating a cache from a list API
CACHE_MAX_LOAD: int = _constants["caching"]["max_cache_load"]

# -----------------------------------------------------------------------------
# API Constants
# -----------------------------------------------------------------------------

# Default number of items per page for list API calls
API_DEFAULT_PER_PAGE: int = _constants["api"]["default_per_page"]

# Maximum number of items per page supported by FreshService API
API_MAX_PER_PAGE: int = _constants["api"]["max_per_page"]

# -----------------------------------------------------------------------------
# Datetime Constants
# -----------------------------------------------------------------------------

# Number of days to consider "recent" for relative datetime formatting
DATETIME_RECENT_DAYS_THRESHOLD: int = _constants["datetime"]["recent_days_threshold"]

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = [
    # Caching
    "CACHE_MAX_LOAD",
    # API
    "API_DEFAULT_PER_PAGE",
    "API_MAX_PER_PAGE",
    # Datetime
    "DATETIME_RECENT_DAYS_THRESHOLD",
]

