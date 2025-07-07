import logging
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from sqlalchemy.engine.url import make_url
from sqlalchemy import text, Connection  # Added Connection
from pathlib import Path
from typing import Optional, Tuple

from alembic.script import ScriptDirectory
# EnvironmentContext might still be used by other parts of Alembic or if some logic path needs it,
# but for run_migrations and stamp_db_head post-action revision check, we are changing the method.
# Keep it for now if other alembic internals might rely on it being available.

logger = logging.getLogger(__name__)


def _get_alembic_config_details(migration_logger: logging.Logger) -> Tuple[Path, Path]:
    """Determines the alembic directory and ini file path."""
    current_file_dir = Path(__file__).parent
    project_root = current_file_dir.parent.parent
    alembic_dir = project_root / "alembic"
    alembic_ini_path = project_root / "alembic.ini"

    if not alembic_dir.is_dir() or not alembic_ini_path.is_file():
        migration_logger.debug("Alembic config not found in project root, trying package path.")
        try:
            import llm_accounting
            package_root = Path(llm_accounting.__file__).parent
            alembic_dir = package_root / "alembic"
            alembic_ini_path = package_root / "alembic.ini"
        except ImportError:
            migration_logger.error("llm_accounting package not found for Alembic path resolution.")
            raise RuntimeError("Alembic configuration could not be found (ImportError).")
        except Exception as e:
            migration_logger.error(f"Error determining alembic directory path from package: {e}")
            raise RuntimeError(f"Alembic configuration could not be found (Package Path Error: {e}).")

    if not alembic_dir.is_dir():
        raise RuntimeError(f"Alembic directory not found at expected path: {alembic_dir}.")
    if not alembic_ini_path.is_file():
        raise RuntimeError(f"alembic.ini not found at {alembic_ini_path}.")
    migration_logger.debug(f"Using alembic_dir: {alembic_dir}, alembic_ini_path: {alembic_ini_path}")
    return alembic_dir, alembic_ini_path


