import pytest

from llm_accounting.backends.base import BaseBackend, UsageEntry
from tests.backends.mock_backends import IncompleteBackend, MockBackend


def test_backend_interface():
    """Test that UsageBackend properly enforces its interface"""
    # Test that a complete implementation works
    backend = MockBackend()
    assert isinstance(backend, BaseBackend)

    # Test that an incomplete implementation raises TypeError
    with pytest.raises(TypeError):
        IncompleteBackend()


def test_backend_abstract_methods():
    """Test that all abstract methods are properly defined"""
    # Get all abstract methods from BaseBackend
    abstract_methods = {
        method for method in dir(BaseBackend)
        if callable(getattr(BaseBackend, method))
        and not method.startswith('__')
    }

    # Verify that MockBackend implements all abstract methods
    for method in abstract_methods:
        assert hasattr(MockBackend, method), f"MockBackend missing {method}"
        assert callable(getattr(MockBackend, method)), f"{method} is not callable"
