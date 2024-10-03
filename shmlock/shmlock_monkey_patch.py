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
import os
import warnings
from multiprocessing import resource_tracker

def remove_shm_from_resource_tracker(pattern: str, print_warning: bool = True):
    # pylint: disable=all
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
    if os.name != "posix" and print_warning:
        warnings.warn("remove_shm_from_resource_tracker is (probably) "\
            "not necessary on non-posix systems", stacklevel=2)

    def fix_register(name: str, rtype):
        if pattern in name:
            return
        return resource_tracker._resource_tracker.register(name, rtype)
    resource_tracker.register = fix_register

    def fix_unregister(name: str, rtype):
        if pattern in name:
            return
        return resource_tracker._resource_tracker.unregister(name, rtype)
    resource_tracker.unregister = fix_unregister

    if not pattern and "shared_memory" in resource_tracker._CLEANUP_FUNCS:
        del resource_tracker._CLEANUP_FUNCS["shared_memory"]