def run_migrations(db_url: str, connection: Optional[Connection] = None) -> Optional[str]:
    """
    Checks and applies any pending database migrations for the given DB URL.
    If a SQLAlchemy Connection object is provided, it will be used by Alembic,
    which is essential for in-memory SQLite databases to ensure operations
    occur on the same database instance.
    Returns the current database revision after upgrade.
    """
    migration_logger = logging.getLogger(__name__ + ".migrations")

    if not db_url:
        # If a connection is provided, db_url might be redundant for configuration,
        # but AlembicConfig still typically expects it.
        if connection and connection.engine:
            db_url = str(connection.engine.url)
            migration_logger.debug(f"Using db_url from provided connection: {db_url}")
        else:
            raise ValueError("Database URL must be provided to run migrations if no connection is given.")

    alembic_dir, alembic_ini_path = _get_alembic_config_details(migration_logger)

    log_db_url = db_url
    try:
        parsed_url = make_url(db_url)
        if parsed_url.password:
            log_db_url = str(parsed_url._replace(password="****"))
    except Exception:
        pass
    migration_logger.debug(f"Attempting database migrations for URL: {log_db_url}")

    alembic_logger = logging.getLogger("alembic")
    alembic_logger.setLevel(logging.DEBUG)

    current_rev: Optional[str] = None
    try:
        alembic_cfg = AlembicConfig(file_=str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        # If an external connection is provided, pass it to env.py via attributes
        if connection:
            alembic_cfg.attributes['connection'] = connection
            migration_logger.debug("Using provided external connection for migrations.")

        alembic_command.upgrade(alembic_cfg, "head")
        migration_logger.debug("Database migration upgrade to 'head' completed.")

        # Use the potentially passed-in connection for querying version,
        # or the one that env.py might have established and put in attributes.
        conn_to_query = connection if connection else alembic_cfg.attributes.get('connection')

        if conn_to_query:
            try:
                result = conn_to_query.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1"))
                current_rev = result.scalar_one_or_none()
                if current_rev:
                    migration_logger.debug(f"Current database revision from DB query: {current_rev}")
                else:  # Should not happen if alembic_version table has entries
                    migration_logger.warning("Could not find revision in alembic_version table after upgrade.")
            except Exception as e_sql:
                migration_logger.warning(f"Could not query alembic_version table after upgrade: {e_sql}. Falling back to script head.")
        else:
            migration_logger.warning("No connection found on alembic_cfg.attributes after upgrade. Cannot query alembic_version table directly.")

        if current_rev is None:  # Fallback if connection or query failed
            migration_logger.debug("Attempting to get current revision from script directory as fallback.")
            script = ScriptDirectory.from_config(alembic_cfg)
            # In a non-branching history, current revision after upgrade to head *should* be the head.
            # get_current_head() returns a tuple of heads.
            heads = script.get_heads()
            if heads:
                current_rev = heads[0]  # Take the first head if multiple (should ideally be one)
                migration_logger.debug(f"Current database revision from script head (fallback): {current_rev}")
            else:
                migration_logger.error("Fallback failed: Could not determine head revision from scripts.")

        return current_rev

    except Exception as e:  # type: ignore
        migration_logger.error(f"Error running database migrations: {e}", exc_info=True)
        raise


def get_head_revision(db_url: str) -> Optional[str]:
    '''
    Retrieves the "head" revision(s) from the Alembic migration scripts.
    Returns the first head if multiple are present.
    '''
    migration_logger = logging.getLogger(__name__ + ".migrations_head_check")
    try:
        alembic_dir, alembic_ini_path = _get_alembic_config_details(migration_logger)
        alembic_cfg = AlembicConfig(file_=str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        # sqlalchemy.url is not strictly needed for script operations but good for config consistency
        alembic_cfg.set_main_option("sqlalchemy.url", db_url if db_url else "sqlite:///:memory:")

        script = ScriptDirectory.from_config(alembic_cfg)
        heads = script.get_heads()  # get_heads() returns a tuple of revision strings
        if heads:
            head_rev = heads[0]  # Take the first head
            if len(heads) > 1:
                migration_logger.warning(f"Multiple script heads detected: {heads}. Using first one: {head_rev}")
            migration_logger.debug(f"Current head script revision: {head_rev}")
            return head_rev
        else:
            migration_logger.warning("No head script revision found.")
            return None
    except Exception as e:  # type: ignore
        migration_logger.error(f"Error getting head script revision: {e}", exc_info=True)
        return None


def stamp_db_head(db_url: str) -> Optional[str]:
    migration_logger = logging.getLogger(__name__ + ".migrations_stamp")
    try:
        alembic_dir, alembic_ini_path = _get_alembic_config_details(migration_logger)
    except RuntimeError: # Handle case where config details can't be found
        return None # Or re-raise, depending on desired behavior

    log_db_url_str = str(db_url)
    if db_url:
        try:
            parsed_url = make_url(db_url)
            if parsed_url.password:
                log_db_url_str = str(parsed_url._replace(password="****"))
        except Exception:
            pass
    migration_logger.debug(f"Attempting to stamp database for URL context: {log_db_url_str}")

    try:
        alembic_cfg = AlembicConfig(file_=str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        alembic_command.stamp(alembic_cfg, "head")
        migration_logger.debug(f"Successfully stamped database {log_db_url_str} with head revision.")

        # After stamping, the "current revision" is the head it was stamped to.
        # Get this from the scripts directly.
        script = ScriptDirectory.from_config(alembic_cfg)
        heads = script.get_heads()
        if heads:
            stamped_to_rev = heads[0]  # Take the first head
            if len(heads) > 1:
                migration_logger.warning(f"Multiple script heads detected: {heads} after stamping. Database marked with: {stamped_to_rev}")
            migration_logger.debug(f"Database confirmed stamped to script head: {stamped_to_rev}")
            return stamped_to_rev
        else:
            migration_logger.error("Could not determine script head revision after stamping. This is unexpected.")
            return None  # Should ideally not happen if stamp 'head' succeeded and scripts exist.

    except Exception as e:  # type: ignore
        migration_logger.error(f"Error stamping database {log_db_url_str} with head revision: {e}", exc_info=True)
        return None
