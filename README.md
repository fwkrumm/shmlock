# Readme

## Table of Contents

- [About](#about)
- [Pros and Cons: When to Use This Module and When Not To](#pros-and-cons-when-to-use-this-module-and-when-not-to)
- [Installation](#installation)
- [Quick Dive](#quick-dive)
- [Examples](#examples)
- [Troubleshooting and Known Issues](#troubleshooting-and-known-issues)
- [Version History](#version-history)
- [Acknowledgments](#acknowledgments)
- [ToDos](#todos)



---
<a name="about"></a>
<a id="about"></a>
## About

Feel free to provide constructive feedback, suggestions, or feature requests. Thank you.
This module is currently under development and may undergo frequent changes on the master branch.
It is recommended to use a static version for testing.

This module provides an inter-process lock implementation (named semaphore), eliminating the need to pass around objects for synchronization.
Designed for seamless integration across multiple terminals or consoles, it enables reliable process locking simply by referencing a shared name identifier.
Under the hood, the module leverages Python’s `multiprocessing.shared_memory`.
In real-world scenarios, a lock is used to synchronize access to shared resources across multiple Python instances, such as different terminals.
Notable examples include a file or a shared memory block, which may be modified by multiple actors; see the real-world example in Section [Quick Dive](#quick-dive) and comments therein for more details.

---
<a name="pros-and-cons-when-to-use-this-module-and-when-not-to"></a>
<a id="pros-and-cons-when-to-use-this-module-and-when-not-to"></a>
## Pros and Cons: When to Use This Module and When Not To

This module is ideal when you need a simple locking mechanism without the overhead of passing lock objects between processes. It excels in scenarios where you want to avoid file-based or server-client-based locks (such as filelock, Redis, or pyzmq) and prefer a lightweight solution with minimal dependencies (aside from pywin32 on Windows, which is optional).

However, this module may not be suitable if you require very high performance with a large number of lock acquisitions, as it relies on a polling interval (i.e., a sleep interval) for synchronization. Additionally, if you are uncomfortable using shared memory as the underlying lock mechanism, alternative solutions might be more appropriate.

**Note:** Process interruptions (SIGINT/SIGTERM) during shmlock acquisition may lead to dangling shared memory. This is a known limitation of the underlying shared memory mechanism. For details on handling such scenarios, refer to the [Troubleshooting and Known Issues](#troubleshooting-and-known-issues) section.

In summary, this module works best when the number of synchronized accesses remains moderate rather than extremely high and the starting/stopping of processes is well controlled.

---
<a name="installation"></a>
<a id="installation"></a>
## Installation

This module has no additional dependencies. There are several ways to install it:

1. Via the Python Package Index (available from version 3.0.0 onward; older versions can be accessed through git tags, see point 2. and 3. below):

```
pip install shmlock[membar]
```

The optional `[membar]` installs the `membar` (memory barrier) module. If you do not need this feature, you can simply install via `pip install shmlock`.

2. Install directly from the repository:
`pip install git+https://github.com/fwkrumm/shmlock@master`
for the latest version or
```
pip install git+https://github.com/fwkrumm/shmlock@X.Y.Z
```
for a specific version; cf. Section [Version History](#version-history).

3. Clone this repository and install it from the local files via pip:
    ```
    git clone https://github.com/fwkrumm/shmlock
    cd shmlock
    pip install . -r requirements.txt
    ```

    Note that `-r requirements.txt` is only necessary if you want to run the tests and examples. The module itself does not have additional requirements apart from standard modules.

---
<a name="quick-dive"></a>
<a id="quick-dive"></a>
## Quick Dive

For further examples please check out the [Examples](#examples) section.
For the sake of completeness: **Do not** share a lock among threads. Each thread should use its own lock. However, typically, you would not use this lock implementation to synchronize threads within the same process. Instead, you would use the more efficient `threading.Lock()`.


```python
import shmlock

# lock name should only be used by locks and not any other shared memory
# if you want to use the lock in any other process, just use the same name
lock = shmlock.ShmLock("shm_lock")

#
# to apply the lock, use one of the following: a), b), c)
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
        # lock could not be acquired after the specified timeout
        pass


# add description for debug purposes
lock.description = "main process lock"

# get exit event and set it in the main process to stop all locks from acquiring
# NOTE that if no event has been specified during the init, this will be a mocked event
# i.e. there will not be automatic creations of threading.Event or multiprocessing.Event objects
lock.get_exit_event()

# get uuid of lock which has currently acquired shared memory
lock.acquire()
print(lock.debug_get_uuid_of_locking_lock())
lock.release()

# get uuid of this lock
print(lock.uuid)

# check if lock is currently acquired
print(lock.acquired)

# the lock is reentrant:
with lock:
    with lock:
        pass
    # still locked, lock.release() would raise an exception unless force parameter is used

# create a logger (helper function)
import logging
logger = shmlock.create_logger(name="shmlogger", level=logging.DEBUG) # also check doc-string
lock_with_logger = shmlock.ShmLock("shm_lock", logger=logger)

# on some architectures (e.g. ARM) you might want to enable memory barriers to
# ensure correct ordering of operations.
lock_with_membar = shmlock.ShmLock("shm_lock_membar", memory_barrier=True)

# the following lock will block SIGINT and SIGTERM signals during shared memory allocation
# to prevent dangling shared memory in case of abrupt process termination.
# Note that this may not work for process terminations, depending on the platform.
lock_which_blocks_signals = shmlock.ShmLock("shm_lock_signals", block_signals=True)
```

### Real-world Example

A simple example demonstrating the actual use of a lock is the following code, which should run across different terminals.
The reference counter is incremented synchronously, and each terminal writes a 16-byte UUID to the shared memory block in a synchronized manner.

Additionally, the `unlink()` function (only relevant for POSIX) is only called when the last terminal executing the code has closed.

```python
from multiprocessing import shared_memory
import shmlock
import time
import uuid

lock = shmlock.ShmLock("lock_name")

with lock:
    # create (attach to) shared memory for synchronized access
    try:
        shm = shared_memory.SharedMemory(name="shm_name", create=True, size=17) # buffer layout: 1 byte for the reference counter (to track usage), followed by 16 bytes for the UUID (128-bit unique identifier)
    except FileExistsError:
        shm = shared_memory.SharedMemory(name="shm_name")

    # increment ref counter (synchronized with lock)
    shm.buf[0] += 1
    print("ref count incremented to", shm.buf[0])

try:

    while True:

        with lock:
            print("lock acquired; current ref count is", shm.buf[0])
            # write uuid (or any other payload) to shared memory block
            uuid_bytes = uuid.uuid4().bytes
            shm.buf[1:1+len(uuid_bytes)] = uuid_bytes
        time.sleep(1) # prevent spam

except KeyboardInterrupt:
    print("KeyboardInterrupt received, exiting...")

finally:
    with lock:
        shm.buf[0] -= 1
        ref_count = shm.buf[0]
        print("ref count decremented to", ref_count)
        shm.close()
        if ref_count == 0:
            shm.unlink()
            print("shared memory unlinked since last reference released")

# the lock does not require any additional release as long as the process did not terminate abruptly.

```

---
<a name="examples"></a>
<a id="examples"></a>
## Examples

There are examples that demonstrate the usage in more detail. Note that the requirements from the `requirements.txt` file are required for some of the examples.

### ./examples/multiple_terminals/run_multiple.py

Simply execute this file from different consoles and experiment with the global variable:

```python
USE_LOCK = True
```

Each instance will attempt to increment the value stored in a shared memory, the name of which is defined by `RESULT_SHM_NAME` in the file.

If `USE_LOCK` is set to `True` (default), the lock is enabled, and the output should resemble the following (depending on the OS and the chosen number of `RUNS` and `DELAY_FOR_LOCKS` in the example):

![multiple_ok](./docs/assets/example_multiple_ok.png)

If you now try the same with:

```python
USE_LOCK = False
```

you will (non-deterministically) get

![multiple_nok](./docs/assets/example_multiple_nok.png)


This happens if a race condition occurs, i.e., one instance overwrote the value already extracted by another instance before it could increment and store the value. This does not happen if the locking mechanism is used.

### ./examples/performance_analysis/run_perf.py

This file can be used to test the performance of different locking mechanisms. Currently, this includes "no lock", zmq, shmlock, and filelock.

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


INFO:PerformanceLogger:Running test type filelock
INFO:PerformanceLogger:Test type filelock:
INFO:PerformanceLogger:average time: 0.006232s
INFO:PerformanceLogger:max time: 0.645011s
INFO:PerformanceLogger:min time: 0.000296s
INFO:PerformanceLogger:standard deviation: 0.030970s
INFO:PerformanceLogger:Result buffer: 15000 (should be 15000)
```

The first test does not synchronize anything. This is, of course, the fastest; however, the counter is often not incremented properly.

The second test uses pyzmq (https://pypi.org/project/pyzmq/), the third test uses the shared memory lock implemented in this project, and the fourth test uses filelock (https://pypi.org/project/filelock/).

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
<a name="troubleshooting-and-known-issues"></a>
<a id="troubleshooting-and-known-issues"></a>
## Troubleshooting and Known Issues


### Resource Tracking

For Python 3.13 and later versions, there is an additional parameter for `SharedMemory(..., track: bool = True)` which disables the shared memory tracking that causes the following tracking issues.

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

Usually, each lock should be released properly. One problem however is if the process is
interrupted abruptly (SIGINT/SIGTERM) which might cause issues. For details see the following Subsection.

Please note that with Python version 3.13, there will be a "track" parameter for shared memory block creation, which can be used to disable tracking. I am aware of this and will use it at some point in the future.

### Process Interrupt (SIGINT/SIGTERM)

**Important:** Starting from version 4.4.0, there is a `block_signals` parameter in the `ShmLock` constructor. If set to `True`, it will block `SIGINT` and `SIGTERM` signals during the critical shared memory allocation phase to prevent dangling shared memory in case of abrupt process termination. Note that this may not work for all process terminations, depending on the platform. This is the recommended approach when process interruptions are a concern.

In short: Abrupt process termination carries the risk of dangling shared memory. Make sure to release the lock properly. If proper release is not possible, try the `add_exit_handlers(...)` function or use `block_signals=True`; see the text below for details.


**TLDR:** Use `block_signals=True` when creating the lock to mitigate issues from abrupt process terminations during shared memory allocation.

One potential issue arises if a process is terminated (such as through a `KeyboardInterrupt`) during the creation of shared memory (i.e., inside `shared_memory.SharedMemory(...)`). On Linux, this can lead to problematic outcomes, such as the shared memory mmap file being created with a size of zero or a shared memory block being allocated without an object reference being returned. In such cases, neither `close()` nor `unlink()` can be properly called.

Since detecting this scenario is not trivial, the function `query_for_error_after_interrupt(...)` helps to handle such cases:


```python

lock = shmlock.ShmLock("lock_name")
lock.query_for_error_after_interrupt()

```

If the shared memory is in an inconsistent state (such as being created but lock does not hold reference) the function raises an exception. Otherwise, if everything is functioning correctly, it simply returns `None`. For further details, check the function's doc-string.


In case you expect the process being terminated abruptly, you can use the following function:

```python
s = shmlock.ShmLock("lock_name")

# the following function will (depending on parameters) register cleanup via atexit module (nt and posix), via signal module (for SIGINT, SIGTERM and SIGHUP; posix only), via weakref.finalize (nt and posix) and via win32api (console handler, nt only) and trigger garbage collection, respectively.
s.add_exit_handlers(register_atexit = True,
                    register_signal = True,
                    register_weakref = True,
                    register_console_handler = True,
                    call_gc = True) # experimental
```

However, please note that in some situations, you might not be able to recover from an interruption. One example on POSIX is when the shared memory mmap has been created at `/dev/shm/` but has not yet been filled—i.e., it has a size of zero—and the process is interrupted. In this case, you can neither create shared memory with that name (`FileExistsError`) nor attach to it (`ValueError`). The previously mentioned `query_for_error_after_interrupt(...)` will report this error; however, you will have to manually delete the mmap file at `/dev/shm/{lock_name}`.

### Using Locks in a Module’s `__del__` Method

Exercise caution when using locks within another module’s `__del__` method, as the `SharedMemory` class from the `shared_memory` file may no longer be available.
To ensure safe cleanup, consider alternatives such as `atexit`, `signal.signal`, or `weakref.finalize` when a lock is required during teardown.


---
<a name="version-history"></a>
<a id="version-history"></a>
## Version History

| Version / Git Tag on Master | Description |
|----------------------------|-------------|
| 1.0.0                      | Initial release providing basic functionality. |
| 1.1.0                      | Added PyPI workflow and made minor corrections. |
| 2.0.0                      | Introduced the `query_for_error_after_interrupt(...)` function, removed the custom (experimental) resource tracker, and added multiple tests to improve code coverage. |
| 3.0.0                      | Added reentrancy support and removed the `throw` parameter. |
| 3.0.1                      | Made minor adjustments to `README.md` and several workflow files. |
| 3.0.2                      | Added example code to `README.md`. |
| 3.1.0                      | Moved `ShmLockConfig` to a separate file and extended support down to Python 3.8 (`Union` from `typing`). |
| 3.1.1                      | Made a minor fix to the real-world example in `README.md`. |
| 3.1.2                      | Replaced direct errors with `warnings.warn` for potential dangling shared memory blocks. |
| 3.1.3                      | Fixed anchors in `README.md` and removed unnecessary spaces. |
| 4.0.0                      | Handled `OSError` when the event handle becomes invalid on Windows. Removed automatic initialization of the multiprocessing event; instead, a mock event simply applies `time.sleep()`. |
| 4.0.1                      | Fixed properties not being available before acquisition and implemented proper test methods. |
| 4.0.2                      | Reworked version history. |
| 4.1.0                      | Added a helper function to create a logger, added more tests and removed unnecessary space. |
| 4.2.0                      | Added function to automatically register exit handlers for process termination. |
| 4.2.1                      | Added community files (templates, code of conduct, security). |
| 4.2.2                      | Added workflow permissions. |
| 4.2.3                      | Moved pull request template to correct location in .github folder. |
| 4.2.4                      | Minor correction to readme. |
| 4.3.0                      | Added memory barrier and minor additions to readme. |
| 4.4.0                      | Add possibility to disable SIGINT and SIGTERM during shared memory allocation to prevent dangling shared memory. |
| 4.4.1                      | Use static version for pymembar package and improve signal handling. |
| 4.4.2                      | Improve exception handling. |
| 4.4.3                      | Prevent attribute error in case of wrong parameters being passed (correctly raise TypeError). |
| 4.4.4                      | Minor improvements to README.md. |

---
<a name="acknowledgments"></a>
<a id="acknowledgments"></a>
## Acknowledgments

This project has been refined and extended with the assistance of GitHub Copilot Agent powered by Claude Sonnet 4.5. The AI assistant has been instrumental in code refinement, documentation enhancement, and providing critical feedback throughout the development process.

---
<a name="todos"></a>
<a id="todos"></a>
## ToDos

- TBD
