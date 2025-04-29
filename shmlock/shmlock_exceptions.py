"""
exceptions for shmlock module
"""

class ShmlockError(Exception):
    """
    base class for all exceptions in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)

class ShmLockRuntimeError(ShmlockError):
    """
    exception raised for runtime errors in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)

class ShmLockValueError(ValueError):
    """
    exception raised for value errors in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)

class ShmLockDanglingSharedMemoryError(ShmlockError):
    """
    exception raised for potentially dangling shared memory in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)

class ShmLockTimeoutError(ShmlockError):
    """
    exception raised for timeout errors in the shmlock module.
    """
    pass # pylint: disable=(unnecessary-pass)
