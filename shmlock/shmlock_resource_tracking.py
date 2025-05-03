"""
custom and experimental resource tracking for shared memory locks and clean up functions
"""
import os
import sys
import threading
import multiprocessing
import signal
import atexit
import logging
import warnings
from multiprocessing import shared_memory
from weakref import WeakValueDictionary


from shmlock.shmlock_base_logger import ShmModuleBaseLogger

# for debug logs (if enabled)
PROCESS_NAME = multiprocessing.current_process().name

# for resource tracking (if enabled)
_RESOURCE_TRACKER = None

# if warnings should be printed
_ENABLE_WARNINGS = True


def enable_disable_warnings(enable_warnings: bool):
    """
    set warnings to True or False

    Parameters
    ----------
    enable_warnings : bool
        set warnings to True or False
    """
    global _ENABLE_WARNINGS # pylint: disable=(global-statement)
    _ENABLE_WARNINGS = enable_warnings

#
# Resource Tracking
#
class SingletonMeta(type):
    """
    based on https://github.com/nlm/python-singletonmeta/tree/master
    also without lock mechanism mentioned in
    https://stackoverflow.com/questions/6760685/what-is-the-best-way-of-implementing-singleton-in-python
    """
    _instances = WeakValueDictionary() # ensure that object is deleted if all references are gone
    _lock = threading.Lock()  # ensure thread-safety, only one instance per process

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]

class ResourceTrackerSingleton(ShmModuleBaseLogger,
                               metaclass=SingletonMeta):

    """
    singleton resource tracker class for shared memory tracking. Experimental.

    NOTE that only one tracker should run PER PROCESS.
    """

    def __init__(self, logger: logging.Logger = None):
        """
        init singleton class for resource tracking

        Parameters
        ----------
        logger : logging.Logger, optional
            specify a logger, by default None
        """
        ShmModuleBaseLogger.__init__(self, logger=logger)

        self._lock = threading.Lock() # to safely add/remove shm per process
        self._shared_memories: dict[int, list[str]] = None
        self._parent_pid: int = None # for inheritance check

        with self._lock:
            if self._shared_memories is None:
                self._shared_memories = {}
        self.info("Custom Resource Tracker initialized. Note that this feature is experimental.")

    def _shared_memories_current_pid(self):
        """
        returns the list of the shared memories by this process

        NOTE that if the fork method is used the pid might change after init
        and thus each tracker has to track shared memory for the correct pid.

        However, the resource tracker should not be shared among processes.

        NOTE do not use the self._lock here since this function is called within an acquired lock
            and would result in a deadlock.

        Returns
        -------
        list
            list of shared memory by this process
        """
        # first throw away all shared memory names from all other keys (pids) except the
        # current one. on non-posix systems this is not necessary since the fork method is not
        # supported. an alternative would be to prevent sharing via inheritance. However, this
        # might cause problems due to singleton nature.
        #with self._lock: # NOTE this function is locked by parent functions. DO NOT USE A LOCK
        # LOCK HERE SINCE IT RESULTS IN A DEADLOCK
        self._shared_memories = {os.getpid(): self._shared_memories.setdefault(os.getpid(),
                                                                                [])}
        return self._shared_memories[os.getpid()]

    def add_shared_memory(self, name: str):
        """
        add shm name to tracking list

        Parameters
        ----------
        name : str
            name of shm currently acquired by a lock in this process
        """
        with self._lock:
            if name in self._shared_memories_current_pid():
                raise RuntimeError(f"shm {name} already contained in "\
                                   f"{self._shared_memories} for pid {os.getpid()}")
            # setdefault called within _shared_memories_current_pid, before so key exists
            self._shared_memories[os.getpid()].append(name)
            self.debug("added shared memory %s to tracking list", name)

    def remove_shared_memory(self, name: str):
        """
        remove shm from tracking list

        Parameters
        ----------
        name : str
            shm name to remove

        Returns
        -------
        bool
            True, if shared memory name was removed from the list, False otherwise
        """
        with self._lock:
            if name not in self._shared_memories_current_pid():
                self.warning("name %s not contained in %s for pid %s. This might happen "\
                             "if the resource tracking was initialized while in a "\
                             "separate thread the lock was already acquired.",
                             name, self._shared_memories, os.getpid())
                return False
            # setdefault called within _shared_memories_current_pid, before so key exists
            self._shared_memories[os.getpid()].remove(name)
            self.debug("removed shared memory %s from tracking list", name)
        return True

    def clean_up(self):
        """
        clean up all shared memory.
        """
        with self._lock:

            if os.name != "posix" and len(self._shared_memories_current_pid()) > 0:
                self.warning("clean_up might not work properly on non-posix systems, "\
                             "especially unlinking! For non-posix systems you have to assure "\
                             "that all locks are released properly.")

            for shm_name in self._shared_memories_current_pid():
                self.warning("process %s was killed and shm might still be "\
                             "acquired. try releasing lock %s now ...",
                             PROCESS_NAME,
                             shm_name)
                try:
                    # try to release the shm of the corresponding lock
                    shm = shared_memory.SharedMemory(name=shm_name)
                    try:
                        # NOTE that on windows unlink() is not supported/has not effect
                        shm.close()
                        shm.unlink()
                        del shm
                        self.debug("closed/unlinked/del shared memory %s", shm_name)
                    except Exception as err: # pylint: disable=(broad-exception-caught)
                        self.exception("could not close/unlink/del shared memory: "\
                                     f"{shm_name} because of {err}", shm_name, err)
                except FileNotFoundError:
                    # this can happen during program exit if the shared memory has been
                    # closed/unlinked elsewhere. in that case i.e. if we do not find the shared
                    # memory -> only remove it from the list
                    pass
                except ValueError as err:
                    # possible on linux; shm block requires to be deleted manually
                    self.error("Error: %s", err)
                # setdefault called within _shared_memories_current_pid, before so key exists
                self._shared_memories[os.getpid()].remove(shm_name)
                self.debug("during clean up: removed shared memory %s from tracking list",
                           shm_name)

    @property
    def shared_memories(self):
        """
        return list of tracked shared memories

        Returns
        -------
        list
            list of tracked shared memory names
        """
        return self._shared_memories_current_pid()

    @property
    def shared_memories_dict(self):
        """
        return dict of tracked shared memories. This should only be
        used for debugging purposes. Usually the shared_memories dict
        should only contain one key, the pid of the process.
        However, for the fork method on posix systems, it might contain
        multiple pids since due to the fork method the existing
        shared memory dict is inherited.

        Returns
        -------
        dict
            dict of tracked shared memory names
            for all pids
        """
        return self._shared_memories

