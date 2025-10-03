# ShmLock - Inter-Process Lock Implementation

[![PyPI version](https://badge.fury.io/py/shmlock.svg)](https://badge.fury.io/py/shmlock)
[![Python versions](https://img.shields.io/pypi/pyversions/shmlock.svg)](https://pypi.org/project/shmlock/)
[![License](https://img.shields.io/github/license/fwkrumm/shmlock.svg)](https://github.com/fwkrumm/shmlock/blob/main/LICENSE.txt)

## Table of Contents

- [About](#about)
- [Key Features](#key-features)
- [Pros and Cons: When to Use This Module and When Not To](#pros-and-cons-when-to-use-this-module-and-when-not-to)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Examples](#examples)
- [API Reference](#api-reference)
- [Troubleshooting and Known Issues](#troubleshooting-and-known-issues)
- [Contributing](#contributing)
- [Version History](#version-history)
- [License](#license)

---

## About

**ShmLock** is a Python module that provides an inter-process lock implementation using shared memory, eliminating the need to pass lock objects between processes. Designed for seamless integration across multiple terminals or consoles, it enables reliable process synchronization simply by referencing a shared name identifier.

⚠️ **Development Status**: This module is currently under active development and may undergo frequent changes on the main branch. It is recommended to use a specific version for production use.

### Key Features

- **No object passing required**: Lock synchronization using only string names
- **Cross-process compatibility**: Works seamlessly across different Python processes
- **Minimal dependencies**: Only requires `pywin32` on Windows systems
- **Reentrant locks**: Same lock object can be acquired multiple times by the same thread
- **Configurable polling**: Adjustable polling intervals for performance tuning
- **Comprehensive logging**: Optional detailed logging for debugging
- **Resource tracking**: Built-in resource management with optional monkey-patching

Under the hood, the module leverages Python's `multiprocessing.shared_memory` to create named shared memory blocks that serve as inter-process synchronization primitives.

---

## Pros and Cons: When to Use This Module and When Not To

| ✅ **When to Use** | ❌ **When Not to Use** |
|-------------|-----------------|
| You want a lock without passing lock objects around | You do not want a lock that uses a polling interval (i.e. a sleep interval) |
| You need a simple locking mechanism | You require very high performance and a large number of acquisitions |
| You want to avoid file-based or server-client-based locks (like filelock, Redis, pyzmq, etc.) | You are not comfortable using shared memory as a lock mechanism |
| You do not want the lock to add dependencies to your project (despite pywin32 on Windows optionally) | You need sub-millisecond locking precision |
| You need cross-platform compatibility | You are working within a single process (use `threading.Lock` instead) |

**Performance Note**: This module is best suited for moderate-frequency lock acquisitions. For high-frequency locking scenarios, consider alternative approaches.

---

## Installation

This module has minimal dependencies and can be installed in several ways:

### 1. From PyPI (Recommended)

```bash
pip install shmlock
```

### 2. From Source (Latest Development Version)

```bash
pip install git+https://github.com/fwkrumm/shmlock@main
```

### 3. For Development

```bash
git clone https://github.com/fwkrumm/shmlock
cd shmlock
pip install -e .[dev]
```

**Optional Dependencies:**
- `pywin32`: Required on Windows systems for console handling
- `coloredlogs`: Optional for colored console output

---

## Quick Start

### Basic Usage

```python
import shmlock

# Create a lock with a unique name
lock = shmlock.ShmLock("my_shared_resource")

# Method 1: Context manager (recommended)
with lock.lock(timeout=5.0) as acquired:
    if acquired:
        print("Lock acquired! Doing critical work...")
        # Your critical section here
    else:
        print("Could not acquire lock within timeout")

# Method 2: Callable syntax
with lock(timeout=5.0) as acquired:
    if acquired:
        # Your critical section here
        pass

# Method 3: Manual acquire/release
if lock.acquire(timeout=5.0):
    try:
        # Your critical section here
        pass
    finally:
        lock.release()
```

### Cross-Process Example

**Terminal 1:**
```python
import shmlock
import time

lock = shmlock.ShmLock("shared_counter")

with lock.lock(timeout=10.0) as acquired:
    if acquired:
        print("Process 1: Working...")
        time.sleep(5)  # Simulate work
        print("Process 1: Done!")
```

**Terminal 2:**
```python
import shmlock

lock = shmlock.ShmLock("shared_counter")  # Same name!

with lock.lock(timeout=10.0) as acquired:
    if acquired:
        print("Process 2: My turn!")
        # This will wait until Process 1 releases the lock
```

---

## Examples

### File Access Synchronization

```python
import shmlock
import json

def update_shared_file(data):
    """Update a shared JSON file safely across processes."""
    lock = shmlock.ShmLock("file_access_lock")
    
    with lock.lock(timeout=10.0) as acquired:
        if not acquired:
            raise TimeoutError("Could not acquire file lock")
        
        # Read current data
        try:
            with open("shared_data.json", "r") as f:
                current_data = json.load(f)
        except FileNotFoundError:
            current_data = {}
        
        # Update data
        current_data.update(data)
        
        # Write back
        with open("shared_data.json", "w") as f:
            json.dump(current_data, f, indent=2)
        
        print(f"Updated file with: {data}")

# Usage from multiple processes
update_shared_file({"process_1": "data"})
```

### Resource Pool Management

```python
import shmlock
import time
from typing import Optional

class SharedResourcePool:
    """Manage a pool of shared resources across processes."""
    
    def __init__(self, pool_name: str, max_resources: int = 5):
        self.pool_name = pool_name
        self.max_resources = max_resources
        self.lock = shmlock.ShmLock(f"pool_{pool_name}")
    
    def acquire_resource(self, timeout: float = 30.0) -> Optional[int]:
        """Acquire a resource from the pool."""
        with self.lock.lock(timeout=timeout) as acquired:
            if not acquired:
                return None
            
            # Check resource availability (simplified)
            # In real implementation, you'd track this in shared memory
            for resource_id in range(self.max_resources):
                if self._is_resource_available(resource_id):
                    self._mark_resource_used(resource_id)
                    return resource_id
            
            return None  # No resources available
    
    def release_resource(self, resource_id: int):
        """Release a resource back to the pool."""
        with self.lock.lock(timeout=10.0) as acquired:
            if acquired:
                self._mark_resource_free(resource_id)

# Usage
pool = SharedResourcePool("database_connections")
resource = pool.acquire_resource()
if resource is not None:
    try:
        print(f"Using resource {resource}")
        # Do work with resource
    finally:
        pool.release_resource(resource)
```

### Advanced Configuration

```python
import shmlock
import logging
import multiprocessing

# Configure logging
logger = shmlock.create_logger(
    name="MyApp",
    level=logging.DEBUG,
    use_colored_logs=True,
    file_path="app.log"
)

# Create lock with custom configuration
exit_event = multiprocessing.Event()
lock = shmlock.ShmLock(
    "advanced_lock",
    poll_interval=0.1,  # Check every 100ms
    logger=logger,
    exit_event=exit_event
)

# Use with timeout and error handling
try:
    with lock.lock(timeout=5.0) as acquired:
        if acquired:
            logger.info("Critical section started")
            # Your critical code here
            logger.info("Critical section completed")
        else:
            logger.warning("Could not acquire lock within timeout")
except Exception as e:
    logger.error(f"Error in critical section: {e}")
finally:
    # Signal other processes to stop waiting
    exit_event.set()
```

---

## API Reference

### ShmLock Class

```python
class ShmLock(lock_name, poll_interval=0.05, logger=None, exit_event=None, track=None)
```

**Parameters:**
- `lock_name` (str): Unique name for the lock
- `poll_interval` (float, optional): Polling interval in seconds (default: 0.05)
- `logger` (logging.Logger, optional): Logger instance for debugging
- `exit_event` (Event, optional): Event to signal lock acquisition termination
- `track` (bool, optional): Whether to track shared memory (Python 3.13+ only)

**Methods:**

#### `acquire(timeout=None) -> bool`
Acquire the lock.

**Parameters:**
- `timeout` (float|bool|None): 
  - `None`: Wait indefinitely
  - `False`: Single attempt, no waiting
  - `True`: 1-second timeout
  - `float`: Timeout in seconds

**Returns:** `True` if acquired, `False` otherwise

#### `release() -> None`
Release the lock.

#### `lock(timeout=None) -> ContextManager[bool]`
Context manager for lock acquisition.

#### `__call__(timeout=None) -> ContextManager[bool]`
Callable syntax for lock acquisition.

### Utility Functions

#### `create_logger(name, level, file_path=None, use_colored_logs=True) -> logging.Logger`
Create a configured logger instance.

#### `remove_shm_from_resource_tracker(pattern, print_warning=True) -> None`
Monkey-patch resource tracker to prevent shared memory warnings (POSIX only, Python < 3.13).

---

## Troubleshooting and Known Issues

### Common Issues

#### 1. "Permission denied" errors
**Cause:** Insufficient permissions to create shared memory blocks.
**Solution:** Run with appropriate permissions or use a different lock name.

#### 2. Resource tracker warnings on POSIX systems
**Cause:** Python's resource tracker detects "orphaned" shared memory.
**Solution:** Use the resource tracker monkey patch:

```python
import shmlock

# Remove warnings for locks with "myapp" in the name
shmlock.remove_shm_from_resource_tracker("myapp")

# Or remove all shared memory tracking (use with caution)
shmlock.remove_shm_from_resource_tracker("")
```

#### 3. Deadlocks
**Cause:** Multiple locks acquired in different orders.
**Solution:** Always acquire locks in the same order across processes, or use timeouts.

#### 4. Memory leaks
**Cause:** Processes terminated without releasing locks.
**Solution:** 
- Always use context managers or try/finally blocks
- Use exit events to signal termination
- On Linux, manually clean `/dev/shm/` if needed

### Platform-Specific Notes

#### Windows
- Requires `pywin32` for console signal handling
- Shared memory is automatically cleaned up on process termination

#### Linux/macOS
- Shared memory blocks persist in `/dev/shm/` until explicitly removed
- Consider using the resource tracker monkey patch
- Manual cleanup may be needed after abnormal termination

### Performance Considerations

- Default polling interval is 50ms - adjust based on your needs
- Lower polling intervals increase responsiveness but use more CPU
- For high-frequency locking, consider alternative synchronization methods

---

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/fwkrumm/shmlock
   cd shmlock
   ```

2. Install development dependencies:
   ```bash
   pip install -e .[dev]
   ```

3. Run tests:
   ```bash
   python -m unittest discover tests/
   ```

4. Run linting:
   ```bash
   pylint shmlock/
   black shmlock/ tests/
   mypy shmlock/
   ```

### Reporting Issues

Please report issues on our [GitHub Issues](https://github.com/fwkrumm/shmlock/issues) page with:
- Python version
- Operating system
- Minimal code example
- Error messages/tracebacks

---

## Version History

### v4.2.4 (Current)
- Improved type hints and documentation
- Enhanced error handling
- Added comprehensive test coverage
- Better resource management

### v4.2.x
- Bug fixes and stability improvements
- Performance optimizations

### v4.1.x
- Added exit event support
- Improved logging capabilities

### v4.0.x
- Major rewrite with improved architecture
- Added context manager support
- Enhanced cross-platform compatibility

### v3.x
- Initial stable release
- Basic shared memory locking functionality

For detailed changelog, see [CHANGELOG.md](CHANGELOG.md).

---

## License

This project is licensed under the BSD 3-Clause License - see the [LICENSE.txt](LICENSE.txt) file for details.

---

## Acknowledgments

- Thanks to Álvaro Justen (turicas) for the resource tracker monkey patch
- Inspired by various inter-process communication solutions
- Built on Python's excellent `multiprocessing.shared_memory` module

---

**Need help?** Feel free to open an issue or start a discussion on GitHub!