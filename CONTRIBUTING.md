# Contributing to PyStackQuery

First off, thank you for considering contributing to PyStackQuery! It's people like you that make PyStackQuery such a great tool.

## Code of Conduct

By participating in this project, you are expected to uphold our high standards of professional conduct and technical excellence.

## How Can I Contribute?

### Reporting Bugs
*   **Check the existing issues** to see if the bug has already been reported.
*   If you can't find an open issue that addresses the problem, **open a new one**.
*   Include a **reproducible example** and details about your environment (OS, Python version).

### Suggesting Enhancements
*   Open an issue to discuss the change before starting work.
*   Explain why the feature would be useful to most users.

### Pull Requests
1.  Fork the repo and create your branch from `main`.
2.  Install dependencies using `uv sync --dev`.
3.  If you've added code that should be tested, add tests.
4.  Ensure the test suite passes (`uv run pytest`).
5.  Run linting and type checking (`uv run ruff check .` and `uv run mypy .`).
6.  Ensure your code adheres to the existing style and architecture (PEP 695 generics, PEP 8).

## Development Setup

We use `uv` for dependency management.

```bash
# Clone the repo
git clone https://github.com/yourusername/pystackquery.git
cd pystackquery

# Install dependencies
uv sync --dev

# Run tests
uv run pytest
```

## Styling & Standards
*   **Python 3.12+**: Use modern syntax (Built-in generics, `|` unions).
*   **Linting**: We use Ruff. Always run `ruff check --fix .` before committing.
*   **Typing**: Static typing is mandatory. Ensure `mypy .` returns zero errors.
*   **Documentation**: Update documentation in `docs/` if you change any public APIs.
