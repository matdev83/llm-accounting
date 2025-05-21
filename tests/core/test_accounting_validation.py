from datetime import datetime, timedelta

import pytest

from llm_accounting import LLMAccounting, UsageEntry, UsageStats


def test_track_usage_empty_model(accounting):
    """Test tracking usage with empty model name"""
    with accounting:
        with pytest.raises(ValueError, match="Model name must be a non-empty string"):
            accounting.track_usage(
                model="",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150
            )


def test_track_usage_none_model(accounting):
    """Test tracking usage with None model name"""
    with accounting:
        with pytest.raises(ValueError, match="Model name must be a non-empty string"):
            accounting.track_usage(
                model=None,
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150
            )


def test_usage_entry_empty_model():
    """Test creating UsageEntry with empty model name"""
    with pytest.raises(ValueError, match="Model name must be a non-empty string"):
        UsageEntry(model="")


def test_usage_entry_none_model():
    """Test creating UsageEntry with None model name"""
    with pytest.raises(ValueError, match="Model name must be a non-empty string"):
        UsageEntry(model=None)


def test_track_usage_without_timestamp(accounting):
    """Test tracking usage without providing timestamp"""
    with accounting:
        # Track usage without timestamp
        accounting.track_usage(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5
        )

        # Get the entry
        entries = accounting.tail(1)
        assert len(entries) == 1

        # Verify timestamp was set by database
        assert entries[0].timestamp is not None
        # Verify timestamp is recent (within last minute)
        assert (datetime.now() - entries[0].timestamp).total_seconds() < 60


def test_track_usage_with_timestamp(accounting):
    """Test tracking usage with explicit timestamp"""
    test_timestamp = datetime(2024, 1, 1, 12, 0, 0)

    with accounting:
        # Track usage with timestamp
        accounting.track_usage(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5,
            timestamp=test_timestamp
        )

        # Get the entry
        entries = accounting.tail(1)
        assert len(entries) == 1

        # Verify timestamp was preserved
        assert entries[0].timestamp == test_timestamp


def test_track_usage_with_token_details(accounting):
    """Test tracking usage with cached and reasoning tokens"""
    with accounting:
        # Track usage with token details
        accounting.track_usage(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5,
            cached_tokens=20,
            reasoning_tokens=10
        )

        # Get the entry
        entries = accounting.tail(1)
        assert len(entries) == 1

        # Verify token details
        entry = entries[0]
        assert entry.cached_tokens == 20
        assert entry.reasoning_tokens == 10


def test_track_usage_default_token_details(accounting):
    """Test tracking usage with default token details"""
    with accounting:
        # Track usage without token details
        accounting.track_usage(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )

        # Get the entry
        entries = accounting.tail(1)
        assert len(entries) == 1

        # Verify default values
        entry = entries[0]
        assert entry.cached_tokens == 0
        assert entry.reasoning_tokens == 0
