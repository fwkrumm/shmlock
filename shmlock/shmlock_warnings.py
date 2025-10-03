"""
Shmlock warnings module.

This module defines custom warning classes for the shmlock module,
providing specific warning types for different scenarios.
"""

import warnings


class ShmLockDanglingSharedMemoryWarning(ResourceWarning):
    """
    Warning for potentially dangling shared memory blocks.

    This warning is issued when shared memory blocks might be left in an
    inconsistent state due to process interruption, typically from KeyboardInterrupt.
    """


# Ensure the warning is always shown to the user
warnings.simplefilter("always", ShmLockDanglingSharedMemoryWarning)
