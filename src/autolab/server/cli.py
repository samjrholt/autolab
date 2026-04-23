"""Thin CLI wrapper around uvicorn that accepts a --bootstrap argument.

Usage:
    python -m autolab.server.cli --bootstrap wsl_demo
    python -m autolab.server.cli --bootstrap add_demo --port 8001
    python -m autolab.server.cli --bootstrap none --reload

The --bootstrap value is injected as AUTOLAB_BOOTSTRAP before uvicorn
starts, avoiding the need for shell env var gymnastics across platforms.
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    if "pytest" not in sys.modules:
        from dotenv import load_dotenv

        load_dotenv()

    parser = argparse.ArgumentParser(
        prog="autolab-serve",
        description="Start the autolab Lab server.",
    )
    parser.add_argument(
        "--bootstrap",
        default=os.environ.get("AUTOLAB_BOOTSTRAP", "none"),
        help=(
            "Bootstrap mode. Default is 'none' — the Lab boots empty with "
            "'this-pc' as the only default Resource. Demo content is "
            "registered on top via POST /bootstraps/apply. Valid modes: "
            "none | mammos | demo_quadratic | add_demo | wsl_demo | "
            "wsl_ssh_demo | superellipse | <module>:<func>"
        ),
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--reload", action="store_true", default=False)
    parser.add_argument("--root", default=None, help="Lab root directory (overrides AUTOLAB_ROOT)")

    args = parser.parse_args()

    os.environ["AUTOLAB_BOOTSTRAP"] = args.bootstrap
    if args.root:
        os.environ["AUTOLAB_ROOT"] = args.root

    import uvicorn  # type: ignore[import]
    uvicorn.run(
        "autolab.server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
