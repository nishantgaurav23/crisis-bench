"""Shared test fixtures for CRISIS-BENCH.

This file is loaded automatically by pytest for all test modules.
Add shared fixtures here as the project grows.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return PROJECT_ROOT
