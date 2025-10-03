"""
Exceptions for shmlock module.

This module defines custom exception classes for the shmlock module,
providing specific error types for different failure scenarios.
"""

from typing import Optional


class ShmlockError(Exception):
    """
    Base class for all exceptions in the shmlock module.
    
    This serves as the root exception class for all shmlock-specific errors,
    allowing for easy catching of any shmlock-related exception.
    """

    def __init__(self, message: str, *args: object) -> None:
        """
        Initialize the ShmlockError.
        
        Parameters
        ----------
        message : str
            The error message
        *args : object
            Additional arguments to pass to the base Exception class
        """
        super().__init__(message, *args)


class ShmLockRuntimeError(ShmlockError, RuntimeError):
    """
    Exception raised for runtime errors in the shmlock module.
    
    This exception is raised when an operation fails due to runtime conditions,
    such as attempting to use a lock created in a different process.
    """


class ShmLockValueError(ShmlockError, ValueError):
    """
    Exception raised for value errors in the shmlock module.
    
    This exception is raised when invalid parameters are passed to shmlock functions,
    such as negative timeout values or empty lock names.
    """


class ShmLockDanglingSharedMemoryError(ShmlockError):
    """
    Exception raised for potentially dangling shared memory in the shmlock module.
    
    This exception is raised when shared memory blocks appear to be in an inconsistent
    state, typically after process interruption during lock acquisition.
    """


class ShmLockTimeoutError(ShmlockError):
    """
    Exception raised for timeout errors in the shmlock module.
    
    This exception is raised when lock acquisition fails due to timeout,
    indicating that the lock could not be acquired within the specified time limit.
    """
