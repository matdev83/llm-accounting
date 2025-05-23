import unittest
import subprocess
import sys

# Assuming the main CLI script is executable and in the Python path
# Adjust if the entry point is different, e.g., a function call
LLM_ACCOUNTING_CLI = [sys.executable, "-m", "llm_accounting.cli.main"]

class TestCliAPI(unittest.TestCase):
    def test_cli_help_option(self):
        """Test that the CLI responds to --help."""
        try:
            result = subprocess.run(
                LLM_ACCOUNTING_CLI + ["--help"],
                capture_output=True,
                text=True,
                check=True,
                env={"PYTHONPATH": "src"}  # Ensure src is in PYTHONPATH
            )
            self.assertIn("usage: main.py", result.stdout.lower())
            self.assertIn("llm accounting cli - track and analyze llm usage", result.stdout.lower()) # Check for description
        except subprocess.CalledProcessError as e:
            self.fail(f"CLI --help command failed: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}")
        except FileNotFoundError:
            self.fail("CLI script not found. Ensure llm_accounting.cli.main is accessible.")

    def test_cli_version_option(self):
        """Test that the CLI responds to --version (if implemented)."""
        # First, check if --version is a known argument from --help
        try:
            help_result = subprocess.run(
                LLM_ACCOUNTING_CLI + ["--help"],
                capture_output=True, text=True, check=True, env={"PYTHONPATH": "src"}
            )
            if "--version" not in help_result.stdout:
                self.skipTest("--version option not found in --help output.")
        except subprocess.CalledProcessError as e:
            self.fail(f"CLI --help command failed while checking for version: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}")
        except FileNotFoundError:
            self.fail("CLI script not found for version test. Ensure llm_accounting.cli.main is accessible.")

        try:
            result = subprocess.run(
                LLM_ACCOUNTING_CLI + ["--version"],
                capture_output=True,
                text=True,
                check=True,
                env={"PYTHONPATH": "src"}
            )
            # We don't know the exact version, but it should output something.
            self.assertTrue(len(result.stdout.strip()) > 0)
        except subprocess.CalledProcessError as e:
            self.fail(f"CLI --version command failed: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}")

    def test_cli_subcommands_exist_and_help(self):
        """Test that core subcommands exist and respond to --help."""
        subcommands = [
            "stats",
            "purge",
            "tail",
            "select",
            "track",
            "limits",
        ]
        for subcommand in subcommands:
            with self.subTest(subcommand=subcommand):
                try:
                    result = subprocess.run(
                        LLM_ACCOUNTING_CLI + [subcommand, "--help"],
                        capture_output=True,
                        text=True,
                        check=True,
                        env={"PYTHONPATH": "src"}
                    )
                    # Check that the usage for the subcommand is printed
                    self.assertIn(f"usage: main.py {subcommand}", result.stdout.lower())
                except subprocess.CalledProcessError as e:
                    self.fail(f"CLI command '{subcommand} --help' failed: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}")
                except FileNotFoundError:
                    self.fail(f"CLI script not found for subcommand '{subcommand}'. Ensure llm_accounting.cli.main is accessible.")

if __name__ == "__main__":
    unittest.main()
