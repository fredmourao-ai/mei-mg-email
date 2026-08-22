"""Compatibility wrapper for the single pre-send entrypoint."""
from worker.safe_entrypoint import main

if __name__ == "__main__":
    raise SystemExit(main())
