import json
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from llm_accounting.models.base import Base
from ...db_migrations import run_migrations, get_head_revision

logger = logging.getLogger(__name__)

MIGRATION_CACHE_PATH = "data/migration_status.json"

class SQLiteConnectionManager:
    def __init__(self, db_path: str, default_db_path: str):
        self.db_path = db_path
        self.default_db_path = default_db_path
        self.engine = None
        self.conn = None

    def _determine_db_connection_string(self, actual_db_path: str) -> str:
        if actual_db_path == ":memory:":
            logger.info("Using in-memory SQLite database.")
            return "sqlite:///:memory:"
        elif str(actual_db_path).startswith("file:"):
            db_connection_str = f"sqlite:///{actual_db_path}"
            if "uri=true" not in actual_db_path:
                db_connection_str += ("&" if "?" in actual_db_path else "?") + "uri=true"
            return db_connection_str
        else:
            return f"sqlite:///{actual_db_path}"

    def _handle_in_memory_db_setup(self, actual_db_path_for_logging: str) -> None:
        logger.info(f"Initializing IN-MEMORY SQLite database ({actual_db_path_for_logging}): using create_all().")
        assert self.engine is not None
        Base.metadata.create_all(self.engine)
        logger.info(f"In-memory database ({actual_db_path_for_logging}) schema created using create_all().")

    def _get_disk_db_path_for_existence_check(self, actual_db_path: str) -> Path:
        path_to_check_existence = actual_db_path
        if str(actual_db_path).startswith("file:"):
            path_to_check_existence = actual_db_path.split('?')[0]
            if path_to_check_existence.startswith("file:"):
                path_to_check_existence = path_to_check_existence[len("file:"):]
                if path_to_check_existence.startswith('///'):
                    path_to_check_existence = path_to_check_existence[2:]
                elif path_to_check_existence.startswith('/'):
                     pass
        return Path(path_to_check_existence)

    def _update_migration_cache(self, migration_cache_file: Path, actual_db_path: str, revision: Optional[str]) -> None:
        if not revision:
            logger.warning(f"No revision provided to update migration cache for {actual_db_path}.")
            return
        try:
            migration_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(migration_cache_file, "w") as f_cache:
                json.dump({"db_path": actual_db_path, "revision": revision}, f_cache)
            logger.info(f"Migration cache updated for {actual_db_path} with revision {revision}")
        except IOError as e:
            logger.warning(f"Could not write migration cache file {migration_cache_file}: {e}")

    def _manage_new_disk_db_migrations(self, actual_db_path: str, db_connection_str: str, migration_cache_file: Path) -> None:
        logger.info(f"On-disk database {actual_db_path} is new. Running migrations and stamping with head revision.")
        db_rev_after_migration = run_migrations(db_url=db_connection_str)
        logger.info(f"Migrations completed for new on-disk database {actual_db_path}. Reported database revision: {db_rev_after_migration}")

        if db_rev_after_migration:
            self._update_migration_cache(migration_cache_file, actual_db_path, db_rev_after_migration)
        else:
            logger.warning(f"Could not determine revision after stamping new on-disk database {actual_db_path}. Cache not updated.")

    def _manage_existing_disk_db_migrations(self, actual_db_path: str, db_connection_str: str, migration_cache_file: Path) -> None:
        logger.info(f"Existing on-disk database {actual_db_path} found. Checking migration status.")
        cached_revision: Optional[str] = None
        if migration_cache_file.exists():
            try:
                with open(migration_cache_file, "r") as f:
                    cache_data = json.load(f)
                if cache_data.get("db_path") == actual_db_path:
                    cached_revision = cache_data.get("revision")
                    logger.info(f"Found cached migration revision: {cached_revision} for {actual_db_path}")
                else:
                    logger.warning(f"Cache file {migration_cache_file} db_path ({cache_data.get('db_path')}) does not match current {actual_db_path}. Ignoring cache.")
            except Exception as e:
                logger.warning(f"Could not read migration cache file {migration_cache_file}: {e}")

        current_head_script_revision = get_head_revision(db_connection_str)
        logger.info(f"Determined current head script revision: {current_head_script_revision}")

        run_migrations_needed = False
        if cached_revision is None:
            logger.info(f"No valid cached revision found for {actual_db_path}. Migrations will run.")
            run_migrations_needed = True
        elif current_head_script_revision is None:
            logger.warning(f"Could not determine head script revision for {actual_db_path}. Migrations will run as a precaution.")
            run_migrations_needed = True
        elif cached_revision != current_head_script_revision:
            logger.info(f"Cached revision {cached_revision} differs from head script revision {current_head_script_revision} for {actual_db_path}. Migrations will run.")
            run_migrations_needed = True
        else:
            logger.info(f"Cached revision {cached_revision} matches head script revision {current_head_script_revision}. Migrations will be skipped.")

        if run_migrations_needed:
            logger.info(f"Running migrations for existing on-disk database {actual_db_path}...")
            db_rev_after_migration = run_migrations(db_url=db_connection_str)
            logger.info(f"Migrations completed for {actual_db_path}. Reported database revision: {db_rev_after_migration}")

            if db_rev_after_migration:
                self._update_migration_cache(migration_cache_file, actual_db_path, db_rev_after_migration)
            else:
                logger.warning(f"run_migrations did not return a new revision for {actual_db_path} despite being run. Cache not updated with new revision.")

        logger.info(f"Initialization for existing on-disk database {actual_db_path} complete.")

    def _handle_on_disk_db_setup(self, actual_db_path: str, db_connection_str: str) -> None:
        logger.info(f"Initializing ON-DISK SQLite database ({actual_db_path}): using Alembic migrations.")

        disk_db_path_obj = self._get_disk_db_path_for_existence_check(actual_db_path)

        if not str(actual_db_path).startswith("file:") and not actual_db_path == ":memory:":
             disk_db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        is_new_disk_db = not (disk_db_path_obj.exists() and disk_db_path_obj.stat().st_size > 0)
        migration_cache_file = Path(MIGRATION_CACHE_PATH)

        if is_new_disk_db:
            self._manage_new_disk_db_migrations(actual_db_path, db_connection_str, migration_cache_file)
        else:
            self._manage_existing_disk_db_migrations(actual_db_path, db_connection_str, migration_cache_file)

    def initialize(self) -> None:
        actual_db_path = self.db_path if self.db_path is not None else self.default_db_path
        logger.info(f"Initializing SQLite backend for db: {actual_db_path}")

        db_connection_str = self._determine_db_connection_string(actual_db_path)

        if self.engine is None:
            logger.info(f"Creating SQLAlchemy engine for {db_connection_str}")
            self.engine = create_engine(db_connection_str, future=True)

        is_in_memory_type = (actual_db_path == ":memory:") or \
                            (str(actual_db_path).startswith("file:") and "mode=memory" in actual_db_path)

        if is_in_memory_type:
            self._handle_in_memory_db_setup(actual_db_path)
        else:
            self._handle_on_disk_db_setup(actual_db_path, db_connection_str)

    def _ensure_connected(self) -> None:
        if self.engine is None:
            logger.warning("Engine not initialized. Attempting to initialize now in _ensure_connected.")
            self.initialize()
            if self.engine is None:
                 raise ConnectionError("Failed to initialize database engine.")

        if self.conn is None or self.conn.closed: # type: ignore[attr-defined]
            assert self.engine is not None
            logger.debug(f"Establishing new connection for {self.engine.url}")
            self.conn = self.engine.connect()

    def close(self) -> None:
        if self.conn and not self.conn.closed: # type: ignore[attr-defined]
            logger.info(f"Closing SQLAlchemy connection for {self.db_path or self.default_db_path}")
            self.conn.close()

    def get_connection(self):
        self._ensure_connected()
        return self.conn
