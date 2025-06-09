"""
rather an integration tests -> run multiple processes and check if the shared memory lock works

an alternative for patching resource tracker for tests might be

https://github.com/vllm-project/vllm/pull/5512/commits/af0e16c70572c222e747a64f637b7c795f884334

related to
https://github.com/vllm-project/vllm/issues/5468
https://github.com/vllm-project/vllm/pull/5512

"""
import multiprocessing
from multiprocessing import shared_memory
import multiprocessing.synchronize
import unittest
import os
import sys
import time
import struct
import threading
import logging
import shmlock

NUM_PROCESSES = 15
NUM_RUNS = 2000
LOCK_NAME = "shm_lock_test_lock_shm"
RESULT_SHM_NAME = "shm_lock_result_shm"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("TestLogger")

# log buffer since we have to set some settings globally but we do not want to have them
# spammed due to multiprocess spawning
log_buffer = {"info": [], "error": []}

if os.name == "posix":
    if sys.version_info >= (3, 12, 0):
        # for 3.12.5 there is a deprecation warning concerning fork method and threads.
        # so we set it to spawn here
        try:
            multiprocessing.set_start_method("spawn", force=True)
            log_buffer.get("info").\
                append("Setting method to spawn. Because of deprecation warning.")
        except RuntimeError as exc:
            log_buffer.get("error").append(f"Could not set start method to spawn: {exc}")

    # otherwise it spams KeyErrors since resource tracker also tracks shm of other processes
    # and complains that it has not been unlinked because it was unlinked by another process
    if sys.version_info < (3, 13):
        # NOTE that this is not necessary for python 3.13 and above since there is the track
        # parameter to deactivate tracking
        shmlock.remove_shm_from_resource_tracker("shm_lock")
        log_buffer.get("info").append("Removed shared memory from resource tracker.\n\n")
else:
    log_buffer.get("info").append("Not removing shared memory from resource tracker\n\n")

class ArgumentsCollector: # pylint: disable=too-few-public-methods
    """
    just a little helper class to collect arguments for multiprocessing tests
    """

    def __init__(self):
        """
        init all with None, publish methods set afterwards manually

        start event for synchronized start
        use_lock_function to specify whether use lock function (contextmanager)
            or __enter__ and __exit__
        timeout for lock acquirement
        failed_acquire_queue to store failed acquirements
        poll_interval for lock
        time_measure_queue to store time measurements
        """
        self.start_event = None
        self.use_lock_function = None
        self.timeout = None
        self.failed_acquire_queue = None
        self.poll_interval = None
        self.time_measure_queue = None


def worker(arg_collector: ArgumentsCollector):
    """
    worker function for multiprocessing tests

    Parameters
    ----------
    arg_collector : ArgumentsCollector
        object of argument collector helper class containing
        all necessary arguments for the worker function
    """

    start_event : multiprocessing.synchronize.Event = arg_collector.start_event
    use_lock_function : bool = arg_collector.use_lock_function
    timeout : float = arg_collector.timeout
    failed_acquire_queue : multiprocessing.Queue = arg_collector.failed_acquire_queue
    poll_interval : float = arg_collector.poll_interval
    time_measure_queue : multiprocessing.Queue = arg_collector.time_measure_queue

    start_event.wait() # to synchronize start of all processes
    shm = shared_memory.SharedMemory(name=RESULT_SHM_NAME)
    if poll_interval is not None:
        obj = shmlock.ShmLock(LOCK_NAME,
                              poll_interval=poll_interval,
                              track=False if sys.version_info >= (3, 13) else None)
    else:
        obj = shmlock.ShmLock(LOCK_NAME, track=False if sys.version_info >= (3, 13) else None)

    time_measurement = []
    failed_acquirements = 0

    for _ in range(NUM_RUNS):
        # with lock increment result shared memory value each run
        start_time = time.perf_counter()
        if use_lock_function:
            with obj.lock(timeout=timeout) as res:
                if res:
                    current_value = struct.unpack_from("Q", shm.buf, 0)[0]
                    struct.pack_into("q", shm.buf, 0, current_value + 1)
                else:
                    failed_acquirements+=1
        else:
            with obj(timeout=timeout) as res:
                if res:
                    current_value = struct.unpack_from("Q", shm.buf, 0)[0]
                    struct.pack_into("q", shm.buf, 0, current_value + 1)
                else:
                    failed_acquirements+=1
        end_time = time.perf_counter()
        time_measurement.append(end_time - start_time)

    # be aware https://docs.python.org/2/library/multiprocessing.html#programming-guidelines
    # "Joining processes that use queues"; should be adapted here!
    # at the moment we might miss some values here; but it is not critical for the test
    failed_acquire_queue.put_nowait(failed_acquirements)
    time_measure_queue.put_nowait(time_measurement)
    # clean up
    del obj
    shm.close()
    del shm

