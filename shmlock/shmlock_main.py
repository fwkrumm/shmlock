"""
main class of shared memory lock.
"""
import time
import multiprocessing
import multiprocessing.synchronize
from multiprocessing import shared_memory
from multiprocessing import Event
from contextlib import contextmanager
import logging

__all__ = ["ShmLock",
           "remove_shm_from_resource_tracker",
           "init_custom_resource_tracking",
           "de_init_custom_resource_tracking",
           "de_init_custom_resource_tracking_without_clean_up",
           "enable_disable_warnings"
           ]

# reveal functions for resource tracking adjustments
from shmlock.shmlock_monkey_patch import remove_shm_from_resource_tracker
from shmlock.shmlock_resource_tracking import init_custom_resource_tracking
from shmlock.shmlock_resource_tracking import de_init_custom_resource_tracking
from shmlock.shmlock_resource_tracking import de_init_custom_resource_tracking_without_clean_up
from shmlock.shmlock_resource_tracking import add_to_resource_tracker
from shmlock.shmlock_resource_tracking import remove_from_resource_tracker
from shmlock.shmlock_resource_tracking import enable_disable_warnings
from shmlock.shmlock_resource_tracking import PROCESS_NAME

from shmlock.shmlock_base_logger import ShmModuleBaseLogger

