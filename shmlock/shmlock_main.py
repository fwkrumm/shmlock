"""
main class of shared memory lock.

If possible never terminate this process using ctrl+c or similar. This can lead to dangling
shared memory blocks. Best practice is to use the exit event to stop the lock from acquirement.
"""
import os
import time
import sys
import threading
import warnings
import multiprocessing
import multiprocessing.synchronize
from multiprocessing import shared_memory
from contextlib import contextmanager
import logging
from typing import Union, Optional
import signal
import weakref
import atexit
import gc

try:
    # try import memory barrier module
    import membar
except ImportError:
    # module not found; warn user that memory barriers will not be used
    # however this might be intentional; currently there is not parameter for this
    membar = None

__all__ = ["ShmLock",
           "remove_shm_from_resource_tracker",
           "exceptions",
           "create_logger"
           ]

# reveal functions for resource tracking adjustments
import shmlock.shmlock_exceptions as exceptions
from shmlock.shmlock_monkey_patch import remove_shm_from_resource_tracker
from shmlock.shmlock_base_logger import ShmModuleBaseLogger, create_logger
from shmlock.shmlock_uuid import ShmUuid
from shmlock.shmlock_config import ShmLockConfig, ExitEventMock
from shmlock.shmlock_warnings import ShmLockDanglingSharedMemoryWarning, \
                                     ShmMemoryBarrierMissingWarning


if os.name == "nt":
    try:
        import win32api # pylint: disable=import-error
        import win32con # pylint: disable=import-error
    except ImportError:
        # prevents console handler on exit
        win32api = None
        win32con = None
else:
    # on posix systems we do not need to import win32api and win32con
    win32api = None
    win32con = None

LOCK_SHM_SIZE = 16 # size of the shared memory block in bytes to store uuid


