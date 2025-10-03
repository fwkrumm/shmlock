"""
ShmLock module - Inter-process lock implementation using shared memory.

The lock only requires a string name to work which is used to create a shared memory block.
It works from multiple consoles and ensures synchronized access to shared resources as long as
the uniqueness of the shared memory name is assured.

Example usage:
    # Create lock. Use any name which is not used by "non-lock" shared memory blocks
    lock = shmlock.ShmLock("shm_name")

    # Use either via context manager with timeout
    timeout = 1  # seconds; optional parameter

    with lock(timeout=timeout) as res:
        if res:
            # do something critical

    # Or use the lock method directly
    with lock.lock(timeout=timeout) as res:
        if res:
            # do something critical

NOTE on POSIX systems you might want to 'patch' the resource tracker to not track shared memory
resources of other processes. For details see the 'Troubleshooting' section of the README.md.

NOTE the lock should not be shared. Each process (and if you must thread) should use its
own instance of this lock. However for multithreading you should use the threading.Lock class.
"""

from shmlock.shmlock_main import ShmLock
from shmlock.shmlock_monkey_patch import remove_shm_from_resource_tracker
from shmlock.shmlock_base_logger import create_logger
import shmlock.shmlock_exceptions as exceptions

# Export main components
__all__ = ["ShmLock", "remove_shm_from_resource_tracker", "exceptions", "create_logger"]

# Do NOT alter the following line in any way EXCEPT changing
# the version number. No comments, no rename, whatsoever
__version__ = "4.2.4"
