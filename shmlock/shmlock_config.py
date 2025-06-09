"""
config dataclass for the shared memory lock
"""
import time
import multiprocessing
import multiprocessing.synchronize
import threading
from dataclasses import dataclass
from typing import Union

from shmlock.shmlock_uuid import ShmUuid


class ExitEventMock():
    """
    mock class for exit event if not desired by user. Note that this is not thread-safe or
    process-safe and should only be used if the user does not want so use any threading or
    multiprocessing events as exit event. The wait will simply be a sleep for given timeout.
    """

    def __init__(self):
        """
        initialize the mock exit event
        """
        self._set = False

    def is_set(self) -> bool:
        """
        mock is_set function to resemble Event.is_set()
        This function returns True if the exit event is set, otherwise False.

        Returns
        -------
        bool
            True if the exit event is set, otherwise False.
        """
        return self._set

    def set(self):
        """
        mock set function to resemble Event.set()
        """
        self._set = True

    def clear(self):
        """
        mock clear function to resemble Event.clear()
        """
        self._set = False

    def wait(self, sleep_time: float):
        """
        mock wait function to resemble Event(). Note however that this does not react on
        .set() or .clear() calls and will simply sleep for the given sleep time.

        Parameters
        ----------
        sleep_time : float
            time in seconds to wait until the function returns.
        """
        if not self._set:
            time.sleep(sleep_time)
        # we do not need a return Value


@dataclass
class ShmLockConfig(): # pylint: disable=(too-many-instance-attributes)
    """
    data class to store the configuration parameters of the lock

    TODO we could include a type check in this dataclass

    Attributes
    ----------
    name : str
        name of the lock i.e. the shared memory block
    poll_interval : float
        time delay in seconds after a failed acquire try after which it will be tried
        again to acquire the lock
    exit_event : multiprocessing.synchronize.Event | threading.Event
        if None is provided a new one will be initialized. if event is set to true
        -> acquirement will stop and it will not be possible to acquire a lock until event is
        unset/cleared
    track : bool
        set to False if you do want the shared memory block been tracked.
        This is parameter only supported for python >= 3,13 in SharedMemory
        class
    timeout : float
        max timeout in seconds until lock acquirement is aborted
    uuid : ShmUuid
        uuid of the lock
    description : str, optional
        custom description of the lock which can be set as property setter, by default ""
    """
    name: str
    poll_interval: Union[float, int]
    exit_event: Union[multiprocessing.synchronize.Event, threading.Event, ExitEventMock]
    track: bool
    timeout: float
    uuid: ShmUuid
    pid: int # process id of the lock instance (should stay the same as
             # long as the user does not share the lock via forking which is
             # STRONGLY DISCOURAGED!)
    description: str = "" # custom description
