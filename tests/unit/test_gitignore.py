"""Tests for S1.1: Verify .gitignore contains critical patterns."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestGitignore:
    REQUIRED_PATTERNS = [
        ".env",
        "data/",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "*.egg-info",
        ".coverage",
        "dist/",
        "node_modules/",
    ]

    def test_required_patterns_present(self):
        content = (ROOT / ".gitignore").read_text()
        for pattern in self.REQUIRED_PATTERNS:
            assert pattern in content, f"Missing .gitignore pattern: {pattern}"

    def test_env_file_ignored(self):
        """The .env file (with secrets) must be gitignored."""
        content = (ROOT / ".gitignore").read_text()
        lines = [line.strip() for line in content.splitlines()]
        assert ".env" in lines, ".env must be explicitly gitignored (exact line)"
