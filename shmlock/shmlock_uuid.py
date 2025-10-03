"""
UUID class for shared memory lock.

This module provides UUID generation and manipulation functionality
for unique identification of shared memory locks.
"""

import uuid


class ShmUuid:
    """
    Data class to store and manage the UUID of the lock.

    This class encapsulates UUID generation and provides convenient
    access to both byte and string representations of the UUID.
    """

    def __init__(self) -> None:
        """
        Initialize a new ShmUuid instance with a random UUID4.
        """
        self.uuid_: uuid.UUID = uuid.uuid4()
        self.uuid_bytes: bytes = self.uuid_.bytes
        self.uuid_str: str = str(self.uuid_)

    def __repr__(self) -> str:
        """
        Return a string representation of the ShmUuid instance.

        Returns
        -------
        str
            String representation showing the UUID value
        """
        return f"ShmUuid(uuid={self.uuid_})"

    def __str__(self) -> str:
        """
        Return the string representation of the UUID.

        Returns
        -------
        str
            String representation of the UUID
        """
        return self.uuid_str

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another ShmUuid instance.

        Parameters
        ----------
        other : object
            Object to compare with

        Returns
        -------
        bool
            True if UUIDs are equal, False otherwise
        """
        if not isinstance(other, ShmUuid):
            return NotImplemented
        return self.uuid_ == other.uuid_

    def __hash__(self) -> int:
        """
        Return hash of the UUID for use in sets/dicts.

        Returns
        -------
        int
            Hash value of the UUID
        """
        return hash(self.uuid_)

    @staticmethod
    def byte_to_string(byte_repr: bytes) -> str:
        """
        Convert byte representation of UUID to string representation.

        Parameters
        ----------
        byte_repr : bytes
            Byte representation of UUID

        Returns
        -------
        str
            String representation of UUID

        Raises
        ------
        ValueError
            If byte_repr is not a valid UUID byte representation
        """
        try:
            return str(uuid.UUID(bytes=byte_repr))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid UUID byte representation: {byte_repr!r}") from e

    @staticmethod
    def string_to_bytes(uuid_str: str) -> bytes:
        """
        Convert string representation of UUID to byte representation.

        Parameters
        ----------
        uuid_str : str
            String representation of UUID

        Returns
        -------
        bytes
            Byte representation of UUID

        Raises
        ------
        ValueError
            If uuid_str is not a valid UUID string
        """
        try:
            return uuid.UUID(uuid_str).bytes
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid UUID string representation: {uuid_str!r}") from e
