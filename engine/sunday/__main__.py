"""Run Sunday: ``python -m sunday`` (host/port from .env via config.settings)."""

from __future__ import annotations

import uvicorn

from .config import settings


def main() -> None:
    uvicorn.run("sunday.app:app", host=settings.sunday_host, port=settings.sunday_port)


if __name__ == "__main__":
    main()
