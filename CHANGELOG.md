# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-10-03

### Added
- Comprehensive type hints throughout the codebase
- Improved exception hierarchy with proper inheritance
- Enhanced validation in configuration classes
- New test suite for improved functionality (`test_improved_functionality.py`)
- New test suite for monkey patch functionality (`test_monkey_patch.py`)
- Comprehensive API documentation in README
- Development dependencies configuration in pyproject.toml
- Black, mypy, and pytest configuration
- Enhanced .gitignore with Python-specific patterns
- Equality and hash methods for ShmUuid class
- Input validation for UUID conversion methods
- Better error handling in logger creation
- Comprehensive docstrings for all public methods

### Changed
- **BREAKING**: Exception inheritance - `ShmLockValueError` now inherits from both `ShmlockError` and `ValueError`
- Improved README.md with better structure, examples, and comprehensive documentation
- Enhanced code formatting and documentation style
- Better error messages with more descriptive text
- Improved resource cleanup and error handling
- Updated requirements.txt with version ranges and better organization
- Enhanced pyproject.toml with proper metadata and development tools configuration

### Fixed
- Fixed unescaped backslashes in pyproject.toml regex patterns
- Improved error handling in file operations for logger
- Better validation of input parameters across all modules
- Fixed potential resource leaks in error conditions
- Corrected type annotations for better IDE support

### Improved
- Code quality and maintainability through type hints
- Test coverage with new comprehensive test cases
- Documentation quality and completeness
- Error handling and user feedback
- Development workflow with proper tooling configuration
- Module structure and organization

### Technical Improvements
- Added proper type checking with mypy configuration
- Implemented code formatting standards with Black
- Enhanced testing framework with pytest configuration
- Improved development dependencies management
- Better code documentation and inline comments
- Enhanced error propagation and handling

## [4.2.4] - Previous Release
- Stable release with basic functionality
- Core shared memory locking implementation
- Cross-platform compatibility
- Basic documentation and examples