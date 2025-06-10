"""
tests whether the exit event is working as intended
"""
import unittest
import time
import threading
import multiprocessing
import logging
import shmlock

LOCK_NAME = "test_exit_event_lock_shm"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("TestLogger")


class ExitEventTest(unittest.TestCase):
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

    @classmethod
    def setUpClass(cls):
        """
        set up class method
        """
        obj = shmlock.ShmLock(LOCK_NAME)
        cls().assertTrue(obj.acquire(timeout=1), "lock could not be acquired initially i.e. "\
            "it is locked by another process. Tests cannot run.")

    # @unittest.skip("skip for now")
    def test_set_exit_event(self):
        """
        check arguments with lock function and timeout None
        """
        log.info("Running test_set_exit_event")
        exit_event = multiprocessing.Event()
        lock = shmlock.ShmLock(LOCK_NAME, exit_event=exit_event)
        exit_event.set()
        self.assertFalse(lock.acquire(), "lock could be acquired although exit event is set")

    def test_set_exit_event_with_thread(self):
        """
        set exit event with thread
        """
        log.info("Running set_exit_event_with_thread")
        exit_event = multiprocessing.Event()
        def worker():
            lock = shmlock.ShmLock(LOCK_NAME, exit_event=exit_event)
            lock_ = shmlock.ShmLock(LOCK_NAME)
            self.assertTrue(lock_.acquire())
            self.assertFalse(lock.acquire()) # exit event will be set in and thus
                # acquirement will be stopped. otherwise this would wait forever
                # (because of default timeout=None)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        time.sleep(1)
        exit_event.set() # let thread die
        thread.join(timeout=2) # give thread some time to finish
        self.assertFalse(thread.is_alive(), "thread is still alive")


if __name__ == "__main__":
    unittest.main(verbosity=2)
