"""``python -m deiy`` starts the API server."""

from __future__ import annotations

import os

import uvicorn

from deiy import create_app


def main() -> None:
    uvicorn.run(
        create_app(),
        host=os.environ.get("DEIY_HOST", "0.0.0.0"),
        port=int(os.environ.get("DEIY_PORT", "8000")),
        log_level=os.environ.get("DEIY_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
