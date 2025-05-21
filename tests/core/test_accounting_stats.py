from datetime import datetime, timedelta

from llm_accounting import LLMAccounting, UsageEntry, UsageStats


def test_get_period_stats(accounting, sample_entries):
    """Test getting period statistics"""
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

        # Get stats for the last 3 hours
        end = datetime.now()
        start = end - timedelta(hours=3)
        stats = accounting.get_period_stats(start, end)

        # Verify totals
        assert stats.sum_prompt_tokens == 450  # 100 + 200 + 150
        assert stats.sum_completion_tokens == 225  # 50 + 100 + 75
        assert stats.sum_total_tokens == 675  # 150 + 300 + 225
        assert stats.sum_cost == 0.006  # 0.002 + 0.001 + 0.003
        assert stats.sum_execution_time == 4.3  # 1.5 + 0.8 + 2.0

        # Verify averages
        assert stats.avg_prompt_tokens == 150  # 450 / 3
        assert stats.avg_completion_tokens == 75  # 225 / 3
        assert stats.avg_total_tokens == 225  # 675 / 3
        assert stats.avg_cost == 0.002  # 0.006 / 3
        assert abs(stats.avg_execution_time - 1.43) < 0.01  # 4.3 / 3


def test_get_model_stats(accounting, sample_entries):
    """Test getting model-specific statistics"""
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

        # Get stats for the last 3 hours
        end = datetime.now()
        start = end - timedelta(hours=3)
        model_stats = accounting.get_model_stats(start, end)

        # Convert to dict for easier testing
        stats_by_model = {model: stats for model, stats in model_stats}

        # Verify gpt-4 stats
        gpt4_stats = stats_by_model["gpt-4"]
        assert gpt4_stats.sum_prompt_tokens == 250  # 100 + 150
        assert gpt4_stats.sum_completion_tokens == 125  # 50 + 75
        assert gpt4_stats.sum_total_tokens == 375  # 150 + 225
        assert gpt4_stats.sum_cost == 0.005  # 0.002 + 0.003
        assert gpt4_stats.sum_execution_time == 3.5  # 1.5 + 2.0

        # Verify gpt-3.5-turbo stats
        gpt35_stats = stats_by_model["gpt-3.5-turbo"]
        assert gpt35_stats.sum_prompt_tokens == 200
        assert gpt35_stats.sum_completion_tokens == 100
        assert gpt35_stats.sum_total_tokens == 300
        assert gpt35_stats.sum_cost == 0.001
        assert gpt35_stats.sum_execution_time == 0.8


def test_get_model_rankings(accounting, sample_entries):
    """Test getting model rankings"""
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

        # Get rankings for the last 3 hours
        end = datetime.now()
        start = end - timedelta(hours=3)
        rankings = accounting.get_model_rankings(start, end)

        # Verify prompt tokens ranking
        prompt_tokens_ranking = rankings['prompt_tokens']
        assert prompt_tokens_ranking[0][0] == "gpt-4"  # First place
        assert prompt_tokens_ranking[0][1] == 250  # 100 + 150
        assert prompt_tokens_ranking[1][0] == "gpt-3.5-turbo"  # Second place
        assert prompt_tokens_ranking[1][1] == 200

        # Verify cost ranking
        cost_ranking = rankings['cost']
        assert cost_ranking[0][0] == "gpt-4"  # First place
        assert cost_ranking[0][1] == 0.005  # 0.002 + 0.003
        assert cost_ranking[1][0] == "gpt-3.5-turbo"  # Second place
        assert cost_ranking[1][1] == 0.001
