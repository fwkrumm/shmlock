"""
init tests of shmlock package
"""
import multiprocessing
import threading
from multiprocessing import shared_memory
import sys
import time
import unittest
import shmlock
import shmlock.shmlock_exceptions
import shmlock.shmlock_config

class InitTest(unittest.TestCase):
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

    def test_init(self):
        """
        check if init works with default values
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name, poll_interval=1)
        self.assertEqual(lock.name, shm_name)
        self.assertEqual(lock.poll_interval, 1)
        # internally should be a float
        self.assertTrue(isinstance(lock.poll_interval, float))
        # exit event should be automatically assigned
        self.assertTrue(isinstance(lock.get_exit_event(), shmlock.shmlock_config.ExitEventMock))

        del lock
        # shared memory should be deleted thus attaching should fail
        with self.assertRaises(FileNotFoundError):
            shared_memory.SharedMemory(name=shm_name)

    def test_init_methods(self):
        """
        check that locked and acquired properties work correctly
        """
        shm_name = str(time.time())
        lock = shmlock.ShmLock(shm_name, poll_interval=1)
        self.assertFalse(lock.locked)
        self.assertFalse(lock.acquired)

        # acquire the lock
        self.assertTrue(lock.acquire(timeout=1))
        self.assertTrue(lock.locked)
        self.assertTrue(lock.acquired)

        # release the lock
        lock.release()
        self.assertFalse(lock.locked)
        self.assertFalse(lock.acquired)

    def test_event_types(self):
        """
        test if event types are correctly set
        """
        shm_name = str(time.time())

        for event in (multiprocessing.Event(), threading.Event(),):
            lock = shmlock.ShmLock(shm_name, exit_event=event)
            self.assertTrue(isinstance(lock.get_exit_event(), type(event)))
            lock.use_mock_exit_event()
            self.assertTrue(isinstance(lock.get_exit_event(), shmlock.shmlock_config.ExitEventMock))

    def test_shm_config_init(self):
        """
        version basic test for shm config class; check that init
        values are correctly set
        """
        uuid = shmlock.shmlock_uuid.ShmUuid()
        config = shmlock.shmlock_config.ShmLockConfig(
            name="test",
            poll_interval=1.0,
            exit_event=None,
            track=True,
            timeout=1.0,
            uuid=uuid,
            pid=1,
            description="description"
        )
        self.assertEqual(config.name, "test")
        self.assertEqual(config.poll_interval, 1.0)
        self.assertEqual(config.exit_event, None)
        self.assertEqual(config.track, True)
        self.assertEqual(config.timeout, 1.0)
        self.assertEqual(config.uuid, uuid)
        self.assertEqual(config.pid, 1)
        self.assertEqual(config.description, "description")


    def test_wrong_parameter_types(self):
        """
        test if wrong parameter types are caught
        """
        shm_name = str(time.time())

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            shmlock.ShmLock(shm_name, poll_interval=None)

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            shmlock.ShmLock(shm_name, logger=1)

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            shmlock.ShmLock(shm_name, exit_event=1)

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            shmlock.ShmLock(1)

    def test_no_zero_poll(self):
        """
        test if zero poll interval is caught. poll_interval == 0 is strongly discouraged since
        it will lead to high cpu usage and takes a long time. thus we prevent it explicitly.
        Test for int and float
        """
        shm_name = str(time.time())

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            shmlock.ShmLock(shm_name, poll_interval=0)

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            shmlock.ShmLock(shm_name, poll_interval=0.0)

    def test_no_negative_poll(self):
        """
        test if negative poll interval is caught
        """
        shm_name = str(time.time())
        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            shmlock.ShmLock(shm_name, poll_interval=-1)

    def test_empty_name(self):
        """
        test if empty name is caught
        """
        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            shmlock.ShmLock("")

    @unittest.skipUnless(sys.version_info < (3, 13), "test only for lower python versions")
    def test_track_for_too_low_version(self):
        shm_name = str(time.time())
        # this is not a valid test since the version is too low
        if sys.version_info < (3, 13):
            with self.assertRaises(ValueError):
                shmlock.ShmLock(shm_name, track=False)
        else:
            # should work fine
            l = shmlock.ShmLock(shm_name, track=False)
            self.assertTrue(l.acquire())

if __name__ == "__main__":
    unittest.main(verbosity=2)
