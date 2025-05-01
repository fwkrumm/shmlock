"""
main class of shared memory lock.

If possible never terminate this process using ctrl+c or similar. This can lead to dangling
shared memory blocks. Best practice is to use the exit event to stop the lock from acquirement.
"""
import uuid
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
import  shmlock.shmlock_exceptions as exceptions
from shmlock.shmlock_monkey_patch import remove_shm_from_resource_tracker
from shmlock.shmlock_resource_tracking import init_custom_resource_tracking
from shmlock.shmlock_resource_tracking import de_init_custom_resource_tracking
from shmlock.shmlock_resource_tracking import de_init_custom_resource_tracking_without_clean_up
from shmlock.shmlock_resource_tracking import add_to_resource_tracker
from shmlock.shmlock_resource_tracking import remove_from_resource_tracker
from shmlock.shmlock_resource_tracking import enable_disable_warnings
from shmlock.shmlock_resource_tracking import PROCESS_NAME

from shmlock.shmlock_base_logger import ShmModuleBaseLogger

LOCK_SHM_SIZE = 16 # size of the shared memory block in bytes to store uuid
KEYBOARD_INTERRUPT_QUERY_NUMBER = 3 # at keyboard interrupt it will be checked if there is a
                                   # dangling shared memory block. This will be done a specific
                                   # number of times. Not a perfect solution

# to-do: to own class
class ShmUuid:
    """
    data class to store the uuid of the lock
    """

    def __init__(self):
        self.uuid_ = uuid.uuid4()
        self.uuid_bytes = self.uuid_.bytes
        self.uuid_str = str(self.uuid_)

    def __repr__(self):
        return f"ShmUuid(uuid={self.uuid_})"

    @staticmethod
    def byte_to_string(byte_repr: bytes) -> str:
        """
        convert byte representation of uuid to string representation

        Parameters
        ----------
        byte_repr : bytes
            byte representation of uuid

        Returns
        -------
        str
            string representation of uuid
        """
        return str(uuid.UUID(bytes=byte_repr))

    @staticmethod
    def string_to_bytes(uuid_str: str) -> bytes:
        """
        convert string representation of uuid to byte representation

        Parameters
        ----------
        uuid_str : str
            string representation of uuid

        Returns
        -------
        bytes
            byte representation of uuid
        """
        return uuid.UUID(uuid_str).bytes

