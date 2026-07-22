"""Executable module for the MarktWert desktop application."""

from marktwert.bootstrap import run


def main() -> int:
    """Start MarktWert and return the process exit code."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
