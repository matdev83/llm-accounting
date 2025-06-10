import pytest
from unittest.mock import Mock

from llm_accounting import LLMAccounting
from llm_accounting.backends.base import TransactionalBackend, AuditBackend


def test_separate_audit_backend_usage():
    usage_backend = Mock(spec=TransactionalBackend)
    audit_backend = Mock(spec=AuditBackend)

    acc = LLMAccounting(backend=usage_backend, audit_backend=audit_backend)

    with acc:
        acc.track_usage(model="gpt", prompt_tokens=1)
        acc.audit_logger.log_event(
            app_name="app",
            user_name="user",
            model="gpt",
            log_type="event",
        )

    usage_backend.initialize.assert_called_once()
    usage_backend.insert_usage.assert_called_once()
    usage_backend.close.assert_called_once()

    audit_backend.initialize.assert_called_once()
    audit_backend.initialize_audit_log_schema.assert_called_once()
    audit_backend.log_audit_event.assert_called_once()
    audit_backend.close.assert_called_once()
