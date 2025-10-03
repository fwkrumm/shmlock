"""
Configuration dataclass for the shared memory lock.

This module provides configuration management and mock classes
for the shared memory lock implementation.
"""
import time
import multiprocessing
import multiprocessing.synchronize
import threading
from dataclasses import dataclass, field
from typing import Union, Optional

from shmlock.shmlock_uuid import ShmUuid


class ExitEventMock:
    """
    Mock class for exit event when not desired by user.
    
    Note that this is not thread-safe or process-safe and should only be used
    if the user does not want to use any threading or multiprocessing events
    as exit event. The wait will simply be a sleep for given timeout.
    """

    def __init__(self) -> None:
        """Initialize the mock exit event."""
        self._set: bool = False

    def is_set(self) -> bool:
        """
        Mock is_set function to resemble Event.is_set().
        
        This function returns True if the exit event is set, otherwise False.

        Returns
        -------
        bool
            True if the exit event is set, otherwise False
        """
        return self._set

    def set(self) -> None:
        """Mock set function to resemble Event.set()."""
        self._set = True

    def clear(self) -> None:
        """Mock clear function to resemble Event.clear()."""
        self._set = False

    def wait(self, sleep_time: float) -> None:
        """
        Mock wait function to resemble Event().
        
        Note however that this does not react on .set() or .clear() calls
        and will simply sleep for the given sleep time.

        Parameters
        ----------
        sleep_time : float
            Time in seconds to wait until the function returns
        """
        if not self._set:
            time.sleep(sleep_time)


@dataclass
class ShmLockConfig:  # pylint: disable=(too-many-instance-attributes)
    """
    Data class to store the configuration parameters of the lock.

    Attributes
    ----------
    name : str
        Name of the lock i.e. the shared memory block
    poll_interval : float
        Time delay in seconds after a failed acquire try after which it will be tried
        again to acquire the lock
    exit_event : Union[multiprocessing.synchronize.Event, threading.Event, ExitEventMock]
        Exit event to control lock acquisition. If event is set to true,
        acquirement will stop and it will not be possible to acquire a lock until event is
        unset/cleared
    track : Optional[bool]
        Set to False if you do want the shared memory block been tracked.
        This is parameter only supported for python >= 3.13 in SharedMemory class
    timeout : Optional[float]
        Max timeout in seconds until lock acquirement is aborted
    uuid : ShmUuid
        UUID of the lock
    pid : int
        Process ID where the lock was created
    description : str
        Custom description of the lock which can be set as property setter
    """
    name: str
    poll_interval: float
    exit_event: Union[multiprocessing.synchronize.Event, threading.Event, ExitEventMock]
    track: Optional[bool]
    timeout: Optional[float]
    uuid: ShmUuid
    pid: int
    description: str = field(default="")

    def __post_init__(self) -> None:
        """
        Validate configuration parameters after initialization.
        
        Raises
        ------
        ValueError
            If any configuration parameter is invalid
        """
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string")
        
        if not isinstance(self.poll_interval, (int, float)) or self.poll_interval <= 0:
            raise ValueError("poll_interval must be a positive number")
        
        if self.timeout is not None and (not isinstance(self.timeout, (int, float)) or self.timeout < 0):
            raise ValueError("timeout must be a non-negative number or None")
        
        if not isinstance(self.pid, int) or self.pid <= 0:
            raise ValueError("pid must be a positive integer")
