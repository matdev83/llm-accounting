import subprocess
import sys
import tempfile
import pathlib
import shutil
import pytest # Added for the packaging marker

@pytest.mark.packaging # Added packaging marker
def test_packaging_integrity():
    """
    Tests the packaging integrity of the llm-accounting package.
    It creates a virtual environment, installs the package from a built wheel,
    and runs a simple client application to ensure basic functionality.
    """
    with tempfile.TemporaryDirectory() as tmpdir_name:
        tmpdir = pathlib.Path(tmpdir_name)

        # 1. Create a virtual environment
        venv_path = tmpdir / "venv_test_packaging"
        try:
            # Use sys.executable to ensure we're using the same Python that's running the test
            # Using "virtualenv" module instead of "venv" due to ensurepip issues
            venv_process = subprocess.run(
                [sys.executable, "-m", "virtualenv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"Venv creation stdout: {venv_process.stdout}")
            if venv_process.stderr:
                print(f"Venv creation stderr: {venv_process.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"Venv creation failed. Exit code: {e.returncode}")
            print(f"Venv creation stdout: {e.stdout}")
            print(f"Venv creation stderr: {e.stderr}")
            raise

        # Determine the path to the Python interpreter in the virtual environment
        if sys.platform == "win32":
            venv_python_interpreter = venv_path / "Scripts" / "python.exe"
            venv_pip_executable = venv_path / "Scripts" / "pip.exe"
            venv_hatch_executable = venv_path / "Scripts" / "hatch.exe"
        else:
            venv_python_interpreter = venv_path / "bin" / "python"
            venv_pip_executable = venv_path / "bin" / "pip"
            venv_hatch_executable = venv_path / "bin" / "hatch"

        # Install hatch and virtualenv into the temporary venv
        print(f"Installing hatch and virtualenv into temporary venv: {venv_path}")
        try:
            install_tools_process = subprocess.run(
                [str(venv_pip_executable), "install", "hatch", "virtualenv"],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"Install tools stdout: {install_tools_process.stdout}")
            if install_tools_process.stderr:
                print(f"Install tools stderr: {install_tools_process.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"Installation of hatch/virtualenv into temporary venv failed. Exit code: {e.returncode}")
            print(f"Install tools stdout: {e.stdout}")
            print(f"Install tools stderr: {e.stderr}")
            raise

        # 2. Define and write the client_app.py
        client_app_content = """
import llm_accounting
import sys
from datetime import datetime # Added import

def main():
    try:
        print(f"llm_accounting module path: {llm_accounting.__file__}")
        # Corrected backend initialization for in-memory SQLite
        backend_instance = llm_accounting.SQLiteBackend(db_path=":memory:")
        # Initialize LLMAccounting with project_name, app_name, user_name for complete UsageEntry
        accounting = llm_accounting.LLMAccounting(
            backend=backend_instance,
            project_name="test_project",
            app_name="test_app",
            user_name="test_user"
        )
        accounting.track_usage( # Changed log_event to track_usage
            model="test_model",      # Was model_name
            prompt_tokens=100,       # Was input_tokens
            completion_tokens=50,    # Was output_tokens
            cost=0.01
            # provider="test_provider" - 'provider' is not a direct param of track_usage.
            # Caller/username/project are set in LLMAccounting constructor or passed to track_usage.
        )
        # Changed get_stats to get_period_stats with a wide range
        stats = accounting.get_period_stats(start=datetime(2000, 1, 1), end=datetime.utcnow())
        print(f"Stats: {stats}")
        print("CLIENT_APP_SUCCESS")
    except Exception as e:
        print(f"Client app error: {e}", file=sys.stderr)
        sys.exit(1) # Ensure non-zero exit code on error

if __name__ == "__main__":
    main()
"""
        client_app_path = tmpdir / "client_app.py"
        with open(client_app_path, "w") as f:
            f.write(client_app_content)

        # 3. Build the llm-accounting package as a wheel
        project_root = pathlib.Path(__file__).resolve().parent.parent

        dist_dir = project_root / "dist"
        if dist_dir.exists():
            print(f"Cleaning existing dist directory: {dist_dir}")
            shutil.rmtree(dist_dir)
        dist_dir.mkdir(parents=True, exist_ok=True)

        print(f"Building wheel in project root: {project_root}")
        try:
            build_process = subprocess.run(
                [str(venv_python_interpreter), "-m", "hatch", "build", "-t", "wheel"],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True
            )
            print(f"Build stdout: {build_process.stdout}")
            if build_process.stderr:
                print(f"Build stderr: {build_process.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"Build failed. Exit code: {e.returncode}")
            print(f"Build stdout: {e.stdout}")
            print(f"Build stderr: {e.stderr}")
            raise
        except FileNotFoundError:
            print("Build failed: 'hatch' command not found. Ensure hatch is installed and in PATH.")
            raise

        # 4. Find the path to the built wheel file
        try:
            wheel_files = list(dist_dir.glob("llm_accounting-*.whl"))
            if not wheel_files:
                raise FileNotFoundError(f"No 'llm_accounting-*.whl' file found in {dist_dir}. Contents: {list(dist_dir.iterdir())}")
            if len(wheel_files) > 1:
                print(f"Warning: Multiple wheel files found, using the first one: {wheel_files}")
            wheel_file_path = wheel_files[0]
            print(f"Found wheel file: {wheel_file_path}")
        except FileNotFoundError as e:
            print(f"Wheel file discovery failed: {e}")
            raise

        # 5. Install the wheel into the created virtual environment
        print(f"Installing wheel {wheel_file_path} using {venv_python_interpreter}")
        try:
            install_process = subprocess.run(
                [str(venv_python_interpreter), "-m", "pip", "install", str(wheel_file_path)],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"Install stdout: {install_process.stdout}")
            if install_process.stderr:
                 print(f"Install stderr: {install_process.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"Installation failed. Exit code: {e.returncode}")
            print(f"Installation stdout: {e.stdout}")
            print(f"Installation stderr: {e.stderr}")
            raise

        # 6. Run the client_app.py using the virtual environment's Python interpreter
        print(f"Running client_app.py using {venv_python_interpreter} from {tmpdir}")
        run_app_process = subprocess.run(
            [str(venv_python_interpreter), str(client_app_path)],
            capture_output=True,
            text=True,
            cwd=tmpdir
        )

        client_stdout = run_app_process.stdout
        client_stderr = run_app_process.stderr
        client_exit_code = run_app_process.returncode

        print(f"Client app stdout:\n{client_stdout}")
        print(f"Client app stderr:\n{client_stderr}")
        print(f"Client app exit code: {client_exit_code}")

        # 7. Assertions
        assert client_exit_code == 0, f"Client app exited with non-zero status: {client_exit_code}. Stderr: {client_stderr}"
        assert "CLIENT_APP_SUCCESS" in client_stdout, f"Client app success message not found in stdout. Stdout: {client_stdout}"

        if client_stderr:
            # Filter out known non-critical messages from stderr
            filtered_stderr_lines = []
            for line in client_stderr.splitlines():
                if "INFO  [alembic.runtime.migration]" in line:
                    continue
                if "DeprecationWarning: datetime.datetime.utcnow()" in line:
                    continue
                filtered_stderr_lines.append(line)

            filtered_stderr = "\n".join(filtered_stderr_lines)

            assert "ERROR" not in filtered_stderr.upper(), f"Error found in client app stderr: {filtered_stderr}"
            assert "FAIL" not in filtered_stderr.upper(), f"Failure found in client app stderr: {filtered_stderr}"
            # Re-evaluate if any other warnings should be explicitly ignored or if this check is too broad.
            # For now, we'll only check for explicit ERROR or FAIL.

if __name__ == "__main__":
    print("Running test_packaging_integrity directly for debugging...")
    expected_pyproject_path = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not expected_pyproject_path.exists():
        print(f"Warning: pyproject.toml not found at expected location: {expected_pyproject_path}")
        print("Make sure you are running this script from the project's root directory,")
        print("or that the project structure is as expected.")

    test_packaging_integrity()
    print("test_packaging_integrity executed (if run directly). Review output above.")