class ShmLock(ShmModuleBaseLogger):

    """
    lock class using shared memory to synchronize shared resources access
    """

    def __init__(self,
                 lock_name: str,
                 poll_interval: float|int = 0.05,
                 logger: logging.Logger = None,
                 exit_event: multiprocessing.synchronize.Event = None):
        """
        default init. set shared memory name (for lock) and poll_interval.
        the latter is used to check if lock is available every poll_interval seconds

        Parameters
        ----------
        lock_name : str
            name of the lock i.e. the shared memory block.
        poll_interval : float or int, optional
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

        # type checks
        if (not isinstance(poll_interval, float) and \
            not isinstance(poll_interval, int)) or poll_interval <= 0:
            raise exceptions.ShmLockValueError("poll_interval must be a float or int and > 0")
        if not isinstance(lock_name, str):
            raise exceptions.ShmLockValueError("lock_name must be a string")
        if exit_event is not None and \
            not isinstance(exit_event, multiprocessing.synchronize.Event):
            raise exceptions.ShmLockValueError("exit_event must be a multiprocessing.Event")

        if not lock_name:
            raise exceptions.ShmLockValueError("lock_name must not be empty")

        super().__init__(logger=logger)

        self._name = lock_name
        self._poll_interval = float(poll_interval) # use float type
        self._timeout = None # for __call__
        self._throw = False # for __call__
        self._exit_event = exit_event if exit_event is not None else Event()

        self._uuid = ShmUuid() # unique identifier for the lock

        self.debug("lock %s initialized with poll interval %f",
                   self, self._poll_interval)

    def __repr__(self):
        """
        representation of the lock class

        Returns
        -------
        str
            representation of the lock class
        """
        return f"ShmLock(name={self._name}, uuid={self._uuid}, "\
               f"poll_interval={self._poll_interval}, exit_event={self._exit_event})"

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
            raise exceptions.ShmLockTimeoutError(f"Could not acquire lock {self}")
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
            raise exceptions.ShmLockTimeoutError(f"Could not acquire lock {self}")
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
            # enter loop if exit event is not set and either no timeout is set (0/False) or
            # the passed time of trying to acquire the lock is smaller than the timeout
            # None means infinite wait
            try:
                if self._shm is not None:
                    raise exceptions.ShmLockRuntimeError("lock already acquired; "\
                                       "release it first via .release() function. "\
                                       "Alternatively, you are using the same lock instances "\
                                       "among different threads. Do not do that. If you must: "\
                                       "Each thread should use its own lock!")
                self._shm = shared_memory.SharedMemory(name=self._name,
                                                       create=True,
                                                       size=LOCK_SHM_SIZE)
                # NOTE: shared memory is after creation(!) not filled with the uuid data in
                # the same operation. so it MIGHT be possible that the shm block has been
                # created but not filled with the uuid data so it would be empty.
                self._shm.buf[:LOCK_SHM_SIZE] = self._uuid.uuid_bytes
                add_to_resource_tracker(self._name)
                self.debug("%s acquired lock %s", PROCESS_NAME, self)
                return True
            except FileExistsError:
                # if it returns True -> exit event is set and while loop will break
                self.debug("%s could not acquire lock %s; trying again after %f seconds; "\
                         "timeout[s] is %s",
                         PROCESS_NAME,
                         self,
                         self._poll_interval,
                         timeout)
                if timeout is False:
                    # if timeout is explicitly False
                    #   -> break loop and return False since acquirement failed
                    break
                self._exit_event.wait(self._poll_interval)
                continue
            except KeyboardInterrupt as err:
                # special treatment for keyboard interrupt since this might lead to a
                # dangling shared memory block. This is only the case if the process is
                # interrupted somewhere within the shared memory creation process within the
                # multiprocessing library.
                self.warning("KeyboardInterrupt: process %s interrupted while trying to "\
                           "acquire lock %s. This might lead to leaking resources. "\
                           "shared memory variable is %s",
                           PROCESS_NAME,
                           self,
                           self._shm)

                if self._shm is None:

                    # shared memory object has not yet been returned, but it might have been
                    # created.

                    try:

                        cnt = 0

                        while cnt < KEYBOARD_INTERRUPT_QUERY_NUMBER:

                            cnt+=1

                            # check if shared memory is attachable; NOTE that we do not call
                            # shm.unlink() here since we cannot assure that another process
                            # might have acquired the lock. it us not probable but possible.
                            # also NOTE that on Windows, no new locks can be acquired during
                            # we are here attached to it. This also means that if there
                            # is another interrupt (e.g. ctrl+c spamming) this might lead to
                            # an additional dangling shm block?
                            shm = shared_memory.SharedMemory(name=self._name)

                            # check if uuid for locking lock is available
                            if shm.buf[:LOCK_SHM_SIZE] == b"\x00" * LOCK_SHM_SIZE:
                                # we could attach but no uuid is set, i.e. either a dangling shm
                                # or the other lock process just created the block but did not yet
                                # wrote its uuid; we try multiple times to attach to the shm block.
                                # if we end up in this condition each time we assume that the
                                # block is dangling.
                                shm.close()
                                time.sleep(0.05) # magic number; 50ms
                                continue

                            # check that this lock instance did not acquire the lock. this should
                            # not be possible with self._shm being None
                            assert shm.buf[:LOCK_SHM_SIZE] != self._uuid.uuid_bytes, \
                                "the buffer should not be equal to the uuid of the lock "\
                                f"{str(self)} since self._shm is None and so the uid should "\
                                "not have been set!"

                            # some other process has acquired the lock. this instance can die now.
                            shm.close()
                            break
                        else:
                            self.error("KeyboardInterrupt: process %s interrupted while trying to "\
                                        "acquire lock %s. The shared memory block is seemingly "\
                                        "dangling since for %s times no uuid has been "\
                                        "written to the block. A manual clean up is required, "\
                                        "i.e. on Linux you could try to attach and unlink. "\
                                        "On Windows all handles need to be closed.",
                                        PROCESS_NAME,
                                        self,
                                        KEYBOARD_INTERRUPT_QUERY_NUMBER)
                            raise exceptions.ShmLockDanglingSharedMemoryError("Potential "\
                                f"dangling shm: {self}") from err

                        # if else not triggered in loop -> keyboard interrupt without dangling shm
                        # message is raised
                    except ValueError as err2:
                        # happened only on linux systems so far: shared memory block has been
                        # created but with size 0; so it cannot be attached to (size == 0) or
                        # created (exists already). In this case shared memory has to be removed
                        # from /dev/shm manually
                        self.error("%s: shared memory %s is not available. "\
                            "This might be caused by a process termination. "\
                            "Please check the system for any remaining shared memory "\
                            "blocks and on Linux clean them up manually at path /dev/shm.",
                            err2,
                            self)
                        raise exceptions.ShmLockValueError(f"Shared memory {self}") from err2
                    except FileNotFoundError:
                        # shared memory does not exist, so keyboard interrupt did not yield to
                        # any undesired behavior. will lead to raise of KeyboardInterrupt
                        pass

                # raise keyboardinterrupt to stop the process; release() will clean up.
                raise KeyboardInterrupt("ctrl+c") from err
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
                self.debug("%s released lock %s", PROCESS_NAME, self)
                return True
            except FileNotFoundError:
                # can happen if the lock is acquired and the resource tracker cleans it up
                # before it is released. Since this should not be a problem we just log it
                # NOTE that this only occurs for posix systems which support unlink() function
                self.debug("lock %s has been released already. This might happen on "\
                           "posix systems if the resource tracker was used to clean "\
                           "up while the lock was acquired.",
                           self)

            except Exception as err: # pylint: disable=(broad-exception-caught)
                # other errors will raised as RuntimeError
                raise exceptions.ShmLockRuntimeError(f"process {PROCESS_NAME} could not "\
                    f"release lock {self}. This might result in a leaking resource! "\
                    f"Error was {err}") from err
            finally:
                remove_from_resource_tracker(self._name)
        return False

    def __del__(self):
        """
        destructor
        """
        self.release()

    @property
    def acquired(self) -> bool:
        """
        check if lock is acquired
        """
        return self._shm is not None

    @property
    def name(self) -> str:
        """
        get shared memory name
        """
        return self._name

    @property
    def poll_interval(self) -> float:
        """
        get poll interval
        """
        return self._poll_interval

    def get_exit_event(self) -> multiprocessing.synchronize.Event:
        """
        get exit event

        NOTE do not set this event to any type except an Event

        Returns
        -------
        multiprocessing.synchronize.Event
            set this to stop the lock acquirement
        """
        return self._exit_event

    def get_uuid_of_locking_lock(self) -> str | None:
        """
        get uuid of the locking lock

        Parameters
        ----------
        name : str
            name of the lock

        Returns
        -------
        str
            uuid of the locking lock
        None
            if the lock does not exist or is not acquired; NOTE that if you call this in the
            mean time the lock might be released by another process and you get None
        """
        shm = None
        try:
            shm = shared_memory.SharedMemory(name=self._name)
            return ShmUuid.byte_to_string(shm.buf[:LOCK_SHM_SIZE])
        except FileNotFoundError:
            return None
        finally:
            if shm is not None:
                shm.close()
