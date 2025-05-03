"""
This file is designed to test the resource tracker fix.

How to use this test file:
USE_RESOURCE_TRACKER_FIX = False

Execute this script. The first instance (script execution) will block if you hit Ctrl+C
(KeyBoardInterrupt). Please do not spam the latter (might lead to leaked resources).

If you run a single instance and terminate it with Ctrl+C, all is fine.
The rest of the shared memory will be created and then released (closed and unlinked).

If you run the first instance until it enters the loop and then run the script
 in a second terminal (second instance), you will get a leaked resource warning at the end:

UserWarning: resource_tracker: There appear to be 3 leaked shared_memory objects to
 clean up at shutdown.


This happens because the second instance did not explicitly
 unlink the test shared memory blocks. However, we did not want that since the first
 (main) instance created the blocks and is supposed to unlink them.

If you now terminate the first loop, you also get:

FileNotFoundError: [Errno 2] No such file or directory: '/test_shared_memory'
UserWarning: resource_tracker: '/yet_another': [Errno 2]
 No such file or directory: '/yet_another'
UserWarning: resource_tracker: '/another_shared_memory': [Errno 2]
 No such file or directory: '/another_shared_memory'
UserWarning: resource_tracker: '/test_shared_memory': [Errno 2]
 No such file or directory: '/test_shared_memory'


 This happened because the resource tracker of the second instance unregistered
 the shared memories. For further details, please check the README.md in the root directory.

USE_RESOURCE_TRACKER_FIX = True

All errors/warnings should vanish since we patch the resource tracker to not track the
 specified shared memory blocks. We use a pattern since we may not want to disable
the resource tracker for all shared memory blocks.


"""
# pylint:disable=(duplicate-code) # because of import magic below
from multiprocessing import shared_memory
import os
import sys
import time
import logging

try:
    import shmlock
except ImportError:
    print("trying to import from root directory")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    new_path = os.path.join(current_dir, "..", "..")
    sys.path.append(new_path)
    import shmlock # pylint:disable=(wrong-import-position)


# set this to True to enable the fix, set to False to see the errors
USE_RESOURCE_TRACKER_FIX = True

# shm to check which instane is the first one to be executed
REF_MASTER_SHM_MANE = "REF_MASTER_SHM_NAME"

# test shm names
NAME_OF_TEST_SHM_1 = "test_shared_memory"
NAME_OF_TEST_SHM_2 = "another_shared_memory"
NAME_OF_TEST_SHM_3 = "yet_another"

LOG = logging.getLogger(__name__)
logging.basicConfig(level="INFO")

if __name__ == "__main__":

    # this example does only make sense on posix systems
    if os.name != "posix":
        LOG.error("the resource tracker is only used on posix systems.")
        sys.exit(1)

    shm = None

    try:
        shm = shared_memory.SharedMemory(create=True,
                                         name=REF_MASTER_SHM_MANE,
                                         size=1)
    except FileExistsError:
        assert shm is None


    if USE_RESOURCE_TRACKER_FIX and sys.version_info < (3, 13):
        # remove shared memory names by pattern from resource tracker
        # for 3.13 and above we use the track parameter below
        shmlock.remove_shm_from_resource_tracker("shared_memory")
        shmlock.remove_shm_from_resource_tracker("yet_another")

    shms = []

    if shm is not None:
        try:
            if sys.version_info < (3, 13):
                shms.append(shared_memory.SharedMemory(create=True,
                                                    name=NAME_OF_TEST_SHM_1,
                                                    size=1))
                shms.append(shared_memory.SharedMemory(create=True,
                                                    name=NAME_OF_TEST_SHM_2,
                                                    size=1))
                shms.append(shared_memory.SharedMemory(create=True,
                                                    name=NAME_OF_TEST_SHM_3,
                                                    size=1))
            else:
                # python 3.13 and above
                shms.append(shared_memory.SharedMemory(create=True,
                                                    name=NAME_OF_TEST_SHM_1,
                                                    size=1,
                                                    track=False))
                shms.append(shared_memory.SharedMemory(create=True,
                                                    name=NAME_OF_TEST_SHM_2,
                                                    size=1,
                                                    track=False))
                shms.append(shared_memory.SharedMemory(create=True,
                                                    name=NAME_OF_TEST_SHM_3,
                                                    size=1,
                                                    track=False))
        except FileExistsError:
            # if the script ended appruptly, the shared memory might still exist.
            LOG.error("Some shms could not be created. will try to close and unlink all ahms. "\
                      "please restart script afterwards.")
            shms = []
            for shm_name in (NAME_OF_TEST_SHM_1, NAME_OF_TEST_SHM_2, NAME_OF_TEST_SHM_3):
                try:
                    test_shm = shared_memory.SharedMemory(name=shm_name)
                    test_shm.close()
                    test_shm.unlink()
                except FileNotFoundError:
                    # not a problem, just a clean up, some might not exist
                    pass
    else:
        # second instance -> only append
        shms.append(shared_memory.SharedMemory(name=NAME_OF_TEST_SHM_1))
        shms.append(shared_memory.SharedMemory(name=NAME_OF_TEST_SHM_2))
        shms.append(shared_memory.SharedMemory(name=NAME_OF_TEST_SHM_3))

    # blocking loop for first (main) instance
    if shm is not None:
        LOG.info("Entering loop ... hit ctrl+c one time after second instance (i.e. "\
                 "run this script in a second terminal) ran.")
    while shm is not None and len(shms) > 0:
        # block so that another instance can run
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            LOG.info("cleaning up and exiting")
            if USE_RESOURCE_TRACKER_FIX is True:
                LOG.info("Since USE_RESOURCE_TRACKER_FIX is True, no errors should be shown.")
            else:
                LOG.info("Since USE_RESOURCE_TRACKER_FIX is False, errors/warnings should be "\
                         "shown if the second instance has run before.")
            shm.close()
            shm.unlink()
            break

    # close and unlink test shared memory files
    for test_shm in shms:
        LOG.info("closing %s", test_shm.name)
        test_shm: shared_memory.SharedMemory
        test_shm.close()
        if shm is not None:
            # only master node should call unlink
            LOG.info("unlinking %s", test_shm.name)
            test_shm.unlink()
