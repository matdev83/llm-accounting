from datetime import datetime, timedelta

from llm_accounting import LLMAccounting, UsageEntry, UsageStats


def test_track_usage(accounting, sample_entries):
    """Test tracking usage entries"""
    with accounting:
        for entry in sample_entries:
            accounting.track_usage(
                model=entry.model,
                prompt_tokens=entry.prompt_tokens,
                completion_tokens=entry.completion_tokens,
                total_tokens=entry.total_tokens,
                cost=entry.cost,
                execution_time=entry.execution_time,
                timestamp=entry.timestamp
            )


def test_tail(accounting, sample_entries):
    """Test getting recent usage entries"""
    with accounting:
        # Insert sample entries
        for entry in sample_entries:
            accounting.track_usage(
                model=entry.model,
                prompt_tokens=entry.prompt_tokens,
                completion_tokens=entry.completion_tokens,
                total_tokens=entry.total_tokens,
                cost=entry.cost,
                execution_time=entry.execution_time,
                timestamp=entry.timestamp
            )

        # Get last 2 entries
        entries = accounting.tail(2)
        assert len(entries) == 2

        # Verify entries are in correct order (most recent first)
        assert entries[0].timestamp > entries[1].timestamp

        # Verify entry contents
        assert entries[0].model == "gpt-4"
        assert entries[0].prompt_tokens == 150
        assert entries[0].completion_tokens == 75
        assert entries[0].total_tokens == 225
        assert entries[0].cost == 0.003
        assert entries[0].execution_time == 2.0

        assert entries[1].model == "gpt-3.5-turbo"
        assert entries[1].prompt_tokens == 200
        assert entries[1].completion_tokens == 100
        assert entries[1].total_tokens == 300
        assert entries[1].cost == 0.001
        assert entries[1].execution_time == 0.8


def test_tail_empty(accounting):
    """Test getting recent entries from empty database"""
    with accounting:
        entries = accounting.tail()
        assert len(entries) == 0


def test_tail_default_limit(accounting, sample_entries):
    """Test default limit for tail command"""
    with accounting:
        # Insert more than default limit (10) entries
        for i in range(15):
            entry = UsageEntry(
                model=f"model-{i}",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost=0.002,
                execution_time=1.5,
                timestamp=datetime.now() - timedelta(minutes=i)
            )
            accounting.track_usage(
                model=entry.model,
                prompt_tokens=entry.prompt_tokens,
                completion_tokens=entry.completion_tokens,
                total_tokens=entry.total_tokens,
                cost=entry.cost,
                execution_time=entry.execution_time,
                timestamp=entry.timestamp
            )

        # Get entries with default limit
        entries = accounting.tail()
        assert len(entries) == 10  # Default limit

        # Verify entries are in correct order
        for i in range(len(entries) - 1):
            assert entries[i].timestamp > entries[i + 1].timestamp


def test_track_usage_with_caller_and_user(accounting):
    """Test tracking usage entries with caller name and username"""
    with accounting:
        # Test with both fields
        accounting.track_usage(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5,
            caller_name="test_app",
            username="test_user"
        )

        # Test with empty fields
        accounting.track_usage(
            model="gpt-3.5-turbo",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost=0.001,
            execution_time=0.8
        )

        # Verify entries
        entries = accounting.tail(2)
        assert len(entries) == 2

        # Check first entry (most recent)
        assert entries[0].model == "gpt-3.5-turbo"
        assert entries[0].caller_name == ""
        assert entries[0].username == ""

        # Check second entry
        assert entries[1].model == "gpt-4"
        assert entries[1].caller_name == "test_app"
        assert entries[1].username == "test_user"


def test_tail_with_caller_and_user(accounting):
    """Test tail command with caller name and username fields"""
    with accounting:
        # Insert test entries
        accounting.track_usage(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5,
            caller_name="test_app",
            username="test_user"
        )

        # Get entries
        entries = accounting.tail(1)
        assert len(entries) == 1

        # Verify fields
        entry = entries[0]
        assert entry.model == "gpt-4"
        assert entry.caller_name == "test_app"
        assert entry.username == "test_user"
        assert entry.prompt_tokens == 100
        assert entry.completion_tokens == 50
        assert entry.total_tokens == 150
        assert entry.cost == 0.002
        assert entry.execution_time == 1.5
