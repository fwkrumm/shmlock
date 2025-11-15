"""
shmlock warnings module
"""

import warnings

class ShmLockDanglingSharedMemoryWarning(ResourceWarning):
    # warning if shared memory block might be dangling due to KeyboardInterrupt
    pass

class ShmMemoryBarrierMissingWarning(UserWarning):
    # warning if memory barrier module is missing
    pass

# the warning should be always shown
warnings.simplefilter("always", ShmLockDanglingSharedMemoryWarning)
