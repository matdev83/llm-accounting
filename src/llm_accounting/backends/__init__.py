from .sqlite import SQLiteBackend


def get_backend() -> SQLiteBackend:
    """Get the configured backend instance"""
    return SQLiteBackend("file:memdb.sqlite?mode=memory&cache=shared")


__all__ = ["SQLiteBackend"]
