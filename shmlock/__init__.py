"""
__init__.py of ShmLock module.
The lock does solely require a string name to work which is used to create a shared memory block.
It works from multiple consoles and assures synchronized access to shared resources as long as
the uniqueness of the shared memory name is assured.

# create lock. Use any name which is not used by "non-lock" shared memory blocks
lock = shmlock.ShmLock("shm_name")

# Use either via
timeout = 1 # seconds; optional parameter

with lock(timeout=timeout) as res:
    if res:
        # do something

or

with lock.lock(timeout=timeout) as res:
    if res:
        # do something


NOTE on posix systems you might want to ''patch'' the resource tracker to not track shared memory
resources of other processes. For details see the ''Troubleshooting'' section of the README.md.

NOTE the lock should not be shared. Each process (and if you must thread) should use its
own instance of this lock. However for multithreading you should use the threading.Lock class.

"""

from shmlock.shmlock_main import *

# do NOT alter the following line in any way EXCEPT changing
# the version number. no comments, no rename, whatsoever
__version__ = "4.0.2"
