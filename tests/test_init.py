"""
init tests of shmlock package
"""
import time
import unittest
from multiprocessing import shared_memory
import shmlock
from shmlock import shmlock_resource_tracking


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
        del obj
        # shared memory should be deleted thus attaching should fail
        with self.assertRaises(FileNotFoundError):
            shared_memory.SharedMemory(name=shm_name)

    def test_wrong_parameter_types(self):
        """
        test if wrong parameter types are caught
        """
        with self.assertRaises(ValueError):
            shmlock.ShmLock("some_name", poll_interval=None)

        with self.assertRaises(ValueError):
            shmlock.ShmLock("some_name", logger=1)

        with self.assertRaises(ValueError):
            shmlock.ShmLock("some_name", exit_event=1)

        with self.assertRaises(ValueError):
            shmlock.ShmLock(1)

    def test_unique_custom_resource_tracker(self):
        """
        test if resource tracking is singleton
        """
        tracker1 = shmlock_resource_tracking.ResourceTrackerSingleton()
        tracker2 = shmlock_resource_tracking.ResourceTrackerSingleton()
        self.assertTrue(id(tracker1) == id(tracker2), "ResourceTrackerSingleton should be "\
            "singleton. Only ine id should exist per process")

    def test_no_zero_poll(self):
        """
        test if zero poll interval is caught. poll_interval == 0 is strongly discouraged since
        it will lead to high cpu usage and takes a long time. thus we prevent it explicitly.
        Test for int and float
        """
        with self.assertRaises(ValueError):
            shmlock.ShmLock("some_name", poll_interval=0)

        with self.assertRaises(ValueError):
            shmlock.ShmLock("some_name", poll_interval=0.0)

    def test_no_negative_poll(self):
        """
        test if negative poll interval is caught
        """
        with self.assertRaises(ValueError):
            shmlock.ShmLock("some_name", poll_interval=-1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
