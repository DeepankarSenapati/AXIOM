"""Isolation and shutdown regressions for the local-only demo launcher."""

import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts import demo


pytestmark = pytest.mark.skipif(os.name != "posix", reason="demo launcher is macOS/Linux only")


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def running(pid):
    result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], text=True, capture_output=True)
    return result.returncode == 0 and bool(result.stdout.strip()) and not result.stdout.strip().startswith("Z")


def test_service_exit_stops_its_stubborn_descendant_without_touching_another_process(tmp_path):
    pid_file = tmp_path / "child.pid"
    child_code = (
        "import os,signal,sys,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "open(sys.argv[1], 'w').write(str(os.getpid())); "
        "time.sleep(30)"
    )
    service_code = (
        "import os,subprocess,sys,time; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]]); "
        "deadline=time.monotonic()+5; "
        "\nwhile not os.path.exists(sys.argv[1]) and time.monotonic()<deadline: time.sleep(.02)\n"
    )
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    service = None
    child_pid = None
    try:
        with (tmp_path / "service.log").open("w") as log:
            service = demo.start_service(
                [sys.executable, "-c", service_code, str(pid_file), child_code], tmp_path, os.environ.copy(), log,
            )
            assert wait_until(lambda: pid_file.exists() and pid_file.stat().st_size > 0)
            child_pid = int(pid_file.read_text())
            assert wait_until(lambda: service[0].poll() is not None)
            assert wait_until(lambda: not running(child_pid))
            assert unrelated.poll() is None
            demo.stop_processes([service])
            service = None
    finally:
        if service is not None:
            demo.stop_processes([service])
        if child_pid is not None and running(child_pid):
            os.kill(child_pid, signal.SIGKILL)
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_closing_control_pipe_stops_a_live_service(tmp_path):
    pid_file = tmp_path / "service.pid"
    code = "import os,sys,time; open(sys.argv[1], 'w').write(str(os.getpid())); time.sleep(30)"
    with (tmp_path / "service.log").open("w") as log:
        service = demo.start_service([sys.executable, "-c", code, str(pid_file)], tmp_path, os.environ.copy(), log)
        try:
            assert wait_until(lambda: pid_file.exists() and pid_file.stat().st_size > 0)
            pid = int(pid_file.read_text())
        finally:
            demo.stop_processes([service])
        assert wait_until(lambda: not running(pid))


def test_readiness_rejects_an_unrelated_healthy_server(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(demo, "STARTUP_TIMEOUT", 0.3)
    try:
        with pytest.raises(RuntimeError, match="did not become ready"):
            demo.wait_for(f"http://127.0.0.1:{server.server_port}/health", [], b"unique-launch-nonce")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_supervisor_refuses_to_run_in_the_callers_process_group():
    result = subprocess.run(
        [sys.executable, str(demo.ROOT / "scripts" / "demo_supervisor.py"), "0", "unused"],
        text=True, capture_output=True, timeout=5,
    )
    assert result.returncode == 2
    assert "own session" in result.stderr
