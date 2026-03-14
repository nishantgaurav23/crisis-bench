"""Tests for S1.1: Verify .env.example contains all required variables."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_env_vars() -> set[str]:
    """Extract variable names from .env.example."""
    env_file = ROOT / ".env.example"
    variables = set()
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            var_name = line.split("=", 1)[0].strip()
            variables.add(var_name)
    return variables


class TestEnvExample:
    REQUIRED_VARS = [
        # LLM API keys
        "DEEPSEEK_API_KEY",
        "QWEN_API_KEY",
        "KIMI_API_KEY",
        "GROQ_API_KEY",
        "GOOGLE_API_KEY",
        # Indian govt APIs
        "BHUVAN_TOKEN",
        "NASA_FIRMS_KEY",
        "DATA_GOV_IN_KEY",
        # Bhashini
        "BHASHINI_USER_ID",
        "BHASHINI_ULCA_API_KEY",
        "BHASHINI_INFERENCE_API_KEY",
        # Local
        "OLLAMA_HOST",
        # Database
        "POSTGRES_PASSWORD",
        "NEO4J_PASSWORD",
        # Langfuse
        "LANGFUSE_SECRET",
        "LANGFUSE_SALT",
    ]

    def test_all_required_vars_present(self):
        env_vars = _load_env_vars()
        for var in self.REQUIRED_VARS:
            assert var in env_vars, f"Missing env var in .env.example: {var}"

    def test_no_real_secrets(self):
        """No actual API keys should be in the example file."""
        env_file = ROOT / ".env.example"
        content = env_file.read_text()
        # Real API keys are typically long alphanumeric strings
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                value = line.split("=", 1)[1].strip()
                # Values should be empty or placeholder-style
                assert len(value) < 30 or value.startswith("${"), (
                    f"Possible real secret in .env.example: {line[:40]}..."
                )
