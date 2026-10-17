"""Run the local API and Nuxt server with one lifecycle and no shell interpolation."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def port_from_env(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if not 1 <= value <= 65535:
        raise ValueError(f"{name} must be a port from 1 to 65535")
    return value


def ensure_available(port: int) -> None:
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(
                f"Port {port} is in use. Stop that server or set REWIND_API_PORT / REWIND_WEB_PORT."
            ) from error


def main() -> int:
    api_port = port_from_env("REWIND_API_PORT", 8000)
    web_port = port_from_env("REWIND_WEB_PORT", 3000)
    ensure_available(api_port)
    ensure_available(web_port)
    if api_port == web_port:
        raise ValueError("The API and web server need different ports")
    processes: list[subprocess.Popen[bytes]] = []
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    environment = os.environ.copy()
    environment["NUXT_API_BASE"] = f"http://127.0.0.1:{api_port}"
    frontend_directory = Path(os.environ.get("REWIND_FRONTEND_DIR", ROOT / "frontend"))
    commands = [
        (
            [
                "uv",
                "run",
                "--project",
                "backend",
                "uvicorn",
                "rewind.main:create_app",
                "--factory",
                "--app-dir",
                "backend",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
                "--reload",
                "--reload-dir",
                "backend/rewind",
            ],
            ROOT,
        ),
        (
            ["bun", "run", "dev", "--host", "127.0.0.1", "--port", str(web_port)],
            frontend_directory,
        ),
    ]
    print(
        f"Rewind → http://127.0.0.1:{web_port}  |  API docs → http://127.0.0.1:{api_port}/docs",
        flush=True,
    )
    try:
        for command, directory in commands:
            processes.append(
                subprocess.Popen(
                    command, cwd=directory, env=environment, start_new_session=True
                )
            )
        while not stopping:
            for process in processes:
                if process.poll() is not None:
                    print(
                        f"A server exited ({process.returncode}); stopping both servers.",
                        file=sys.stderr,
                    )
                    return process.returncode or 1
            time.sleep(0.2)
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Cannot start Rewind: {error}", file=sys.stderr)
        sys.exit(1)
