"""
init tests of shmlock package
"""
import multiprocessing
import multiprocessing.synchronize

from multiprocessing import shared_memory
import sys
import time
import unittest
import shmlock
import shmlock.shmlock_exceptions


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
        obj = shmlock.ShmLock(shm_name, poll_interval=1)
        self.assertEqual(obj.name, shm_name)
        self.assertEqual(obj.poll_interval, 1)
        # internally should be a float
        self.assertTrue(isinstance(obj.poll_interval, float))
        # exit event should be automatically assigned
        self.assertTrue(isinstance(obj.get_exit_event(), multiprocessing.synchronize.Event))

        del obj
        # shared memory should be deleted thus attaching should fail
        with self.assertRaises(FileNotFoundError):
            shared_memory.SharedMemory(name=shm_name)

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
