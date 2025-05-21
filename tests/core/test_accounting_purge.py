from unittest.mock import Mock

from llm_accounting import LLMAccounting


def test_purge(mock_backend, monkeypatch):
    """Test purging all usage entries"""
    # Inject mock backend
    accounting = LLMAccounting(backend=mock_backend)

    # Mock the purge method of the mock_backend instance using monkeypatch
    mock_purge = Mock()
    monkeypatch.setattr(mock_backend, 'purge', mock_purge)

    with accounting:
        # Call purge
        accounting.purge()

        # Verify mock backend's purge was called
        mock_purge.assert_called_once()
