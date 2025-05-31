"""
shmlock warnings module
"""

import warnings

class ShmLockDanglingSharedMemoryWarning(ResourceWarning):
    # for warning if shared memory block might be dangling due to KeyboardInterrupt
    pass

# the warning should be always shown
warnings.simplefilter("always", ShmLockDanglingSharedMemoryWarning)
