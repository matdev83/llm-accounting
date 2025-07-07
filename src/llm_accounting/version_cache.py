"""
Package version-based migration cache management.

This module provides functionality to track package versions and avoid
running migrations unnecessarily when the package hasn't been updated.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

try:
    from importlib.metadata import version
except ImportError:
    # Python < 3.8 fallback
    from importlib_metadata import version

logger = logging.getLogger(__name__)

PACKAGE_NAME = "llm-accounting"


def get_package_version() -> Optional[str]:
    """Get the current package version."""
    try:
        return version(PACKAGE_NAME)
    except Exception as e:
        logger.warning(f"Could not determine package version: {e}")
        return None


def load_migration_cache(cache_file_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Load migration cache from file.
    
    Returns:
        Tuple of (package_version, database_revision) or (None, None) if cache doesn't exist or is invalid
    """
    if not cache_file_path.exists():
        logger.debug(f"Migration cache file does not exist: {cache_file_path}")
        return None, None
    
    try:
        with open(cache_file_path, 'r') as f:
            cache_data = json.load(f)
        
        package_version = cache_data.get("package_version")
        database_revision = cache_data.get("database_revision")
        
        logger.debug(f"Loaded migration cache: package_version={package_version}, database_revision={database_revision}")
        return package_version, database_revision
        
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not read migration cache file {cache_file_path}: {e}")
        return None, None


def save_migration_cache(cache_file_path: Path, package_version: str, database_revision: str) -> None:
    """
    Save migration cache to file.
    
    Args:
        cache_file_path: Path to the cache file
        package_version: Current package version
        database_revision: Current database revision
    """
    try:
        cache_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        cache_data = {
            "package_version": package_version,
            "database_revision": database_revision
        }
        
        with open(cache_file_path, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        logger.debug(f"Saved migration cache: {cache_data}")
        
    except IOError as e:
        logger.warning(f"Could not write migration cache file {cache_file_path}: {e}")


def should_run_migrations(cache_file_path: Path, current_head_revision: str) -> bool:
    """
    Determine if migrations should be run based on package version and cached state.
    
    Args:
        cache_file_path: Path to the cache file
        current_head_revision: Current head revision from migration scripts
        
    Returns:
        True if migrations should be run, False otherwise
    """
    current_package_version = get_package_version()
    if not current_package_version:
        logger.warning("Could not determine current package version. Will run migrations as precaution.")
        return True
    
    cached_package_version, cached_database_revision = load_migration_cache(cache_file_path)
    
    # If no cache exists, run migrations
    if cached_package_version is None:
        logger.debug("No migration cache found. Migrations will run.")
        return True
    
    # If package version changed, run migrations
    if cached_package_version != current_package_version:
        logger.info(f"Package version changed from {cached_package_version} to {current_package_version}. Migrations will run.")
        return True
    
    # If head revision changed (new migration scripts), run migrations
    if cached_database_revision != current_head_revision:
        logger.info(f"Head revision changed from {cached_database_revision} to {current_head_revision}. Migrations will run.")
        return True
    
    # Package version and head revision match - skip migrations
    logger.debug(f"Package version {current_package_version} and head revision {current_head_revision} match cache. Migrations will be skipped.")
    return False


def update_migration_cache_after_success(cache_file_path: Path, database_revision: str) -> None:
    """
    Update migration cache after successful migration.
    
    Args:
        cache_file_path: Path to the cache file
        database_revision: Database revision after migration
    """
    current_package_version = get_package_version()
    if current_package_version:
        save_migration_cache(cache_file_path, current_package_version, database_revision)
    else:
        logger.warning("Could not determine package version after migration. Cache not updated.") 