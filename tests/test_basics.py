"""
tests of basics (lock/release) of shmlock package
"""
from multiprocessing import shared_memory
import time
import unittest
import logging
import shmlock
import shmlock.shmlock_exceptions

class BasicsTest(unittest.TestCase):
    """
    test of basics of shmlock package

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

    def test_release_in_destructor(self):
        """
        test that the lock is released in the destructor
        """
        shm_name = str(time.time())
        lock1 = shmlock.ShmLock(shm_name)
        lock2 = shmlock.ShmLock(shm_name)

        self.assertTrue(lock1.acquire())

        # delete the lock
        del lock1

        try:
            # check that the lock can be acquired i.e. that the resource has been released
            # in the destructor of the lock
            self.assertTrue(lock2.acquire())
        finally:
            lock2.release()


    def test_lock_with_exception(self):
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        def test_func():
            with lock:
                raise RuntimeError("test exception")

        self.assertRaises(RuntimeError, test_func)
        try:
            self.assertTrue(lock.acquire()) # lock should be acquired again
        finally:                              # i.e. shm should not be blocked
            lock.release()

    def test_lock_release(self):
        """
        test the basics
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        self.assertTrue(lock.acquire())
        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockRuntimeError):
            lock.acquire() # already acquired for this lockect

        lock2 = shmlock.ShmLock(shm_name)
        self.assertFalse(lock2.acquire(timeout=1)) # acquired by other lock

        self.assertTrue(lock.release()) # release should be successful
        self.assertTrue(lock2.acquire()) # not should be acquirable

        self.assertTrue(lock2.release()) # check successful release

        # double release should return False
        self.assertFalse(lock.release())
        self.assertFalse(lock2.release())


        shm = None
        with self.assertRaises(FileNotFoundError, msg = f"shm with name {shm_name} could not be "\
                               "acquired, this means that it has not been properly "\
                               "released by the locks!"):
            # attach should fail because there is no shm to attach to
            shm = shared_memory.SharedMemory(name=shm_name)

        if shm is not None:
            # juse in case, make sure that there are never leaking resources
            shm.close()
            shm.unlink()

    def test_get_uuid_of_locking_lock(self):
        """
        test the get_uuid_of_locking_lock method
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)
        lock2 = shmlock.ShmLock(shm_name)

        # check that the uuid of the first lock is returned
        self.assertTrue(lock.acquire())
        self.assertEqual(lock.get_uuid_of_locking_lock(), lock.uuid)

        # switch acquiring locks
        lock.release()
        lock2.acquire()

        # check that the uuid of lock2 is returned
        self.assertEqual(lock2.get_uuid_of_locking_lock(), lock2.uuid)

        # check that the uuid of the locks is different
        self.assertNotEqual(lock.uuid, lock2.uuid)

    def test_logger(self):
        """
        test the logger; logs will not be visible but for code coverage we add them
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        logger = logging.getLogger("test_logger")

        for log in (logger, None,):
            lock = shmlock.ShmLock(shm_name, logger=log)

            # just check that they do not throw exceptions if no logger is set and with logger
            lock.info("test info")
            lock.debug("test debug")
            lock.warning("test warning")
            lock.warn("test warn")
            lock.error("test error")
            lock.exception("test exception")
            lock.critical("test critical")


if __name__ == "__main__":
    unittest.main(verbosity=2)