class ShmLock(ShmModuleBaseLogger):

    """
    lock class using shared memory to synchronize shared resources access

    NOTE that the lock is reentrant, i.e. the same lock object can be acquired multiple times
    by the same thread.
    """

    def __init__(self,
                 lock_name: str,
                 poll_interval: Union[float, int] = 0.05,
                 logger: logging.Logger = None,
                 exit_event: Union[multiprocessing.synchronize.Event, threading.Event] = None,
                 memory_barrier: bool = False,
                 block_signals: bool = False,
                 track: bool = None):
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
        exit_event : multiprocessing.synchronize.Event | threading.Event, optional
            if None is provided a simple sleep will be used. if the exit event is set, the
            acquirement will stop and it will not be possible to acquire a lock until event is
            unset/cleared, by default None
        memory_barrier : bool, optional
            if True memory barriers will be used to ensure memory visibility across processes.
            This requires the membar module to be installed. If membar module is not found
            a warning is raised and memory barriers will not be used, by default False
        block_signals : bool, optional
            if True SIGINT and SIGTERM signals will be blocked during shared memory
            creation to prevent dangling shared memory in case the process is interrupted.
            Note that, depending on the platform, this will not work if the process is
            terminated, by default False
        track : bool, optional
            set to False if you do want the shared memory block been tracked.
            This is parameter only supported for python >= 3.13 in SharedMemory
            class, by default None
        """
        self._shm = threading.local() # will contain shared memory reference and counter
        super().__init__(logger=logger)

        # type checks
        if (not isinstance(poll_interval, (float, int,))) or poll_interval <= 0:
            raise exceptions.ShmLockValueError("poll_interval must be a float or int and > 0")
        if not isinstance(lock_name, str):
            raise exceptions.ShmLockValueError("lock_name must be a string")
        if exit_event and \
            not isinstance(exit_event, (multiprocessing.synchronize.Event, threading.Event,)):
            raise exceptions.ShmLockValueError("exit_event must be a multiprocessing.Event "\
                                               "or thrading.Event")

        if not lock_name:
            raise exceptions.ShmLockValueError("lock_name must not be empty")

        # create config containing all parameters
        self._config = ShmLockConfig(name=lock_name,
                                     poll_interval=float(poll_interval),
                                     timeout=None, # for __call__
                                     exit_event=exit_event if exit_event is not None else\
                                          ExitEventMock(),
                                     track=None,
                                     uuid=ShmUuid(),
                                     pid=os.getpid(),
                                     memory_barrier=False,
                                     block_signals=block_signals
                                     )

        if track is not None:
            # track parameter not supported for python < 3.13
            if sys.version_info < (3, 13):
                raise ValueError("track parameter has been set but it is only supported for "\
                                 "python >= 3.13")
            self._config.track = bool(track)

        if memory_barrier:
            if membar is None:
                msg = "membar module not found. Memory barriers will not be used. " \
                      "This might lead to unexpected behavior on some architectures (e.g. ARM)."
                self.error(msg)
                warnings.warn(msg, ShmMemoryBarrierMissingWarning, stacklevel=2)
            else:
                self._config.memory_barrier = True

        self.debug("lock %s initialized.", self)

    def __repr__(self):
        """
        representation of the lock class

        Returns
        -------
        str
            representation of the lock class
        """
        return f"ShmLock(name={self._config.name}, "\
               f"uuid={self._config.uuid}, "\
               f"description={self._config.description})"

    @contextmanager
    def lock(self, timeout: float = None):
        """
        lock method to be used as context manager

        Parameters
        ----------
        timeout : float, optional
            max timeout in seconds until lock acquirement is aborted, by default None

        Yields
        ------
        bool
            True if lock acquired, False otherwise
        """
        try:
            if self.acquire(timeout=timeout):
                self._shm.counter = getattr(self._shm, "counter", 0) + 1
                self.debug("lock acquired via contextmanager incremented thread ref counter to %d",
                           self._shm.counter)
                yield True
                return
        finally:
            # decrement counter (default it to 1 in ase lock has never been acquired before so
            # that counter never becomes negative); this would otherwise happen if one would
            # (for whatever reason) call release() multiple times without acquiring the lock
            self._shm.counter = max(getattr(self._shm, "counter", 1) - 1, 0)
            self.debug("lock %s decremented thread ref counter to %d",
                    self,
                    self._shm.counter)
            if self._shm.counter == 0:
                # release the lock if counter is 0
                self.release()
        yield False


    def __enter__(self):
        """
        enter stage to resemble multiprocessing.Lock or threading.Lock behavior

        Returns
        -------
        bool
            True if lock acquired, False otherwise
        """
        # acquire the lock
        if self.acquire(timeout=self._config.timeout):
            self._shm.counter = getattr(self._shm, "counter", 0) + 1
            self.debug("lock acquired via __enter__ incremented thread ref counter to %d",
                       self._shm.counter)
            return True
        return False

    def __call__(self, timeout=None):
        """
        call stage of context manager. set timeout as parameter

        Parameters
        ----------
        timeout : _type_, optional
            max timeout for lock acquirement, by default None

        Returns
        -------
        self
            ...
        """
        self._config.timeout = timeout
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
        self._shm.counter = max(getattr(self._shm, "counter", 1) - 1, 0)
        self.debug("lock %s decremented thread ref counter to %d",
                self,
                self._shm.counter)
        if self._shm.counter == 0:
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

        if self._config.pid != os.getpid():
            raise exceptions.ShmLockRuntimeError(f"lock {self} has been created in another "\
                                                 "process and cannot be used in this process. "\
                                                 "Do not shared locks among processes!")

        start_time = time.perf_counter()
        try:
            while (not self._config.exit_event.is_set()) and \
                (not timeout or time.perf_counter() - start_time < timeout):
                # enter loop if exit event is not set and either no timeout is set (0/False) or
                # the passed time of trying to acquire the lock is smaller than the timeout
                # None means infinite wait
                try:
                    return self._create_or_fail() # returns True or raises exception
                except FileExistsError:
                    # shared memory block already exists, i.e. the lock is already acquired
                    self.debug("could not acquire lock %s; "\
                            "timeout[s] is %s",
                            self,
                            timeout)
                    if timeout is False:
                        # if timeout is explicitly False
                        #   -> break loop and return False since acquirement failed
                        break
                    self._config.exit_event.wait(self._config.poll_interval)
                    continue
                except KeyboardInterrupt as err:
                    # special treatment for keyboard interrupt since this might lead to a
                    # dangling shared memory block. This is only the case if the process is
                    # interrupted somewhere within the shared memory creation process within the
                    # multiprocessing library.
                    msg = "KeyboardInterrupt: process interrupted while trying to "\
                         f"acquire lock {self}. This might lead to leaking resources. "\
                          "shared memory variable is " \
                         f"""{getattr(self._shm, "shm", None)}. """ \
                          "Try to use the query_for_error_after_interrupt() function to " \
                          "check shared memory integrity. Make sure other processes "\
                          "are still able to acquire the lock."
                    self.error(msg)
                    warnings.warn(msg, ShmLockDanglingSharedMemoryWarning, stacklevel=2)

                    # raise keyboardinterrupt to stop the process; release() will clean up.
                    raise KeyboardInterrupt("ctrl+c") from err
            # could not acquire within timeout or exit event is set
            return False
        except OSError as err:
            # on windows this might happen at program termination e.g. if an unittest fails
            msg = f"During acquiring lock {self} the exit event handle got invalid (main "\
                   "process terminated?). Make sure the exit event does not become invalid. "\
                   "Alternatively use use_mock_exit_event() function which repleaces the exit "\
                   "event with a mock event which simply uses time.sleep() and has no handle "\
                   "which might become invalid."
            self.error(msg)
            self.release() # make sure lock is released
            raise OSError(msg) from err

    def _check_already_acquired(self):
        """
        check if lock is already acquired by this thread

        Returns
        -------
        bool
            True if already acquired, False otherwise

        Raises
        ------
        exceptions.ShmLockRuntimeError
            if uuid mismatch detected
        """
        if getattr(self._shm, "shm", None) is None:
            return False

        # this thread already acquired the lock
        # check that the uuid matches (otherwise something is very wrong)
        if self._shm.shm.buf[:LOCK_SHM_SIZE] == self._config.uuid.uuid_bytes:
            self.debug("lock %s already acquired by this thread.", self)
            return True

        # uuid does not match but seemingly this thread has (somehow) acquired the lock
        # this should not happen!
        raise exceptions.ShmLockRuntimeError(
            f"lock {self} seemingly already acquired by "
            f"this thread but uuid does not match (expected {self._config.uuid}, "
            f"got {self._shm.shm.buf[:LOCK_SHM_SIZE]}). This should not happen!")

    def _setup_signal_blocking(self) -> tuple:
        """
        setup signal handlers to block signals during shared memory creation

        Returns
        -------
        tuple
            (old_signal_handlers dict, signal_received container as list)
        """
        old_signal_handlers = {}
        signal_received = [None]  # Use list to allow modification in nested function

        def signal_handler(signum, frame):  # pylint: disable=unused-argument
            """Custom signal handler to catch signals during shared memory creation"""
            signal_received[0] = signum
            self.warning("signal %s received during shared memory creation for lock %s",
                         signum, self)

        for sig in [signal.SIGINT, signal.SIGTERM]:
            old_signal_handlers[sig] = signal.getsignal(sig)
            try:
                signal.signal(sig, signal_handler)
            except Exception as err: # pylint: disable=(broad-exception-caught)
                msg = f"could not set signal handlers for signal {sig} to block signals during "\
                      f"shared memory creation for lock {self}: {err}"
                self.error(msg)
                # restore all previously set signal handlers (best effort)
                for prev_sig, prev_handler in old_signal_handlers.items():
                    if prev_handler is not None:
                        try:
                            signal.signal(prev_sig, prev_handler)
                        except Exception: # pylint: disable=(broad-exception-caught)
                            pass  # prevent exception here
                raise exceptions.ShmLockSignalOverwriteFailed(msg) from err

        return old_signal_handlers, signal_received

    def _restore_signal_handlers(self,
                                 old_signal_handlers: dict,
                                 signal_received: list) -> None:
        """
        restore old signal handlers and re-raise received signal if any

        Parameters
        ----------
        old_signal_handlers : dict
            Dictionary of signal handlers to restore
        signal_received : list
            Container with received signal number
        """
        if not old_signal_handlers:
            # nothing to do
            return

        error_occurred = []

        for sig, handler in old_signal_handlers.items():
            if handler is None:
                # this happens if lock is used within __del__ (should be avoided)
                self.debug("old signal handler for signal %s is None, "\
                           "skipping restore for lock %s", sig, self)
                continue
            try:
                signal.signal(sig, handler)
                self.debug("restored signal handler for signal %s after shared memory creation",
                            sig)
            except Exception as err: # pylint: disable=(broad-exception-caught)
                msg = f"could not restore signal handlers after shared memory " \
                    f"creation for lock {self} and signal {sig}: {err}"
                self.error(msg)
                # continue loop to attempt to restore other signal handlers
                error_occurred.append(err)

        if error_occurred:
            # raise exception if any error occurred during restore
            raise exceptions.ShmLockSignalOverwriteFailed(
                "could not restore all signal handlers after shared memory creation "
                f"for lock {self}. The errors were: {error_occurred}")

        if signal_received[0] is not None:
            self.warning("re-raising signal %s after shared memory creation for lock %s",
                         signal_received[0], self)
            signal.raise_signal(signal_received[0])

    def _create_shared_memory(self):
        """
        create the shared memory block

        Returns
        -------
        shared_memory.SharedMemory
            The created shared memory object
        """
        if self._config.track is not None:
            return shared_memory.SharedMemory(  # pylint:disable=(unexpected-keyword-arg)
                name=self._config.name,
                create=True,
                size=LOCK_SHM_SIZE,
                track=self._config.track)

        return shared_memory.SharedMemory(
            name=self._config.name,
            create=True,
            size=LOCK_SHM_SIZE)

    def _create_or_fail(self):
        """
        create shared memory block i.e. successfully acquire lock

        Returns
        -------
        boolean
            returns True if lock has been acquired successfully, or raises Exception

        Raises
        ------
        exceptions.ShmLockRuntimeError
            if lock already acquired i.e. for other locks this would mean a deadlock
        FileExistsError
            if shared memory block already exists i.e. the lock is already acquired
        """
        # check if already acquired by this thread
        already_acquired = self._check_already_acquired()
        if already_acquired:
            return already_acquired

        # setup signal blocking if needed
        old_signal_handlers = {}
        signal_received = [None]
        if self._config.block_signals:
            old_signal_handlers, signal_received = self._setup_signal_blocking()

        try:
            self._shm.shm = self._create_shared_memory()
        finally:
            self._restore_signal_handlers(old_signal_handlers, signal_received)

        # NOTE: shared memory is after creation(!) not filled with the uuid data in
        # the same operation. so it is possible that the shm block has been
        # created but not filled with the uuid data so it will be empty for a moment.
        # this is however not a problem since this is within the same process only used to
        # assure correct reentrant behavior. inter-process-wise this should only be used for
        # debugging in case one has a deadlock and does not know which lock acquired the
        # shared memory.
        self._shm.shm.buf[:LOCK_SHM_SIZE] = self._config.uuid.uuid_bytes

        self.debug("lock %s acquired", self)

        # are there any branches without keyboard interrupt which might lead to self._shm.shm
        # still being None but shared memory being created?
        assert self._shm.shm is not None, "self._shm.shm is None without exception being raised. "\
            "This should not happen!"

        # ensure all reads are visible so that the successful acquirement assures
        #  that potential memory operations are visible to this process
        if self._config.memory_barrier:
            membar.rmb()

        return True

    def query_for_error_after_interrupt(self, number_of_checks: int = 3):
        """
        NOTE this function THROWS or returns None in case all is fine

        try to check if the shared memory block is dangling or not. This is only the case
        if the process is interrupted somewhere within the shared memory creation process

        NOTE that this might affect the acquirement of other locks. Since e.g. on Windows
        as long as the handle is open the shared memory block is not released.
        So this version is used best at the beginning of the main process or in case any
        processes have been interrupted.

        NOTE that if lock has been acquired (shm block created) but lock did not yet wrote
        its uuid to the block, this function will return (b"\x00" * LOCK_SHM_SIZE)

        Parameters
        ----------
        number_of_checks : int, optional
            number of checks to be performed to check if the shared memory block is dangling,
            by default 3

        Raises
        ------

        exceptions.ShmLockRuntimeError
            if the lock is already acquired which means the lock so far is working fine.

        exceptions.ShmLockDanglingSharedMemoryError
            if the shared memory block is potentially dangling i.e. it had been created but
            its reference was not yet returned. So it cannot be released or attached to.
            Probably the user has to delete it manually from /dev/shm (Linux).

        exceptions.ShmLockValueError
            if the shared memory block is not available, i.e. it has been created but with size 0.
            This is only the case if the process was interrupted during the acquirement process
            and the shared memory block was not created yet. New shared memory blocks cannot
            be created, not can any instance attach to it. Probably the user has to delete it
            manually from /dev/shm (Linux).

        FileNotFoundError
            if the shared memory block does not exist

        Returns
        -------
        None if all is fine; otherwise an exception is raised

        """

        if getattr(self._shm, "shm", None) is not None:
            raise exceptions.ShmLockRuntimeError(f"Lock {self} is currently acquired. This "\
                "function checks for dangling shared memory after shared memory creation had "\
                "been interrupted. release lock first.")

        try:

            cnt = 0

            while cnt < number_of_checks:

                cnt+=1
                shm = None

                # check if shared memory is attachable; NOTE that we do not call
                # shm.unlink() here since we cannot assure that another process
                # might have acquired the lock. it us not probable but possible.
                # also NOTE that on Windows, no new locks can be acquired during
                # we are here attached to it. This also means that if there
                # is another interrupt (e.g. ctrl+c spamming) this might lead to
                # an additional dangling shm block?
                try:
                    shm = shared_memory.SharedMemory(name=self._config.name)

                    # check if uuid for locking lock is available
                    if shm.buf[:LOCK_SHM_SIZE] == b"\x00" * LOCK_SHM_SIZE:
                        # we could attach but no uuid is set, i.e. either a dangling shm
                        # or the other lock process just created the block but did not yet
                        # wrote its uuid; we try multiple times to attach to the shm block.
                        # if we end up in this condition each time we assume that the
                        # block is dangling.
                        time.sleep(0.05) # magic number; 50ms
                        continue

                    # check that this lock instance did not acquire the lock. this should
                    # not be possible with self._shm.shm being None
                    if shm.buf[:LOCK_SHM_SIZE] == self._config.uuid.uuid_bytes:
                        raise exceptions.ShmLockRuntimeError("the buffer should not be equal "\
                            f"to the uuid of the lock {str(self)} since self._shm is None and "\
                            "so the uid should not have been set!")

                    # some other process has acquired the lock. this instance can die now.
                    break
                finally:
                    if shm is not None:
                        shm.close()
            else:
                self.error("KeyboardInterrupt: process interrupted while trying to "\
                           "acquire lock %s. The shared memory block is PROBABLY "\
                           "dangling since for %s times no uuid has been "\
                           "written to the block. A manual clean up might be required, "\
                           "i.e. on Linux you could try to attach and unlink or delete "\
                           "the mmap file in /dev/shm. On Windows all handles need to be closed.",
                           self,
                           number_of_checks)
                raise exceptions.ShmLockDanglingSharedMemoryError("Potential "\
                    f"dangling shm: {self}")

            # if else not triggered in loop -> keyboard interrupt without dangling shm
            # message is raised
        except ValueError as err:
            # happened only on linux systems so far: shared memory block has been
            # created but with size 0; so it cannot be attached to (size == 0) or
            # created (exists already). In this case shared memory has to be removed
            # from /dev/shm manually
            self.error("%s: shared memory %s is not available. "\
                "This might be caused by a process termination. "\
                "Please check the system for any remaining shared memory "\
                "blocks and on Linux clean them up manually at path /dev/shm.",
                err,
                self)
            raise exceptions.ShmLockValueError(f"Valueerror for {self}. On POSIX there is "\
                                               "probably a zero-sized mmap file at /dev/shm "\
                                               "which has to be removed manually") from err
        except FileNotFoundError:
            # shared memory does not exist, so keyboard interrupt did not yield to
            # any undesired behavior. this is "all good"
            pass

    def release(self, force: bool = False) -> bool:
        """
        release potentially acquired lock i.e. shm

        Parameters
        ----------
        force : bool, optional
            if True the lock will skip the check if lock has been acquired via contextmanager.
            This means that code like
            with lock:
                lock.release(force=True)
            would be theoretically possible. HOWEVER the use case of this parameter is to
            force a release within a signal.signal handler, if a process gets terminated
            with the lock potentially being acquired via context manager. Details are provided
            in the readme.

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
        try:
            if self._config.memory_barrier:
                # ensure all writes are visible before release. This might not be
                # necessary on all architectures, but it's a good practice to ensure
                # that all writes are visible to other processes before releasing the
                # lock.
                membar.wmb()
            if self._config.pid != os.getpid():
                raise exceptions.ShmLockRuntimeError(f"lock {self} has been created in another "\
                                                    "process and cannot be used in this process. "\
                                                    "Do not shared locks among processes! If " \
                                                    "shared memory has already been acquired this "\
                                                    "might lead to a deadlock and/or leaking "\
                                                    f"resource: shared memory is {self._shm}")
        except AttributeError:
            # if exception is thrown before config has been defined during __init__ e.g. due to
            # failed type check
            pass

        if (not force) and getattr(self._shm, "counter", 0) > 0:
            # for example if you try to release lock within context manager
            raise exceptions.ShmLockRuntimeError(f"lock {self} is still acquired by this "\
                "thread via contextmanager or __enter__ call.")

        try:
            attribute = getattr(self._shm, "shm", None)
        except AttributeError:
            # if exception is thrown before _shm has been defined during __init__
            # e.g. if invalid parameters are used
            attribute = None

        if attribute is not None:
            # only release if shared memory reference has been set and counter reached 0.
            # This prevents that release of nested with s: with s: with s: ... blocks.
            try:
                self._shm.shm.close()
                self._shm.shm.unlink()
                self._shm.shm = None
                self.debug("lock %s released", self)
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
                raise exceptions.ShmLockRuntimeError(f"process could not "\
                    f"release lock {self}. This might result in a leaking resource! "\
                    f"Error was {err}") from err
        return False

    def __del__(self):
        """
        destructor
        """
        self.release(force=True)

    @property
    def locked(self) -> bool:
        """
        check if lock is acquired (alternative api)
        """
        # make sure member exists
        return getattr(self._shm, "shm", None) is not None


    @property
    def acquired(self) -> bool:
        """
        check if lock is acquired
        """
        return self.locked

    @property
    def name(self) -> str:
        """
        get shared memory name
        """
        return self._config.name

    @property
    def poll_interval(self) -> float:
        """
        get poll interval
        """
        return self._config.poll_interval

    @property
    def uuid(self) -> str:
        """
        get uuid of the lock
        """
        return self._config.uuid.uuid_str

    @property
    def description(self) -> str:
        """
        get description of the lock
        """
        return self._config.description

    @description.setter
    def description(self, description: str):
        """
        set description of the lock to add custom information to the lock
        e.g. for debugging purposes

        Parameters
        ----------
        description : str
            description of the lock
        """
        self._config.description = description

    def get_exit_event(self) -> Union[multiprocessing.synchronize.Event,
                                      threading.Event,
                                      ExitEventMock]:
        """
        get exit event; if lock should be stopped/prevent from further acquirements, set this
        event.

        NOTE do not set this event to any type except an Event

        Returns
        -------
        multiprocessing.synchronize.Event, threading.Event, ExitEventMock
            set this to stop i.e. prevent the lock acquirement
        """
        return self._config.exit_event

    def use_mock_exit_event(self):
        """
        use mock exit event which replaces the multiprocessing or threading event.
        This is useful for lock calls within __del__ methods since (at least on Windows) within
        interative sessions the exit event might be invalid at garbace collection time.
        In this case it might be useful to use this mock exit event which simply uses a
        time.sleep()
        """
        if isinstance(self._config.exit_event, ExitEventMock):
            self.debug("mocked exit event already set for lock %s", self)
            return
        self._config.exit_event = ExitEventMock()
        self.debug("using mocked exit event for lock %s", self)

    def debug_get_uuid_of_locking_lock(self) -> Optional[str]:
        """
        get uuid of the locking lock


        NOTE that if you call this in the mean time the lock might be released by another
        process and you get None. Also on windows during this time no new locks can be acquired.
        This should be only used for debugging purposes.

        Returns
        -------
        str
            uuid of the locking lock
        None
            if the lock does not exist or is not acquired;
        """
        shm = None
        try:
            shm = shared_memory.SharedMemory(name=self._config.name)
            return ShmUuid.byte_to_string(bytes(shm.buf[:LOCK_SHM_SIZE]))
        except FileNotFoundError:
            # shm does not exist
            return None
        except ValueError:
            # shm is currently created i.e. the file is already there but the content is missing
            return None
        finally:
            if shm is not None:
                shm.close()

    def add_exit_handlers(self,
                          register_atexit: bool = True,
                          register_signal: bool = True,
                          register_weakref: bool = True,
                          register_console_handler: bool = True,
                          call_gc: bool = True):
        """
        Experimental and not recommended to use in production code!

        add exit handlers to make sure lock is released if e.g. console is shut down or
        process is terminated via ctrl+c or similar and lock is still acquired.

        NOTE that there is still the possibility that the shared memory has been acquired but
        the process is terminated before the shared memory object has been returned.

        Parameters
        ----------
        register_atexit : bool, optional
            register atexit handler to close the shared memory, by default True
        register_signal : bool, optional
            register signal handlers to clean up the shared memory, by default True
            only for POSIX systems since it did not work as expected on Windows
        register_weakref : bool, optional
            register weakref handler to clean up the shared memory, by default True
        register_console_handler : bool, optional
            register console handler to clean up the shared memory, by default True
            only for Windows systems
        call_gc : bool, optional
            call garbage collector to clean up the shared memory, by default True
        """
        if os.name == "posix" and register_signal:

            # get potentially existing signal handlers
            existing_handlers_sigint = signal.getsignal(signal.SIGINT)
            existing_handlers_sigterm = signal.getsignal(signal.SIGTERM)
            existing_handlers_sighup = signal.getsignal(signal.SIGHUP)

            def clean_up(signum, frame):
                """
                cleanup function to close the shared memory queue
                """
                self.release(force=True)

                # call existing handlers if they are callable
                if callable(existing_handlers_sigint):
                    existing_handlers_sigint(signum, frame)
                if callable(existing_handlers_sigterm):
                    existing_handlers_sigterm(signum, frame)
                if callable(existing_handlers_sighup):
                    existing_handlers_sighup(signum, frame)

            # register signal handlers
            signal.signal(signal.SIGINT, clean_up)
            signal.signal(signal.SIGTERM, clean_up)
            signal.signal(signal.SIGHUP, clean_up)


        if os.name == "nt" and register_console_handler:
            if win32api is not None and win32con is not None:
                # only for windows systems which us necessary if a console is closed
                def console_handler(ctrl_type):
                    if ctrl_type in (win32con.CTRL_C_EVENT,
                                     win32con.CTRL_CLOSE_EVENT,
                                     win32con.CTRL_LOGOFF_EVENT,
                                     win32con.CTRL_SHUTDOWN_EVENT,):
                        self.release(force=True)
                        return True  # Prevent immediate termination if possible
                    return False  # Continue default behavior

                win32api.SetConsoleCtrlHandler(console_handler, True)
            else:
                self.error("win32api or win32con is not available. "\
                           "Cannot register console handler for lock %s. "\
                           "Make sure you have the pywin32 package installed.",
                           self)

        if register_weakref:
            # register weakref handler to clean up the shared memory
            weakref.finalize(self, self.release, force=True)

        if register_atexit:
            # register atexit handler to close the shared memory queue
            # usually this should not be necessary since the usage of signal and weakref, but
            # safe is safe
            atexit.register(self.release, force=True)

        if call_gc:
            # call garbage collector
            gc.collect()
