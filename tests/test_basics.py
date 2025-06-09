"""
tests of basics (lock/release) of shmlock package
"""
from multiprocessing import shared_memory
import time
import gc
import unittest
import logging
import shmlock
import shmlock.shmlock_exceptions
from shmlock.shmlock_uuid import ShmUuid

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
        gc.collect() # force garbage collection to assure call of the destructor

        try:
            # check that the lock can be acquired i.e. that the resource has been released
            # in the destructor of the lock
            self.assertTrue(lock2.acquire())
        finally:
            lock2.release()

    def test_properties(self):
        """
        test some properties
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        self.assertTrue(lock.acquire())
        self.assertTrue(lock.acquired)

        lock.description = "test description"
        self.assertEqual(lock.description, "test description")

    def test_lock_with_exception(self):
        """
        test that lock is released even if an exception is raised
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        def test_func():
            with lock:
                raise RuntimeError("test exception")

        self.assertRaises(RuntimeError, test_func)
        try:
            self.assertTrue(lock.acquire()) # lock should be acquired again
        finally:                            # i.e. shm should not be blocked
            lock.release()

    def test_reentrant_lock(self):
        """
        test that the lock is reentrant
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        with lock: # __enter__
            with lock.lock(): # contextmanager
                # this should not block
                pass
            self.assertTrue(lock.acquired)

        self.assertFalse(lock.acquired) # lock should be released now

        # test force parameter. NOTE That this should not be used in production code!
        with lock:
            with lock:
                lock.release(force=True)
            self.assertFalse(lock.acquired) # lock should be released now

        self.assertFalse(lock.acquired) # lock should still be released

    def test_lock_release(self):
        """
        test the basics
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        self.assertTrue(lock.acquire())

        # due to reentrant lock, this should not block and also return True
        self.assertTrue(lock.acquire())

        lock2 = shmlock.ShmLock(shm_name)

        # check expected behavior if lock already acquired
        self.assertFalse(lock2.acquire(timeout=1)) # positive timeout
        self.assertFalse(lock2.acquire(timeout=False)) # timeout False

        with lock2(timeout=0.1) as res:
            self.assertFalse(res)


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

    def test_debug_get_uuid_of_locking_lock(self):
        """
        test the debug_get_uuid_of_locking_lock method
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)
        lock2 = shmlock.ShmLock(shm_name)

        # no shm acquired yet
        self.assertIsNone(lock.debug_get_uuid_of_locking_lock())

        # check that the uuid of the first lock is returned
        self.assertTrue(lock.acquire())
        self.assertEqual(lock.debug_get_uuid_of_locking_lock(), lock.uuid)

        # switch acquiring locks
        self.assertTrue(lock.release())
        self.assertTrue(lock2.acquire())

        # check that the uuid of lock2 is returned
        self.assertEqual(lock2.debug_get_uuid_of_locking_lock(), lock2.uuid)

        # check that the uuid of the locks is different
        self.assertNotEqual(lock.uuid, lock2.uuid)

    def test_logger(self):
        """
        test the logger; logs will not be visible but for code coverage we add them
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        logger = logging.getLogger("test_logger")
        logger.setLevel(logging.NOTSET)

        for log in (logger, None,):
            lock = shmlock.ShmLock(shm_name, logger=log)

            # just check that they do not throw exceptions if no logger is set and with logger
            lock.info("base logger test info")
            lock.debug("base logger test debug")
            lock.warning("base logger test warning")
            lock.warn("base logger test warn")
            lock.error("base logger test error")
            lock.exception("base logger test exception")
            lock.critical("base logger test critical")

    def test_repr(self):
        """
        test the repr method
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        # check that the repr method does not throw an exception
        self.assertIsNotNone(repr(lock))

    def test_uuid_methods(self):
        """
        test uuid conversion methods and representation method existence
        """
        uuid = ShmUuid()
        uuid_bytes = uuid.uuid_bytes
        uuid_str = uuid.uuid_str
        self.assertEqual(uuid_bytes, ShmUuid.string_to_bytes(uuid_str))
        self.assertEqual(uuid_str, ShmUuid.byte_to_string(uuid_bytes))
        self.assertIsNotNone(repr(uuid))

    def test_exceptions_at_release_within_contextmanager(self):
        """
        test that exceptions are raised if release is called within the context manager
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name)

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockRuntimeError):
            with lock.lock():
                lock.release()

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockRuntimeError):
            with lock:
                lock.release()

if __name__ == "__main__":
    unittest.main(verbosity=2)
