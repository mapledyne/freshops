"""
Tests for configuration management.

These tests verify that configuration loading and logging setup
work correctly.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from freshops import (
    FreshServiceConfig,
    check_config,
    configure_logging,
    load_config,
)
from freshops.config import (
    get_api_key_from_env,
    get_domain_from_env,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_from_env_vars(self) -> None:
        """Verify config loads from environment variables."""
        env = {
            "FRESHSERVICE_DOMAIN": "test.freshservice.com",
            "FRESHSERVICE_API_KEY": "test_key_123",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_config()
            assert config.domain == "test.freshservice.com"
            assert config.api_key == "test_key_123"

    def test_load_config_returns_empty_when_missing(self) -> None:
        """Verify load_config returns empty strings when vars missing."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear any .env loading
            with patch("freshops.config.load_dotenv"):
                config = load_config()
                assert config.domain == ""
                assert config.api_key == ""


class TestCheckConfig:
    """Tests for check_config function."""

    def test_check_config_valid(self) -> None:
        """Verify check_config passes with valid config."""
        config = FreshServiceConfig(
            domain="mycompany",
            api_key="test_key",
        )
        is_valid, errors = check_config(config)
        assert is_valid is True
        assert errors == []

    def test_check_config_missing_domain(self) -> None:
        """Verify check_config fails when domain is missing."""
        config = FreshServiceConfig(
            domain="",
            api_key="test_key",
        )
        is_valid, errors = check_config(config)
        assert is_valid is False
        assert any("FRESHSERVICE_DOMAIN" in e for e in errors)

    def test_check_config_invalid_domain_with_dots(self) -> None:
        """Verify check_config fails when domain contains periods."""
        config = FreshServiceConfig(
            domain="mycompany.freshservice.com",
            api_key="test_key",
        )
        is_valid, errors = check_config(config)
        assert is_valid is False
        assert any("use just the company name" in e for e in errors)

    def test_check_config_missing_api_key(self) -> None:
        """Verify check_config fails when API key is missing."""
        config = FreshServiceConfig(
            domain="mycompany",
            api_key="",
        )
        is_valid, errors = check_config(config)
        assert is_valid is False
        assert any("FRESHSERVICE_API_KEY" in e for e in errors)

    def test_check_config_missing_both(self) -> None:
        """Verify check_config fails when both are missing."""
        config = FreshServiceConfig(
            domain="",
            api_key="",
        )
        is_valid, errors = check_config(config)
        assert is_valid is False
        assert len(errors) == 2


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_logging_default_level(self) -> None:
        """Verify default logging level is INFO."""
        # Just verify it doesn't raise
        configure_logging("INFO")

    def test_configure_logging_debug_level(self) -> None:
        """Verify DEBUG level can be set."""
        configure_logging("DEBUG")


class TestGetApiKeyFromEnv:
    """Tests for get_api_key_from_env function."""

    def test_returns_key_when_present(self) -> None:
        """Verify API key is returned when set."""
        with patch.dict(os.environ, {"FRESHSERVICE_API_KEY": "my_key"}):
            result = get_api_key_from_env()
            assert result == "my_key"

    def test_returns_none_when_missing(self) -> None:
        """Verify None is returned when key is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_api_key_from_env()
            assert result is None


class TestGetDomainFromEnv:
    """Tests for get_domain_from_env function."""

    def test_returns_domain_when_present(self) -> None:
        """Verify domain is returned when set."""
        with patch.dict(os.environ, {"FRESHSERVICE_DOMAIN": "test.freshservice.com"}):
            result = get_domain_from_env()
            assert result == "test.freshservice.com"

    def test_returns_none_when_missing(self) -> None:
        """Verify None is returned when domain is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_domain_from_env()
            assert result is None
