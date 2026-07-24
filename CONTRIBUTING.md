# Contributing to Driftline

Thank you for your interest in contributing to Driftline! We welcome contributions from the community.

## Code of Conduct

All contributors are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.

## How to Contribute

### 1. Reporting Bugs

Before creating a bug report, please check existing issues to avoid duplicates. When filing an issue, please use the Bug Report template and include:
- A clear, descriptive title.
- Steps to reproduce the behavior.
- Expected vs actual behavior.
- Relevant environment details (OS, Python version, Docker version).

### 2. Suggesting Features

We welcome feature proposals! Please use the Feature Request template to outline:
- The problem your feature solves.
- Proposed implementation details or API changes.
- Any alternative solutions considered.

### 3. Submitting Pull Requests

1. **Fork the repository** and create a feature branch off `main`.
2. **Set up your local environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Make your changes**: Follow our architecture and coding conventions.
4. **Run tests**: Make sure all unit and integration tests pass cleanly:
   ```bash
   python -m pytest
   ```
5. **Update documentation**: If you modified features or APIs, update the `README.md` and `BUILD_LOG.md` accordingly.
6. **Submit a Pull Request**: Provide a clear summary of your changes and reference any related issues.

## Development & Code Conventions

- **Domain-Driven Architecture**: Backend logic belongs in domain modules (`src/<domain>/service.py`), not in `main.py` or router files.
- **Mathematical Invariants**: Any function with a mathematical invariant must include a unit test asserting that invariant.
- **Database Operations**: Persist output state to PostgreSQL. Always write clean Alembic migrations for schema changes.
- **Testing**: Maintain high test coverage. Ensure `python -m pytest` passes before opening a PR.

Thank you for helping make Driftline better!
