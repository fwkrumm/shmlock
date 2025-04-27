"""
tests concerning custom memory management/tracking
"""
import unittest
import logging
import multiprocessing
import os
from multiprocessing import shared_memory
import shmlock
from shmlock import shmlock_resource_tracking

# disable warnings for this test
shmlock.enable_disable_warnings(False)

LOCK_NAME = "test_resource_tracker"

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("TestLogger")

def worker(result_queue: multiprocessing.Queue):
    """
    create shared memory block and clean it up
    """
    shmlock.init_custom_resource_tracking()

    # we do not use the shared memory lock but an "ordinary" shared memory block since
    # we want to test the resource tracking
    _ = shared_memory.SharedMemory(name=LOCK_NAME)
    shmlock_resource_tracking.add_to_resource_tracker(LOCK_NAME)
    shmlock_resource_tracking.de_init_custom_resource_tracking()

    # check that after clean up resource tracker is not initialized any more
    if shmlock_resource_tracking.is_resource_tracker_initialized():
        # should lead to test failure
        result_queue.put(False)
    else:
        result_queue.put(True)

class CustomResourceTrackingTest(unittest.TestCase):
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

    def setUp(self):
        """
        set up before each test;
        always check that lock is acquirable
        NOTE that this if course will not work if tests are executed in parallel
        """
        lock = shmlock.ShmLock(LOCK_NAME)
        self.assertTrue(lock.acquire(timeout=1), "lock could not be acquired initially")
        self.assertTrue(lock.release())

    def test_resoutce_tracker_weak_ref_destruction(self):
        """
        test whether weak references are correctly destroyed
        """
        # create tracker and add a referece
        tracker = shmlock_resource_tracking.ResourceTrackerSingleton()
        tracker.add_shared_memory(LOCK_NAME)
        self.assertEqual(len(tracker.shared_memories), 1)

        # delete the tracker
        del tracker
        # now create the tracker (singleton) again and check that no shared memory is tracked
        # if the tracker is not created as weakref instance, the singleton properties
        # will prevent the deletion of the tracker member variables
        tracker = shmlock_resource_tracking.ResourceTrackerSingleton()
        self.assertEqual(len(tracker.shared_memories), 0)

    # @unittest.skip("skip test_custom_resource_tracking")
    def test_custom_resource_tracking(self):
        """
        test custom resource tracking
        """
        log.info("Running test_custom_resource_tracking")

        # enable resource tracking
        shmlock.init_custom_resource_tracking()

        lock = shmlock.ShmLock(LOCK_NAME)
        self.assertTrue(shmlock_resource_tracking.is_resource_tracker_initialized(),
                        "resource tracker is not initialized although it should.")

        # acquire lock and check that it correctly was added to the list
        self.assertTrue(lock.acquire(), "lock could not be acquired initially")
        self.assertTrue(lock.name in shmlock_resource_tracking.get_registered_shared_memories(),\
            f"lock name not in {shmlock_resource_tracking.get_registered_shared_memories()}")
        self.assertTrue(len(shmlock_resource_tracking.get_registered_shared_memories()) == 1,\
             "shmlock.LOCKS_ACQUIRED does not contain exactly one "\
             f"element -> {shmlock_resource_tracking.get_registered_shared_memories()}")

        # release lock and check that it has been removed from LOCKS_ACQUIRED list
        self.assertTrue(lock.release())
        self.assertTrue(len(shmlock_resource_tracking.get_registered_shared_memories()) == 0,\
            "shmlock.LOCKS_ACQUIRED is not empty -> "\
            f"{shmlock_resource_tracking.get_registered_shared_memories()}")

        # assure that resource tracking is deactivated again for this process
        shmlock.de_init_custom_resource_tracking()

    def test_missed_resource(self):
        """
        we try to test the case where a resource is not cleaned up properly.
        this test only makes sense for posix systems since the unlinking is only
        defined for such systems (afaik)
        """
        shm = shared_memory.SharedMemory(name=LOCK_NAME, create=True, size=10)
        result = multiprocessing.Queue()
        process = multiprocessing.Process(target=worker, args=(result,))
        process.start()
        res = result.get() # wait for result
        process.join()
        shm.close()

        self.assertTrue(res, "resource tracking did not initialized properly!")

        # unlink is currently only defined for posix systems
        if os.name == "posix":
            # the unlinking should have been done by the worker process
            # and thus the shared memory should not exist any more
            with self.assertRaises(FileNotFoundError):
                shm.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
