"""
uuid class of shared memory lock.
"""
import uuid

class ShmUuid:
    """
    data class to store the uuid of the lock
    """

    def __init__(self):
        self.uuid_ = uuid.uuid4()
        self.uuid_bytes = self.uuid_.bytes
        self.uuid_str = str(self.uuid_)

    def __repr__(self):
        return f"ShmUuid(uuid={self.uuid_})"

    @staticmethod
    def byte_to_string(byte_repr: bytes) -> str:
        """
        convert byte representation of uuid to string representation

        Parameters
        ----------
        byte_repr : bytes
            byte representation of uuid

        Returns
        -------
        str
            string representation of uuid
        """
        return str(uuid.UUID(bytes=byte_repr))

    @staticmethod
    def string_to_bytes(uuid_str: str) -> bytes:
        """
        convert string representation of uuid to byte representation

        Parameters
        ----------
        uuid_str : str
            string representation of uuid

        Returns
        -------
        bytes
            byte representation of uuid
        """
        return uuid.UUID(uuid_str).bytes

    def __str__(self):
        """
        string representation of the uuid

        Returns
        -------
        str
            string representation of the uuid
        """
        return self.uuid_str
