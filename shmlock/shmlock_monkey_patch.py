"""
Monkey-patch multiprocessing.resource_tracker so SharedMemory won't be tracked.

Patch from Álvaro Justen (turicas) at https://bugs.python.org/issue38119

The main problem is seemingly that the resource_tracker also tracks the shared memory
if it is created by another process and so it results in a warning if the resource
tracker tries to release the "leaking" memory which is unlinked by another process.

For further reading also see:
- https://github.com/vllm-project/vllm/issues/5468
- https://github.com/vllm-project/vllm/pull/5512
"""
import sys
import os
import warnings
import threading
from typing import List, Optional, Any
from multiprocessing import resource_tracker


# Create list to store all patterns so that the monkey patch can be used multiple times
_PATTERN_LIST: List[str] = []
# Use a lock to make the monkey patch thread-safe. NOTE that each process does have its own
# resource_tracker instance so we do not need to lock across processes
_THREADING_LOCK = threading.RLock()


def remove_shm_from_resource_tracker(pattern: str, print_warning: bool = True) -> None:
    """
    Monkey-patch multiprocessing.resource_tracker so SharedMemory will not be tracked.

    More details at: https://bugs.python.org/issue38119
    (forwarded from https://bugs.python.org/issue39959)
    at comment by Author: Álvaro Justen (turicas) Date: 2021-03-08 19:22

    Originally found at:
    https://stackoverflow.com/questions/62748654/
    python-3-8-shared-memory-resource-tracker-producing-unexpected-warnings-at-appli

    Parameters
    ----------
    pattern : str
        Pattern to filter out shared memory tracking. If empty, all shared memory tracking
        will be disabled.

        For example, for pattern == "shm_lock", all shared memory tracking for shared
        memory names containing "shm_lock" will be disabled. You can use this if you still
        want to use the native resource tracker but do not want to see the warnings/KeyErrors
        of the resource tracker concerning allegedly "leaking" shared memory.

        If you set pattern == "", all shared memory tracking will be disabled and you will not
        see any warnings from it. NOTE that this also increases performance on posix systems
        since the un-registering of the shared memory does not happen any longer.
        
    print_warning : bool, optional
        Whether to print warnings if the function is called on non-posix systems, by default True
        
    Raises
    ------
    RuntimeError
        If called on Python 3.13+ where the track parameter should be used instead
    ValueError
        If pattern is not a string
    """
    if sys.version_info >= (3, 13):
        raise RuntimeError(
            "In Python 3.13 and above shared memory blocks contain the 'track' "
            "parameter which can also be used in the ShmLock object. Use "
            "ShmLock(..., track=False) so that shared memory block will not "
            "be tracked."
        )

    if not isinstance(pattern, str):
        raise ValueError("pattern must be a string")

    if os.name != "posix" and print_warning:
        warnings.warn(
            "remove_shm_from_resource_tracker is (probably) "
            "not necessary on non-posix systems",
            UserWarning,
            stacklevel=2
        )

    if not pattern and print_warning:
        warnings.warn(
            "Empty pattern used in function remove_shm_from_resource_tracker. "
            "This will remove the cleanup function for shared memory. "
            "This can lead to memory leaks if shared memory is not unlinked manually. "
            "Use with caution",
            UserWarning,
            stacklevel=2
        )

    # NOTE that this function is not process-safe. This is because each process should have its
    # own resource tracker instance. A check has yet to be implemented
    with _THREADING_LOCK:
        _PATTERN_LIST.append(pattern)

        def fix_register(name: str, rtype: str) -> Optional[Any]:
            """
            Patched register function that filters out shared memory based on patterns.
            
            Parameters
            ----------
            name : str
                Resource name
            rtype : str
                Resource type
                
            Returns
            -------
            Optional[Any]
                Result of original register call or None if filtered
            """
            # Check if pattern contained in any of the elements within _PATTERN_LIST
            if any(pattern in name for pattern in _PATTERN_LIST):
                return None
            return resource_tracker._resource_tracker.register(name, rtype)  # pylint: disable=protected-access

        resource_tracker.register = fix_register

        def fix_unregister(name: str, rtype: str) -> Optional[Any]:
            """
            Patched unregister function that filters out shared memory based on patterns.
            
            Parameters
            ----------
            name : str
                Resource name
            rtype : str
                Resource type
                
            Returns
            -------
            Optional[Any]
                Result of original unregister call or None if filtered
            """
            # Check if pattern contained in any of the elements within _PATTERN_LIST
            if any(pattern in name for pattern in _PATTERN_LIST):
                return None
            return resource_tracker._resource_tracker.unregister(name, rtype)  # pylint: disable=protected-access

        resource_tracker.unregister = fix_unregister

        # If pattern == "", we completely remove the cleanup function for shared memory
        if not pattern and "shared_memory" in resource_tracker._CLEANUP_FUNCS:  # pylint: disable=protected-access
            del resource_tracker._CLEANUP_FUNCS["shared_memory"]  # pylint: disable=protected-access
