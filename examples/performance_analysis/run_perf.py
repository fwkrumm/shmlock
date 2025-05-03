"""
script to run performance analysis for different lock types
"""
# pylint: disable=(duplicate-code)
import time
import sys
import os
import struct
import multiprocessing
import multiprocessing.synchronize
from multiprocessing import shared_memory
import logging
from contextlib import contextmanager
import filelock
import zmq

try:
    import shmlock
except ImportError:
    print("trying to import from root directory")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    new_path = os.path.join(current_dir, "..", "..")
    sys.path.append(new_path)
    import shmlock # pylint:disable=(wrong-import-position)

# specify test parameters
# NOTE that a filelock is being used in this program so keep in mind
# that per run and one process a file is written to the disk
NUM_RUNS = 1000
NUM_PROCESSES = 15


shmlock.enable_disable_warnings(False)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LoggerExampleLockComparison")

# to prevent log spamming if process spawns
log_buffer = {"info": [], "error": []}

if os.name == "posix" and sys.version_info < (3, 13):
    shmlock.remove_shm_from_resource_tracker("", print_warning=False)
    log_buffer.get("info").append("Removed shared memory from resource tracker "\
                                  "for increased performance.\n\n")
else:
    log_buffer.get("info").append("Not removing shared memory from resource tracker\n\n")

# 0.05 is also the current default as defined in ShmLock class. We however use it explicitly
# for this test since it is the default poll interval for filelock
SHM_LOCK_POLL_INTERVAL = 0.05

RESULT_SHM_NAME = "shared_memory_with_results"
ZMQ_URL = "tcp://127.0.0.1:5555"

class ZmqLock():
    """
    add common lock api for a lock using zmq

    NOTE That this requires an own server to run
    or the first lock to be created has to take care
    of this
    """
    def __init__(self, poll_interval: float):
        """
        init lock

        Parameters
        ----------
        poll_interval : float
            after lock acquirement failed, this is the
            time delay after which the lock will try again
            to acquire it
        """
        context = zmq.Context()
        self._lock = context.socket(zmq.REQ)
        self._lock.connect(ZMQ_URL)
        self._poll_interval = poll_interval
        self.locked = False

    def acquire(self) -> bool:
        """
        acquire lock

        Returns
        -------
        bool
            True of lock could be acquired, False
            otherwise
        """
        while True:
            self._lock.send(b"LOCK")
            message = self._lock.recv()
            if message == b"LOCKED":
                self.locked = True
                return True
            # else
            time.sleep(self._poll_interval)
        return False # usually if some timeout would be reached
                     # here however we only use while True for the test

    def release(self):
        """
        release lock if it has been acquired
        """
        if self.locked:
            self._lock.send(b"UNLOCK")
            self._lock.recv()
            self.locked = False

    @contextmanager
    def lock(self):
        """
        for with lock ...
        NOTE that this is currently not used by this test
        but for the sake of completeness we include it

        UNTESTED and as said, currently not required!

        Yields
        ------
        bool
            True of lock could be acquired, false otherwise
        """
        try:
            if self.acquire():
                yield True
                return
        finally:
            self.release()
        yield False

def zmq_server():
    """
    start qmz server which is used to handle the locking
    mechanism

    NOTE that this runs as while True and has no termination
    mechanism, so best to run this as daemonic process
    """
    context = zmq.Context()
    try:
        lock = context.socket(zmq.REP)
        lock.bind(ZMQ_URL)
    except zmq.error.ZMQError:
        print("SERVER COULD NOT START!")
        return

    locked = False
    while True:
        message = lock.recv()
        if message == b"LOCK" and not locked:
            locked = True
            lock.send(b"LOCKED")
        elif message == b"UNLOCK" and locked:
            locked = False
            lock.send(b"UNLOCKED")
        else:
            lock.send(b"FAILED")

class NoLock():
    """
    we also use a "no lock" case to compare performances.
    so we use this to ''fake'' lock api for no-lock case
    """
    def acquire(self):
        """
        acquire nothing
        """
        pass # pylint: disable=(unnecessary-pass)

    def release(self):
        """
        release nothing
        """
        pass # pylint: disable=(unnecessary-pass)