class FunctionalTest(unittest.TestCase):
    """
    init tests of shmlock package

    Parameters
    ----------
    unittest : _type_
        _description_
    """

    def __init__(self, *args, **kwargs):
        """
        test init method
        """
        super().__init__(*args, **kwargs)
        self.result_shm: shared_memory.SharedMemory = None

        self.args: ArgumentsCollector = None

        self.failure_count_queue = multiprocessing.Queue()
        self.time_measurement_queue = multiprocessing.Queue()

        self.use_processes = None

    @classmethod
    def setUpClass(cls):
        """
        set up class method
        """
        obj = shmlock.ShmLock(LOCK_NAME, track=False if sys.version_info >= (3, 13) else None)
        cls().assertTrue(obj.acquire(timeout=1), "lock could not be acquired initially i.e. "\
            "it is locked by another process. Tests cannot run.")

    def tearDown(self):
        """
        tear down i.e. release shared memory
        """
        self.result_shm.close()
        self.result_shm.unlink()
        self.result_shm = None

    @classmethod
    def tearDownClass(cls):
        """
        tear down class method
        """
        if cls().result_shm is not None:
            cls().result_shm.close()
            cls().result_shm.unlink()
            cls().result_shm = None

    def setUp(self):
        """
        set up i.e. create result shared memory for testing
        """
        try:
            self.result_shm = shared_memory.SharedMemory(name=RESULT_SHM_NAME, create=True, size=8)
        except FileExistsError:
            # might happen if you did not clean up properly
            self.result_shm = shared_memory.SharedMemory(name=RESULT_SHM_NAME)
            # set buffer to zero
            self.result_shm.buf[:] = b"\x00" * len(self.result_shm.buf)
        self.args = ArgumentsCollector()
        self.args.time_measure_queue = self.time_measurement_queue
        self.args.failed_acquire_queue = self.failure_count_queue

    # @unittest.skip("skip for now")
    def test_lock_function_timeout_none(self):
        """
        check arguments with lock function and timeout None
        """
        log.info("Running test_lock_function_timeout_none")
        self.use_processes = True
        self.args.use_lock_function = True
        self.execute()

    # @unittest.skip("skip for now")
    def test_timeout(self):
        """
        check arguments with lock function and timeout minimal so that acquirement of
        lock will fail a couple of times (probably, not deterministic, abusing unit testing here)
        """
        # NOTE that the first parameter could also be False (using locking function or not)
        # functionally this results in the same internal function call of the shared memory lock
        log.info("Running test_timeout")
        self.use_processes = True
        self.args.use_lock_function = True
        self.args.timeout = 0.001
        self.execute()

    # @unittest.skip("skip for now")
    def test_wo_lock_function_timeout_none(self):
        """
        check arguments without lock function and timeout None
        """
        log.info("Running test_wo_lock_function_timeout_none")
        self.use_processes = True
        self.args.use_lock_function = False
        self.execute()

    #
    # threading
    #

    # @unittest.skip("skip for now")
    def test_lock_function_timeout_none_as_threads(self):
        """
        check arguments with lock function and timeout None
        """
        log.info("Running test_lock_function_timeout_none_as_threads")
        self.use_processes = False
        self.args.use_lock_function = True
        self.execute()

    # @unittest.skip("skip for now")
    def test_timeout_as_threads(self):
        """
        check arguments with lock function and timeout minimal so that acquirement of
        lock will fail a couple of times (probably, not deterministic, abusing unit testing here)
        """
        # NOTE that the first parameter could also be False (using locking function or not)
        # functionally this results in the same internal function call of the shared memory lock
        log.info("Running test_timeout_as_threads")
        self.use_processes = False
        self.args.use_lock_function = True
        self.args.timeout = 0.001
        self.execute()

    # @unittest.skip("skip for now")
    def test_wo_lock_function_timeout_none_as_threads(self):
        """
        check arguments without lock function and timeout None
        """
        log.info("Running test_wo_lock_function_timeout_none_as_threads")
        self.use_processes = False
        self.args.use_lock_function = False
        self.execute()

    def test_000_log(self):
        """
        HACK to assure unique logging despite multiprocessing spawn method
        make sure that this test_* is alphabetically the first one
        """
        if len(log_buffer) > 0:
            log.info(">> This ''test'' is only for logging uniquely despite process spawning. "\
                "The content logged here holds true for ALL test cases. Log buffer content:\n")
            for key, value in log_buffer.items():
                # log according to key
                for val in value:
                    getattr(log, key)(val)

    def execute(self):
        """
        execute tests with given arguments; basically just a helper function to reduce
        code repetitions
        """
        self.assertEqual(struct.unpack_from("Q", self.result_shm.buf, 0)[0], 0)

        start_event = multiprocessing.Event()
        self.args.start_event = start_event

        processes = []

        for _ in range(NUM_PROCESSES):
            if self.use_processes:
                processes : list[multiprocessing.Process]
                processes.append(multiprocessing.Process(target=worker,
                                                         args=(self.args,),
                                                         daemon=True))
            else:
                processes: list[threading.Thread]
                processes.append(threading.Thread(target=worker,
                                                  args=(self.args,),
                                                  daemon=True))

        for process in processes:
            process.start()

        time.sleep(1) # wait a little bit to make sure all processes are started
        start_event.set() # make sure everything starts at the same time

        not_acquired = 0

        # NOTE that this blocks until all processes have finished
        for _ in range(NUM_PROCESSES):
            not_acquired += self.failure_count_queue.get()

        if self.args.timeout is None or self.args.timeout == 0:
            self.assertEqual(not_acquired, 0,
                             "timeout is None but lock could not be acquired. "\
                             "this should not happen!")

        if not_acquired > 0:
            # should happen for tests with (small) timeout
            log.info("not acquired (approx): %s/%s for this specific test case which makes %s%%.",
                     not_acquired,
                     NUM_PROCESSES * NUM_RUNS,
                     not_acquired/(NUM_PROCESSES * NUM_RUNS) * 100)


        time_measures = []
        # NOTE that this blocks until all processes have finished
        for _ in range(NUM_PROCESSES):
            time_measures.extend(self.time_measurement_queue.get())

        for process in processes:
            # join processes
            # be aware
            # https://docs.python.org/2/library/multiprocessing.html#programming-guidelines
            # "Joining processes that use queues"
            process.join()

        log.info("Average time per run (lock/write/release): %s ms",
                 sum(time_measures) / len(time_measures) * 1000)

        # check if each process incremented exactly one time per run
        self.assertEqual(struct.unpack_from("Q", self.result_shm.buf, 0)[0],
                         NUM_PROCESSES * NUM_RUNS - not_acquired)

        # check that lock shared memory is released at the end
        with self.assertRaises(FileNotFoundError):
            shared_memory.SharedMemory(name=LOCK_NAME)


if __name__ == "__main__":
    unittest.main(verbosity=2)
