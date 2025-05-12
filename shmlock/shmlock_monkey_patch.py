"""
Monkey-patch multiprocessing.resource_tracker so SharedMemory won't be tracked

patch from Álvaro Justen (turicas) at
https://bugs.python.org/issue38119

the main problem is seemingly that the resource_tracker also tracks the shared memory
if it is created by another process and so it results in a warning if the resource
tracker tries to release the "leaking" memory which is unlinked by another process.

For further reading also see
https://github.com/vllm-project/vllm/issues/5468
https://github.com/vllm-project/vllm/pull/5512
"""
import sys
import os
import warnings
import threading
from multiprocessing import resource_tracker


# create list to store all patterns so that the monkey patch can be used multiple times
_PATTERN_LIST = []
# use a locks to make the monkey patch thread-safe. NOTE that each process does have its own
# resource_tracker instance so we do not need to lock across processes
_THREADING_LOCK = threading.RLock()

def remove_shm_from_resource_tracker(pattern: str, print_warning: bool = True):
    """
    Monkey-patch multiprocessing.resource_tracker so SharedMemory will not be tracked

    More details at: https://bugs.python.org/issue38119
        (forwarded from https://bugs.python.org/issue39959)
    at comment
    Author: Álvaro Justen (turicas) 	Datum: 2021-03-08 19:22

    originally found at
    https://stackoverflow.com/questions/62748654/
        python-3-8-shared-memory-resource-tracker-producing-unexpected-warnings-at-appli

    Parameters
    ----------
    pattern : str
        pattern to filter out shared memory tracking. If empty, all shared memory tracking
        will be disabled.

        So for example for pattern == "shm_lock", all shared memory tracking for shared
        memory names containing "shm_lock" will be disabled. You can use this if you still
        want to use the native resource tracker but do not want to see the warnings/KeyErrors
        of the resource tracker concerning allegedly "leaking" shared memory.

        If you set pattern == "", all shared memory tracking will be disabled and you will not
        see any warnings from it. NOTE that this also increases performance on posix systems
        since the un-registering of the shared memory does not happen any longer
    print_warning : bool, optional
        whether to print warnings if the function is called on non-posix systems, default is True
    """

    if sys.version_info >= (3, 13):
        raise RuntimeError("In python 3.13 and above shared memory blocks contain the ''track'' "\
                           "parameter which can also be used in the ShmLock object. Use "\
                           "ShmLock(..., track=false) so that shared memory block will not "\
                           "be tracked.")

    if not isinstance(pattern, str):
        raise ValueError("pattern must be a string")

    if os.name != "posix" and print_warning:
        warnings.warn("remove_shm_from_resource_tracker is (probably) "\
                      "not necessary on non-posix systems", stacklevel=2)

    if not pattern and print_warning:
        warnings.warn("empty pattern used in function remove_shm_from_resource_tracker. "\
                      "This will remove the cleanup function for shared memory. "\
                      "This can lead to memory leaks if shared memory is not unlinked manually. "\
                      "Use with caution", stacklevel=2)

    # NOTE that this function is not process-safe. This is because each proces should have its
    # on resource tracker instance. A check has yet to be implemented
    with _THREADING_LOCK:
        _PATTERN_LIST.append(pattern)

        def fix_register(name: str, rtype):
            # check if pattern contained in any of the elements within _PATTERN_LIST
            if any(pattern in name for pattern in _PATTERN_LIST):
                return None
            return resource_tracker._resource_tracker.register(name, rtype) # pylint: disable=protected-access
        resource_tracker.register = fix_register

        def fix_unregister(name: str, rtype):
            # check if pattern contained in any of the elements within _PATTERN_LIST
            if any(pattern in name for pattern in _PATTERN_LIST):
                return None
            return resource_tracker._resource_tracker.unregister(name, rtype) # pylint: disable=protected-access
        resource_tracker.unregister = fix_unregister

        # if pattern == "", we completely remove the cleanup function for shared memory
        if not pattern and "shared_memory" in resource_tracker._CLEANUP_FUNCS: # pylint: disable=protected-access
            del resource_tracker._CLEANUP_FUNCS["shared_memory"] # pylint: disable=protected-access
