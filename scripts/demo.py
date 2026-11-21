#!/usr/bin/env python3
"""Start a local, disposable AXIOM demo without touching the project's DB.

From the project root with dependencies installed: python scripts/demo.py
The temporary database is removed on normal exit; exports and browser storage
remain. Both servers bind to loopback and only processes started here are stopped.
"""

import importlib.util
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
STARTUP_TIMEOUT = 30.0
LOOPBACK_OPENER = build_opener(ProxyHandler({}))


def free_port(exclude: int | None = None) -> int:
    """Find an available loopback port; children fail if another process takes it."""
    for _ in range(20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        if port != exclude:
            return port
    raise RuntimeError("Could not select two separate loopback ports.")


def wait_for(url: str, processes: list[subprocess.Popen], expected: bytes) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("A demo service exited before it was ready.")
        try:
            with LOOPBACK_OPENER.open(url, timeout=1) as response:
                if response.status == 200 and expected in response.read(200_000):
                    return
        except (OSError, URLError):
            pass
        time.sleep(0.15)
    raise RuntimeError(f"A demo service did not become ready at {url}.")


def start_service(command: list[str], cwd: Path, env: dict[str, str], log: object) -> tuple[subprocess.Popen, int]:
    read_fd, write_fd = os.pipe()
    try:
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "demo_supervisor.py"), str(read_fd), *command],
            cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
            pass_fds=(read_fd,), start_new_session=True,
        )
    except BaseException:
        os.close(read_fd)
        os.close(write_fd)
        raise
    os.close(read_fd)
    return process, write_fd


def stop_processes(services: list[tuple[subprocess.Popen, int]]) -> None:
    for _process, write_fd in reversed(services):
        os.close(write_fd)
    for process, _write_fd in reversed(services):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Do not signal a process group from the parent: its numeric ID
            # could be recycled. The supervisor owns its own group cleanup.
            print("A demo supervisor did not stop; check its process before retrying.", file=sys.stderr)
            raise


def main() -> int:
    if os.name != "posix":
        print("This launcher currently supports macOS and Linux. See docs/SURVIVAL_LAB.md for two-terminal setup.")
        return 1
    if importlib.util.find_spec("uvicorn") is None or importlib.util.find_spec("fastapi") is None:
        print("Backend dependencies are missing. Activate the project virtual environment and install requirements first.")
        return 1
    node = shutil.which("node")
    vite = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    if node is None or not vite.exists():
        print("Frontend dependencies are missing. Install Node.js and run 'npm ci' in frontend first.")
        return 1

    print("AXIOM LOCAL DEMO — synthetic data and simulated activity only.", flush=True)
    print("The temporary demo database resets on normal shutdown. Your existing database is not used.", flush=True)
    print("Browser storage, downloaded exports and the project app.log are not reset. Demo credentials are public.", flush=True)

    services: list[tuple[subprocess.Popen, int]] = []
    handled_signals = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
    previous_handlers = {sig: signal.getsignal(sig) for sig in handled_signals}

    def interrupt(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    for sig in handled_signals:
        signal.signal(sig, interrupt)
    demo_dir: Path | None = None
    status = 0
    try:
        demo_dir = Path(tempfile.mkdtemp(prefix="axiom-demo-"))
        backend_port = free_port()
        frontend_port = free_port(backend_port)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), env.get("PYTHONPATH", "")]))
        env["AXIOM_DEMO_API_PORT"] = str(backend_port)
        nonce = secrets.token_hex(16)
        env["AXIOM_DEMO_READINESS_NONCE"] = nonce
        marker = nonce.encode("ascii")
        log_path = demo_dir / "startup.log"
        with log_path.open("w", encoding="utf-8") as log:
            services.append(start_service(
                [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(backend_port)],
                demo_dir, env, log,
            ))
            wait_for(f"http://127.0.0.1:{backend_port}/health", [service[0] for service in services], marker)
            services.append(start_service(
                [node, str(vite), "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
                FRONTEND, env, log,
            ))
            processes = [service[0] for service in services]
            wait_for(f"http://127.0.0.1:{frontend_port}/__axiom_demo_ready", processes, marker)
            wait_for(f"http://127.0.0.1:{frontend_port}/health", processes, marker)
            wait_for(f"http://127.0.0.1:{frontend_port}/lab", processes, b'<div id="root">')
            print(f"\nDemo ready: http://127.0.0.1:{frontend_port}/lab", flush=True)
            print("Use Explore demo credentials on the sign-in screen. If an old session appears, sign out and back in.", flush=True)
            print("Press Ctrl+C to stop both services and remove the temporary database.", flush=True)
            while all(process.poll() is None for process in processes):
                time.sleep(0.5)
            raise RuntimeError("A demo service stopped unexpectedly.")
    except KeyboardInterrupt:
        print("\nStopping the isolated demo…", flush=True)
    except Exception as exc:
        status = 1
        print(f"\nCould not keep the demo running: {exc}", file=sys.stderr, flush=True)
        log_path = demo_dir / "startup.log" if demo_dir else None
        if log_path and log_path.exists():
            print(log_path.read_text(encoding="utf-8", errors="replace")[-5000:], file=sys.stderr)
    finally:
        for sig in handled_signals:
            signal.signal(sig, signal.SIG_IGN)
        try:
            try:
                stop_processes(services)
            except (OSError, subprocess.TimeoutExpired):
                status = 1
                if demo_dir:
                    print(f"Shutdown could not be confirmed. Temporary demo files retained at {demo_dir}.", file=sys.stderr, flush=True)
            else:
                if demo_dir:
                    try:
                        shutil.rmtree(demo_dir)
                    except OSError as exc:
                        status = 1
                        print(f"Could not remove temporary demo files at {demo_dir}: {exc}", file=sys.stderr, flush=True)
                    else:
                        print("Temporary demo database removed; browser storage, downloads and app.log remain.", flush=True)
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
    return status


if __name__ == "__main__":
    sys.exit(main())