class ShmLock(ShmModuleBaseLogger):

    """
    lock class using shared memory to synchronize shared resources access
    """

    def __init__(self,
                 lock_name: str,
                 poll_interval: float = 0.05,
                 logger: logging.Logger = None,
                 exit_event: multiprocessing.synchronize.Event = None):
        """
        default init. set shared memory name (for lock) and poll_interval.
        the latter is used to check if lock is available every poll_interval seconds

        Parameters
        ----------
        lock_name : str
            name of the lock i.e. the shared memory block
        poll_interval : float, optional
            time delay in seconds after a failed acquire try after which it will be tried
            again to acquire the lock, by default 0.05s (50ms)
        logger : logging.Logger, optional
            a logger, this class only logs at debug level which process tried to acquire,
            which succeeded etc., by default None
        exit_event : multiprocessing.synchronize.Event, optional
            if None is provided a new one will be initialized. if event is set to true
            -> acquirement will stop and it will not be possible to acquire a lock until event is
            unset/cleared, by default None
        """
        self._shm = None # make sure to initialize _shm at the beginning since otherwise
                         # an AttributeError might occur during destructor if init does not
                         # succeed

        super().__init__(logger=logger)

        # type checks
        if not isinstance(poll_interval, float) or poll_interval < 0:
            raise ValueError("poll_interval must be a float and > 0")
        if not isinstance(lock_name, str):
            raise ValueError("lock_name must be a string")
        if exit_event is not None and \
            not isinstance(exit_event, multiprocessing.synchronize.Event):
            raise ValueError("exit_event must be a multiprocessing.Event")

        self._name = lock_name
        self._poll_interval = poll_interval
        self._timeout = None # for __call__
        self._throw = False # for __call__
        self._exit_event = exit_event if exit_event is not None else Event()

    @contextmanager
    def lock(self, timeout: float = None, throw: bool = False):
        """
        lock method to be used as context manager

        Parameters
        ----------
        timeout : float, optional
            max timeout in seconds until lock acquirement is aborted, by default None
        throw : bool, optional
            set to True if exception is supposed to be raised after
            acquirement fails, by default False

        Yields
        ------
        bool
            True if lock acquired, False otherwise

        Raises
        ------
        TimeoutError
            if throw is True and lock acquirement fails
        """
        try:
            if self.acquire(timeout=timeout):
                yield True
                return
        finally:
            self.release()
        if throw:
            raise TimeoutError(f"Could not acquire lock {self._name}")
        yield False


    def __enter__(self):
        """
        enter stage to resemble multiprocessing.Lock or threading.Lock behavior

        Returns
        -------
        bool
            True if lock acquired, False otherwise

        Raises
        ------
        TimeoutError
            if self._throw is True and lock acquirement fails
        """
        # acquire the lock
        if self.acquire(timeout=self._timeout):
            return True
        if self._throw:
            raise TimeoutError(f"Could not acquire lock {self._name}")
        return False

    def __call__(self, timeout=None, throw=False):
        """
        call stage of context manager. set timeout and throw as parameters

        Parameters
        ----------
        timeout : _type_, optional
            max timeout for lock acquirement, by default None
        throw : bool, optional
            if lock acquirement fails -> throw, by default False

        Returns
        -------
        self
            ...
        """
        self._timeout = timeout
        self._throw = throw
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        exit stage of context manager. release lock i.e. shm

        Parameters
        ----------
        exc_type : _type_
            ...
        exc_value : _type_
            ...
        traceback : _type_
            ...
        """
        self.release()

    def acquire(self, timeout: float = None) -> bool:
        """
        try to acquire lock i.e. shm

        None -> wait indefinitely
        False -> no timeout (try acquire lock one time)
        True -> 1 second timeout
        float -> timeout in seconds

        Parameters
        ----------
        timeout : float, optional
            max timeout for lock acquirement in seconds. boolean type is also supported,
            True converts to 1 meaning 1 second timeout and False to 0 meaning
            no timeout i.e. lock acquirement is only tried one time. None means
            infinite wait for lock acquirement, by default None

        Returns
        -------
        bool
            True if lock acquired, False otherwise
        """
        start_time = time.perf_counter()
        while (not self._exit_event.is_set()) and \
            (not timeout or time.perf_counter() - start_time < timeout):
            # enter loop if exit event is not set and either no timeout is set (None or 0/False) or
            # the passed time of trying to acquire the lock is smaller than the timeout
            try:
                if self._shm is not None:
                    raise RuntimeError("lock already acquired; "\
                                       "release it first via .release() function. "\
                                       "Alternatively, you are using the same lock instances "\
                                       "among different threads. Do not do that. If you must: "\
                                       "Each thread should use its own lock!")
                self._shm = shared_memory.SharedMemory(name=self._name, create=True, size=1)
                add_to_resource_tracker(self._name)
                self.debug("%s acquired lock %s", PROCESS_NAME, self._name)
                return True
            except FileExistsError:
                # if it returns True -> exit event is set and while loop will break
                self.debug("%s could not acquire lock %s; trying again after %f seconds; "\
                         "timeout[s] is %s",
                         PROCESS_NAME,
                         self._name,
                         self._poll_interval,
                         timeout)
                if timeout is False:
                    # if timeout is explicitly False
                    #   -> break loop and return False since acquirement failed
                    break
                self._exit_event.wait(self._poll_interval)
                continue
        # could not acquire within timeout or exit event is set
        return False

    def release(self) -> bool:
        """
        release potentially acquired lock i.e. shm

        Returns
        -------
        bool
            True if lock has been acquired and could be release properly.
            False if the lock has not been acquired before OR if the lock
                already has been released.

        Raises
        ------
        RuntimeError
            if the lock could not be released properly
        """
        if self._shm is not None:
            try:
                self._shm.close()
                self._shm.unlink()
                self._shm = None
                remove_from_resource_tracker(self._name)
                self.debug("%s released lock %s", PROCESS_NAME, self._name)
                return True
            except FileNotFoundError:
                # can happen if the lock is acquired and the resource tracker cleans it up
                # before it is released. Since this should not be a problem we just log it
                # NOTE that this only occurs for posix systems which support unlink() function
                self.debug("lock %s has been released already. This might happen on "\
                           "posix systems if the resource tracker was used to clean "\
                           "up while the lock was acquired.",
                           self._name)
                remove_from_resource_tracker(self._name)
            except Exception as err: # pylint: disable=(broad-exception-caught)
                # other errors will raised as RuntimeError
                raise RuntimeError(f"process {PROCESS_NAME} could not release lock "\
                    f"{self._name}. This might result in a leaking resource! "\
                    f"Error was {err}") from err
        return False

    def __del__(self):
        """
        destructor
        """
        self.release()

    @property
    def acquired(self):
        """
        check if lock is acquired
        """
        return self._shm is not None

    @property
    def name(self):
        """
        get shared memory name
        """
        return self._name

    @property
    def poll_interval(self):
        """
        get poll interval
        """
        return self._poll_interval

    def get_exit_event(self):
        """
        get exit event

        NOTE do not set this event to any type except an Event

        Returns
        -------
        multiprocessing.synchronize.Event
            set this to stop the lock acquirement
        """
        return self._exit_event
