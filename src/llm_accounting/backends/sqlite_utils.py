from pathlib import Path


def validate_db_filename(filename: str):
    """Validate database filename meets requirements"""
    # Handle SQLite URI format
    clean_name = filename.split("?")[0].replace("file:", "")
    db_path = Path(clean_name)

    # Allow in-memory databases
    if clean_name == ":memory:":  # Handles ":memory:" after stripping "file:" and "?..."
        return

    # Allow full "file:...&mode=memory..." URIs without further checks on extension or path
    if filename.startswith("file:") and "mode=memory" in filename:
        return

    # Check for valid extensions
    if not any(
        clean_name.lower().endswith(ext) for ext in (".sqlite", ".sqlite3", ".db")
    ):
        raise ValueError(
            f"Invalid database filename '{filename}'. "
            "Must end with .sqlite, .sqlite3 or .db"
        )

    # Check for protected paths (Windows specific examples)
    protected_paths = [
        Path("C:/Windows"),
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
        Path("/root"),  # Common protected path on Linux/Unix
    ]

    # Normalize path for comparison
    absolute_db_path = db_path.resolve()

    def is_subpath(child, parent):
        try:
            child = child.resolve()
            parent = parent.resolve()
            return str(child).startswith(str(parent))
        except Exception:
            return False

    try:
        if any(
            is_subpath(absolute_db_path, protected_path)
            for protected_path in protected_paths
        ):
            raise PermissionError(
                f"Access to protected path '{filename}' is not allowed."
            )
    except Exception as e:
        raise PermissionError(
            f"Access to protected path '{filename}' is not allowed (error during path check: {str(e)})."
        )
