"""
Pytest Configuration and Fixtures

Shared fixtures and configuration for all tests.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, MagicMock

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_repo_path() -> Generator[Path, None, None]:
    """
    Create a temporary repository path for testing.

    Yields:
        Path: Temporary directory path
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create some test files
        (repo_path / "test.py").write_text("""
def hello():
    print("Hello, World!")

class TestClass:
    def test_method(self):
        pass
""")

        (repo_path / "README.md").write_text("""
# Test Repository

This is a test repository for unit testing.
""")

        yield repo_path


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    mock = Mock()
    mock.content = "Test response"
    mock.tool_calls = []
    mock.finish_reason = "stop"
    mock.model = "test-model"
    mock.usage = Mock()
    mock.usage.input_tokens = 10
    mock.usage.output_tokens = 20
    mock.usage.total_tokens = 30
    return mock


@pytest.fixture
def mock_llm_provider(mock_llm_response):
    """Create a mock LLM provider."""
    mock = Mock()
    mock.chat.return_value = mock_llm_response
    mock.stream_chat.return_value = iter([mock_llm_response])
    return mock


@pytest.fixture
def sample_tool_call():
    """Create a sample tool call."""
    from src.llm.base import ToolCall
    return ToolCall(
        id="call_123",
        name="test_tool",
        arguments={"param": "value"}
    )


@pytest.fixture
def env_vars():
    """Set up test environment variables."""
    original = {}
    test_vars = {
        "LLM_BASE_URL": "https://test.com",
        "LLM_API_KEY": "test-key",
        "LLM_MODEL": "test-model",
        "MAX_TOOL_ITERATIONS": "5",
    }

    for key, value in test_vars.items():
        original[key] = os.environ.get(key)
        os.environ[key] = value

    yield test_vars

    # Restore original values
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
