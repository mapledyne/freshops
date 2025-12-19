"""
Custom exceptions for FreshOps.

Simplified version with minimal boilerplate.
"""

from __future__ import annotations


class FreshOpsError(Exception):
    """Base exception for all FreshOps errors."""
    pass


class ValidationError(FreshOpsError, ValueError):
    """Raised when data validation fails."""
    pass


class InvalidEntityIdError(ValidationError):
    """Raised when an entity ID is invalid (missing, zero, or negative)."""
    def __init__(self, entity_type: str, entity_id: int | None) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"Invalid {entity_type} ID: {entity_id}")


class MissingRequiredFieldError(ValidationError):
    """Raised when a required field is missing or empty."""
    def __init__(self, entity_type: str, field_name: str) -> None:
        self.entity_type = entity_type
        self.field_name = field_name
        super().__init__(f"{entity_type} requires {field_name}")


class RegistryError(FreshOpsError, ValueError):
    """Base exception for registry-related errors."""
    pass


class RegistryClientNotInitializedError(RegistryError):
    """Raised when a registry operation requires a client but none is set."""
    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        super().__init__(
            f"{collection_name} registry client not initialized. "
            f"Call {collection_name}.set_client(client) first."
        )


class EntityNotFoundError(RegistryError):
    """Raised when an entity cannot be found in the registry or via API."""
    def __init__(self, entity_name: str, entity_id: int) -> None:
        self.entity_name = entity_name
        self.entity_id = entity_id
        super().__init__(f"{entity_name.capitalize()} {entity_id} not found")


class MissingReferenceError(RegistryError):
    """Raised when a lazy-loaded reference cannot be resolved."""
    def __init__(
        self,
        source_entity_type: str,
        source_entity_id: int,
        reference_type: str,
        reference_id: int,
    ) -> None:
        self.source_entity_type = source_entity_type
        self.source_entity_id = source_entity_id
        self.reference_type = reference_type
        self.reference_id = reference_id
        super().__init__(
            f"{source_entity_type} {source_entity_id} references "
            f"{reference_type} {reference_id} which does not exist"
        )