def add_to_resource_tracker(name: str):
    """
    add shm name to singleton list

    Parameters
    ----------
    name : str
        _description_
    """
    if _RESOURCE_TRACKER is not None:
        _RESOURCE_TRACKER.add_shared_memory(name)

def remove_from_resource_tracker(name: str) -> None | bool:
    """
    remove shm from singleton list

    Parameters
    ----------
    name : str
        _description_

    Returns
    -------
    None | bool
        None if resource tracker not initialized. True if removed, False if not found
    """
    if _RESOURCE_TRACKER is not None:
        return _RESOURCE_TRACKER.remove_shared_memory(name)
    return None

def is_resource_tracker_initialized() -> bool:
    """
    check if resource tracker is initialized

    Returns
    -------
    bool
        True if resource tracker is initialized, False otherwise
    """
    return _RESOURCE_TRACKER is not None

def get_registered_shared_memories() -> list | None:
    """
    get registered shared memories

    Returns
    -------
    list
        list of shared memories if resource tracker is initialized, None otherwise
    """
    if _RESOURCE_TRACKER is not None:
        return _RESOURCE_TRACKER.shared_memories
    return None

def de_init_custom_resource_tracking_without_clean_up():
    """
    de init custom resource tracking; no shm is released because a lock might use it

    use clean up function if the latter is desired
    """
    global _RESOURCE_TRACKER # pylint: disable=(global-statement)
    if _RESOURCE_TRACKER is not None:
        if len(_RESOURCE_TRACKER.shared_memories) > 0 and _ENABLE_WARNINGS:
            warnings.warn("You called de_init_custom_resource_tracking but there are "\
                          f"shm references tracked by resource tracker, namely "\
                          f"{_RESOURCE_TRACKER.shared_memories}. Tracking "\
                          "of them will not continue i.e. you have to assure that they are "\
                          "released properly.", stacklevel=2)
        # if all references are gone, due to wekref, the object will be deleted
        _RESOURCE_TRACKER = None

def de_init_custom_resource_tracking():
    """
    clean up function to release lock if process is killed

    NOTE that this also calls de_init_custom_resource_tracking()
    """
    if _RESOURCE_TRACKER is not None:
        _RESOURCE_TRACKER.clean_up()
        de_init_custom_resource_tracking_without_clean_up()

def _handle_signal(signum, _): # signum, frame
    """
    handle signal to release lock if process is killed
    """
    de_init_custom_resource_tracking()
    if signum == signal.SIGINT:
        # to keep console alive if user spams ctrl+c
        raise KeyboardInterrupt
    sys.exit(signum)

def init_custom_resource_tracking(add_final_clean_up: bool = True,
                                  logger: logging.Logger = None):
    """
    init custom resource tracking. Beware that the signal.signal calls below affect how
    ctrl+c is handled within the console. If you want to handle clean up yourself just set
    add_final_clean_up to False and call clean_up() yourself at program exit

    if you want to reset it yourself for some reason, use:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        atexit.unregister(clean_up)

    Parameters
    ----------
    add_final_clean_up : bool, optional
        bool to initialize final clean up on program kill or exit. Uses
        signal and atexit, by default True
    logger: logging.Logger, optional
        specify a logger for resource tracker if desired, by default None
    """
    if _ENABLE_WARNINGS:
        warnings.warn("Note that this feature of custom resource tracking is experimental. "\
                      "You can disable all warnings via "\
                      "shmlock.enable_disable_warnings(False).",
                      stacklevel=2)

    global _RESOURCE_TRACKER # pylint: disable=(global-statement)
    _RESOURCE_TRACKER = ResourceTrackerSingleton(logger)

    # set clean up for program kill or exit
    if add_final_clean_up:
        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)
        atexit.register(de_init_custom_resource_tracking)
