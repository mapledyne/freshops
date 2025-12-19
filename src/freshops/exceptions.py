"""
Custom exceptions for FreshOps.

Provides domain-specific exceptions that follow Python best practices,
keeping error messages concise while providing detailed context through
exception attributes.
"""

from __future__ import annotations


class FreshOpsError(Exception):
    """
    Base exception for all FreshOps errors.

    All custom exceptions should inherit from this base class.
    """

    pass


class ValidationError(FreshOpsError, ValueError):
    """
    Raised when data validation fails.

    Used for invalid IDs, missing required fields, type mismatches, etc.
    """

    pass


class InvalidEntityIdError(ValidationError):
    """
    Raised when an entity ID is invalid (missing, zero, or negative).

    :ivar entity_type: The type/name of the entity (e.g., "Agent", "Location")
    :ivar entity_id: The invalid ID value
    """

    def __init__(self, entity_type: str, entity_id: int | None) -> None:
        """
        Initialize InvalidEntityIdError.

        :param entity_type: The type/name of the entity
        :param entity_id: The invalid ID value
        """
        self.entity_type = entity_type
        self.entity_id = entity_id
        message = f"Invalid {entity_type} ID: {entity_id}"
        super().__init__(message)


class MissingRequiredFieldError(ValidationError):
    """
    Raised when a required field is missing or empty.

    :ivar entity_type: The type/name of the entity
    :ivar field_name: The name of the missing field
    """

    def __init__(self, entity_type: str, field_name: str) -> None:
        """
        Initialize MissingRequiredFieldError.

        :param entity_type: The type/name of the entity
        :param field_name: The name of the missing field
        """
        self.entity_type = entity_type
        self.field_name = field_name
        message = f"{entity_type} requires {field_name}"
        super().__init__(message)


class RegistryError(FreshOpsError, ValueError):
    """
    Base exception for registry-related errors.

    Used for client initialization, entity lookup failures, etc.
    """

    pass


class RegistryClientNotInitializedError(RegistryError):
    """
    Raised when a registry operation requires a client but none is set.

    :ivar collection_name: The name of the collection class (e.g., "Agents", "Groups")
    """

    def __init__(self, collection_name: str) -> None:
        """
        Initialize RegistryClientNotInitializedError.

        :param collection_name: The name of the collection class
        """
        self.collection_name = collection_name
        message = (
            f"{collection_name} registry client not initialized. "
            f"Call {collection_name}.set_client(client) first."
        )
        super().__init__(message)


class EntityNotFoundError(RegistryError):
    """
    Raised when an entity cannot be found in the registry or via API.

    :ivar entity_name: The name of the entity type (e.g., "agent", "location")
    :ivar entity_id: The ID that was not found
    """

    def __init__(self, entity_name: str, entity_id: int) -> None:
        """
        Initialize EntityNotFoundError.

        :param entity_name: The name of the entity type (singular, lowercase)
        :param entity_id: The ID that was not found
        """
        self.entity_name = entity_name
        self.entity_id = entity_id
        # Capitalize for display: "agent" -> "Agent"
        display_name = entity_name.capitalize()
        message = f"{display_name} {entity_id} not found"
        super().__init__(message)


class MissingReferenceError(RegistryError):
    """
    Raised when a lazy-loaded reference cannot be resolved.

    This is a more specific error than EntityNotFoundError, used when
    an entity references another entity that doesn't exist (e.g., agent
    references a deleted group).

    :ivar source_entity_type: The type of the entity making the reference
    :ivar source_entity_id: The ID of the entity making the reference
    :ivar reference_type: The type of the referenced entity
    :ivar reference_id: The ID of the referenced entity that was not found
    """

    def __init__(
        self,
        source_entity_type: str,
        source_entity_id: int,
        reference_type: str,
        reference_id: int,
    ) -> None:
        """
        Initialize MissingReferenceError.

        :param source_entity_type: The type of the entity making the reference
        :param source_entity_id: The ID of the entity making the reference
        :param reference_type: The type of the referenced entity
        :param reference_id: The ID of the referenced entity that was not found
        """
        self.source_entity_type = source_entity_type
        self.source_entity_id = source_entity_id
        self.reference_type = reference_type
        self.reference_id = reference_id
        message = (
            f"{source_entity_type} {source_entity_id} references "
            f"{reference_type} {reference_id} which does not exist"
        )
        super().__init__(message)

