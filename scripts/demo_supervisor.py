#!/usr/bin/env python3
"""Internal demo supervisor: keep a session alive until its whole group stops.

The parent owns the write side of control_fd. EOF (including parent death), a
child exit, or SIGTERM starts shutdown. This process remains the session leader
until it signals its own group, so no stale process-group ID is used.
"""

import os
import select
import signal
import subprocess
import sys
import time


def main() -> int:
    if os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid():
        print("Demo supervisor must be started in its own session.", file=sys.stderr)
        return 2
    if len(sys.argv) < 3:
        print("Demo supervisor requires a control pipe and a service command.", file=sys.stderr)
        return 2
    control_fd = int(sys.argv[1])
    command = sys.argv[2:]
    if not command:
        return 2
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        child = subprocess.Popen(command, close_fds=True)
        while not stopping and child.poll() is None:
            readable, _, _ = select.select([control_fd], [], [], 0.2)
            if readable and not os.read(control_fd, 1):
                break
    except Exception as exc:
        print(f"Demo supervisor could not start or monitor its service: {exc}", file=sys.stderr, flush=True)
    finally:
        os.close(control_fd)
        # We are still the live group leader while both signals are sent.
        # A stubborn child gets SIGKILL after a short graceful-stop window.
        os.killpg(os.getpgrp(), signal.SIGTERM)
        time.sleep(1)
        os.killpg(os.getpgrp(), signal.SIGKILL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
