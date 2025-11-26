"""
exceptions for shmlock module
"""

class ShmLockError(Exception):
    """
    base class for all exceptions in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)

class ShmLockRuntimeError(ShmLockError):
    """
    exception raised for runtime errors in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)

class ShmLockValueError(ValueError):
    """
    exception raised for value errors in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)

class ShmLockDanglingSharedMemoryError(ShmLockError):
    """
    exception raised for potentially dangling shared memory in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)

class ShmLockTimeoutError(ShmLockError):
    """
    exception raised for timeout errors in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)
