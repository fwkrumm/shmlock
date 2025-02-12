# Readme

## Table of Contents

- [About](#about)
- [Pros and Cons: When to Use This Module and When Not To](#pros-and-cons-when-to-use-this-module-and-when-not-to)
- [Installation](#installation)
- [Quick Dive](#quick-dive)
- [Examples](#examples)
- [Troubleshooting and Resource Tracking](#troubleshooting-and-resource-tracking)
- [ToDos](#todos)



---
<a name="about"></a>
## About

Feel free to provide constructive feedback, suggestions, or feature requests. Thank you.

This module is an inter-process lock implementation that does not require passing around any objects.
The lock can be used in multiple terminals or consoles by using the same name identifier.
Its underlying mechanism uses the multiprocessing.shared_memory module.

---
<a name="pros-and-cons-when-to-use-this-module-and-when-not-to"></a>
## Pros and Cons: When to Use This Module and When Not To

| When to Use | When Not to Use |
|-------------|-----------------|
| You want a lock without passing lock objects around | You do not want a lock that uses a polling interval (i.e. a sleep interval) |
| You need a simple locking mechanism | You require very high performance and a large number of acquisitions |
| You want to avoid file-based or server-client-based locks (like filelock, Redis, pyzmq, etc.) | You are not comfortable using shared memory as a lock mechanism |
| You do not want the lock to add dependencies to your project |  |


So if you chose to use this module it is best to keep the number of synchronized accesses not too high.

---
<a name="installation"></a>
## Installation

This module itself has no additional dependencies. There are multiple ways to install this module:

1. Install directly from the repository:
`pip install git+https://github.com/NotAvailable-EUR/shmlock@master`

2. Clone this repository and install it from the local files via pip:
    ```
    git clone https:/github.com/NotAvailable-EUR/shmlock
    cd shmlock
    pip install . -r requirements.txt
    ```

    Note that `-r requirements.txt` is only necessary if you want to run the tests and examples. The module itself does not have additional requirements apart from standard modules.

---
<a name="quick-dive"></a>
## Quick Dive

For further examples please check out the [Examples](#examples) section.
For the sake of completeness: **Do not** share a lock among threads. Each thread should use its own lock. However, typically, you would not use this lock implementation to synchronize threads within the same process. Instead, you would use the more efficient `threading.Lock()`.


```python
import shmlock

# lock name should only be used by locks and not any other shared memory
# if you want to use the lock in any other process, just use the same name
lock = shmlock.ShmLock("shm_lock")

#
# to apply the lock, use one of the following a), b), c)
#

# a)
with lock:
    # your code here
    pass

# b)
with lock.lock():
    # your code here
    pass

# c)
lock.acquire()
# your code here
lock.release()

#
# if you want a larger poll interval
#
lock = shmlock.ShmLock("shm_lock", poll_interval=1.0)

#
# if you want a timeout (NOTE that you also could also use lock.lock(...) or lock.acquire(...))
#
with lock(timeout=1) as success:
    if success:
        # your code
        pass
    else:
        # sadness i.e. lock could not be acquired after specified timeout
        pass

#
# if you want a timeout and the world to know about the failed acquirement:
#
with lock(timeout=1, throw=True):
    # your code here; if acquirement fails, TimeoutError is raised
    pass

```

---
<a name="examples"></a>
## Examples

There are examples that demonstrate the usage in more detail. Note that the requirements from the `requirements.txt` file are required for some of the examples.

### ./examples/multiple_terminals/run_multiple.py

Simply execute this file from different consoles and experiment with the global variable:

```python
USE_LOCK = True
```

Each instance will attempt to increment the value stored in a shared memory, the name of which is defined by `RESULT_SHM_NAME` in the file.

If `USE_LOCK` is set to `True` (default), the lock is enabled, and the output should resemble the following (depending on the OS, and the chosen number of `RUNS` and `DELAY_FOR_LOCKS` in the example):

If the latter is True (default) the lock is enabled and the output should be something like (depending on OS, and chosen number of `RUNS` and `DELAY_FOR_LOCKS` in the example)

![multiple_ok](./docs/assets/example_multiple_ok.png)

If you now try the same with:

```python
USE_LOCK = False
```

you will (non-deterministically) get

![multiple_nok](./docs/assets/example_multiple_nok.png)

This happens if a race condition occurs, i.e., one instance overwrote the value already extracted by another instance before it could increment and store the value. This does not happen if the locking mechanism is used.

### ./examples/performance_analysis/run_perf.py

This file can be used to test the performance of different locking mechanisms. Currently, this includes "no lock", zmq, shmlock, shmlock (with resource tracking), and filelock.

After executing `python run_perf.py`, you should get an output that looks approximately like this:


```
INFO:PerformanceLogger:Running test type no_lock
INFO:PerformanceLogger:Test type no_lock:
INFO:PerformanceLogger:average time: 0.000001s
INFO:PerformanceLogger:max time: 0.000600s
INFO:PerformanceLogger:min time: 0.000001s
INFO:PerformanceLogger:standard deviation: 0.000009s
INFO:PerformanceLogger:Result buffer: 2902 (probably smaller than 15000)


INFO:PerformanceLogger:Running test type zmq
INFO:PerformanceLogger:Test type zmq:
INFO:PerformanceLogger:average time: 0.003169s
INFO:PerformanceLogger:max time: 0.590404s
INFO:PerformanceLogger:min time: 0.000361s
INFO:PerformanceLogger:standard deviation: 0.022007s
INFO:PerformanceLogger:Result buffer: 15000 (should be 15000)


INFO:PerformanceLogger:Running test type shmlock
INFO:PerformanceLogger:Test type shmlock:
INFO:PerformanceLogger:average time: 0.000412s
INFO:PerformanceLogger:max time: 0.392681s
INFO:PerformanceLogger:min time: 0.000045s
INFO:PerformanceLogger:standard deviation: 0.008226s
INFO:PerformanceLogger:Result buffer: 15000 (should be 15000)


INFO:PerformanceLogger:Running test type shmlock_with_resource_tracking
INFO:PerformanceLogger:Test type shmlock_with_resource_tracking:
INFO:PerformanceLogger:average time: 0.000499s
INFO:PerformanceLogger:max time: 0.412015s
INFO:PerformanceLogger:min time: 0.000046s
INFO:PerformanceLogger:standard deviation: 0.009216s
INFO:PerformanceLogger:Result buffer: 15000 (should be 15000)


INFO:PerformanceLogger:Running test type filelock
INFO:PerformanceLogger:Test type filelock:
INFO:PerformanceLogger:average time: 0.006232s
INFO:PerformanceLogger:max time: 0.645011s
INFO:PerformanceLogger:min time: 0.000296s
INFO:PerformanceLogger:standard deviation: 0.030970s
INFO:PerformanceLogger:Result buffer: 15000 (should be 15000)
```

The first test does not synchronize anything. This is, of course, the fastest; however, the counter is often not incremented properly.

The second test uses pyzmq (https://pypi.org/project/pyzmq/), the third test uses the shared memory lock implemented in this project, the fourth test uses the shared memory lock with experimental custom resource tracking (to check for performance issues), and the fifth test uses filelock (https://pypi.org/project/filelock/).

Note that the results depend on the OS and hardware. The "average time" refers to the time required for a single lock acquisition, result value increment, and lock release:


```python
start = time.perf_counter()
try:
    lock.acquire()
    current_value = struct.unpack_from("Q", result.buf, 0)[0]
    struct.pack_into("Q", result.buf, 0, current_value + 1)
finally:
    lock.release()
end = time.perf_counter()
```

The other values are the maximum time delay, the minimum time delay, the standard deviation of the average time calculation, and the final value of the result buffer (which should be equal for all locking mechanisms and equal to `NUM_PROCESSES * NUM_RUNS`).

### ./examples/performance_analysis/run_poll_perf.py

This file is very similar to `run_perf.py`; however, it focuses solely on `shmlock` and compares its performance for different poll intervals. The measurement and analysis are the same as in the previous section.



---
<a name="troubleshooting-and-resource-tracking"></a>
## Troubleshooting and Resource Tracking


### Troubleshooting

On POSIX systems, the `resource_tracker` will likely complain that either `shared_memory` instances were not found or spam `KeyErrors`. This issue is known:

https://bugs.python.org/issue38119 (forwarded from https://bugs.python.org/issue39959) originally found at https://stackoverflow.com/questions/62748654/python-3-8-shared-memory-resource-tracker-producing-unexpected-warnings-at-appli

This can be deactivated (not fixed, as it essentially just turns off `shm` tracking) via the `remove_shm_from_resource_tracker` function:


```python

# NOTE that you can also use an empty pattern to remove track of all shared memory names
lock_pattern = "shm_lock"

# has to be done by each process
shmlock.remove_shm_from_resource_tracker(lock_pattern)

# create locks with pattern
lock1 = shmlock.ShmLock(lock_pattern + "whatsoever")
lock2 = shmlock.ShmLock("whatsoever" + lock_pattern)
```

This also seems to slightly increase the performance on POSIX systems.

Usually, each lock should be released properly.
Additionally, there is an experimental custom resource tracker; see the following section.


Please note that with Python version 3.13, there will be a "track" parameter for shared memory block creation, which can be used to disable tracking. I am aware of this and will use it at some point in the future.

### Resource Tracking

Since it is crucial that all shared memory blocks are released and the resource tracker on posix systems might cause issues, a custom resource tracker is implemented. Usually however each lock object should release its memory at destruction. To use the (custom) shared memory tracker please follow the following code snippet

Note that this is still experimental.

```python

import logging
import shmlock

# disable warnings if desired
shmlock.enable_disable_warnings(False)

# optional logger; if a history of the tracking is required, it is currently suggested to use a file logger
logging.basicConfig(level="DEBUG")
log = logging.getLogger(__name__)

# init resource tracking (once per process)
shmlock.init_custom_resource_tracking(logger=log)

# now use the ShmLock. Each requirement/release is logged via the specified logger (debug level)
...


# to uninitialize tracking use
shmlock.de_init_custom_resource_tracking()
# OR
shmlock.de_init_custom_resource_tracking_without_clean_up()
# the latter does only report and not free anything

```


---
<a name="todos"></a>
## ToDos

- achieve 100% code coverage
- upload to PyPI
- implement safeguards to prevent the resource tracker from being shared among processes