def worker_different_locks(test_type: str,
                           lock_name: str,
                           start_event: multiprocessing.synchronize.Event,
                           time_measure_queue: multiprocessing.Queue):
    """
    worker_different_locks function for multiprocessing performance tests

    Parameters
    ----------
    test_type : str
        test type
    lock_name : str
        name of the lock being used amongst all processes
    start_event : multiprocessing.synchronize.Event
        synchronization event to start all processes at the same time
    time_measure_queue : multiprocessing.Queue
        queue to store time measurements

    Raises
    ------
    ValueError
        if invalid test type has been used
    """
    result = None
    try:
        result = shared_memory.SharedMemory(name=RESULT_SHM_NAME)
        if test_type == "shmlock":
            lock = shmlock.ShmLock(lock_name,
                                   poll_interval=SHM_LOCK_POLL_INTERVAL,
                                   logger=log,
                                   track=False if sys.version_info >= (3, 13) else None)
        elif test_type  == "shmlock_with_resource_tracking":
            shmlock.init_custom_resource_tracking()
            lock = shmlock.ShmLock(lock_name,
                                   poll_interval=SHM_LOCK_POLL_INTERVAL,
                                   track=False if sys.version_info >= (3, 13) else None)
        elif test_type == "filelock":
            lock = filelock.FileLock(lock_name)
        elif test_type == "zmq":
            lock = ZmqLock(SHM_LOCK_POLL_INTERVAL)
        elif test_type == "no_lock":
            lock = NoLock()
        else:
            raise ValueError(f"Unknown test type {test_type}")

        time_measure = []

        # log.info("waiting for start event to be set")
        start_event.wait()

        for _ in range(NUM_RUNS):
            # for each run measure time for lock acquirement and release
            start = time.perf_counter()
            try:
                lock.acquire()
                current_value = struct.unpack_from("Q", result.buf, 0)[0]
                struct.pack_into("Q", result.buf, 0, current_value + 1)
            finally:
                lock.release()
            end = time.perf_counter()
            time_measure.append(end - start)

        # put data to queue
        time_measure_queue.put(time_measure)
        time_measure_queue.close()
    finally:
        if result is not None:
            result.close()

if __name__ == "__main__":

    log.info("Running %s", __file__)

    procs = []

    # for ''unique logging'' for process spawning
    if len(log_buffer) > 0:
        for key, value in log_buffer.items():
            # log level according to key
            for val in value:
                getattr(log, key)(val)

    START_EVENT = multiprocessing.Event()

    # NOTE that if this script is cancelled, the shared memory will not be freed
    RESULT = None
    try:
        RESULT = shared_memory.SharedMemory(name=RESULT_SHM_NAME, create=True, size=8)
        LOCK_NAME = "test_lock" # use the same lock for all processes
        server_proc = None

        for TEST_TYPE in ("no_lock",
                          "zmq",
                          "shmlock",
                          "shmlock_with_resource_tracking",
                          "filelock"):

            log.info("Running test type %s", TEST_TYPE)

            RESULT.buf[:] = bytearray(len(RESULT.buf[:]) * [0])

            if TEST_TYPE == "zmq":
                # zmq requires a server process, make daemon so that it gets destroyed
                # after main finishes
                server_proc = multiprocessing.Process(target=zmq_server, daemon=True)
                server_proc.start()
                time.sleep(1) # give it some time
                if not server_proc.is_alive():
                    log.error("zmq server (url %s) is not alive after 1s, cannot test qmz",
                              ZMQ_URL)
                    continue # continue with other tests nevertheless

            # queue to collect results
            TIME_MEASUREMENT_QUEUE = multiprocessing.Queue()
            for i in range(NUM_PROCESSES):
                proc = multiprocessing.Process(target=worker_different_locks,
                                               args=(TEST_TYPE,
                                                     LOCK_NAME,
                                                     START_EVENT,
                                                     TIME_MEASUREMENT_QUEUE,))
                procs.append(proc)
                proc.start()

            time.sleep(1) # give processes some time
            START_EVENT.set()

            # collect data from queue
            time_measures = []
            # NOTE that this blocks until all processes have finished
            for _ in range(NUM_PROCESSES):
                time_measures.extend(TIME_MEASUREMENT_QUEUE.get())

            for proc in procs:
                proc: multiprocessing.Process
                # be aware
                # https://docs.python.org/2/library/multiprocessing.html#programming-guidelines
                # "Joining processes that use queues"
                proc.join()


            mean = sum(time_measures) / len(time_measures)
            variance = sum((x - mean) ** 2 for x in time_measures) / len(time_measures)
            standard_deviation = variance ** 0.5

            final_res = struct.unpack_from("Q", RESULT.buf, 0)[0]

            # print results
            log.info("Test type %s:", TEST_TYPE)
            log.info("average time: %fs", mean)
            log.info("max time: %fs", max(time_measures))
            log.info("min time: %fs", min(time_measures))
            log.info("standard deviation: %fs", standard_deviation)

            if TEST_TYPE == "no_lock":
                log.info("Result buffer: %d (probably but not necessarily smaller than %d)\n\n",
                        final_res,
                        NUM_PROCESSES*NUM_RUNS)
            else:
                log.info("Result buffer: %d (should be %d)\n\n",
                         final_res,
                         NUM_PROCESSES*NUM_RUNS)
    finally:
        if RESULT is not None:
            RESULT.close()
            RESULT.unlink()

    # for some reason sometimes filelock artifacts remain
    try:
        os.remove(os.path.join(os.path.dirname(os.path.realpath(__file__)), LOCK_NAME))
    except FileNotFoundError:
        pass
