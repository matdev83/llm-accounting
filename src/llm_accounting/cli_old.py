"""
This module provides an old or alternative entry point for the LLM Accounting CLI.
It simply calls the main function from the current CLI implementation.
"""
from .cli.main import main

if __name__ == "__main__":
    main()
