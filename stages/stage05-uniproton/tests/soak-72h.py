#!/usr/bin/env python3
"""72-hour continuous RPMsg TTY soak for TL3572 M5 acceptance."""

import argparse
import datetime
import hashlib
import json
import os
import select
import subprocess
import tempfile
import termios
import time
import tty


TTY_PATH = "/dev/ttyRPMSG0"
DEFAULT_STATUS = "/root/m5-soak-72h.status.json"


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_status(path: str, state: dict) -> None:
    state["updated_at"] = utc_now()
    directory = os.path.dirname(path) or "."
    fd, temporary = tempfile.mkstemp(prefix=".m5-soak-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wait_running(timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["mcsctl", "status"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
        last = result.stdout
        if result.returncode == 0 and "up0" in last and "Running" in last:
            if os.path.exists(TTY_PATH):
                return
        time.sleep(0.2)
    raise RuntimeError(f"up0 did not become ready:\n{last}")


def make_payload(sequence: int, size: int) -> bytes:
    prefix = f"SOAK-{sequence:010d}-".encode("ascii")
    return prefix + bytes([65 + sequence % 26]) * (size - len(prefix))


def exchange(fd: int, payload: bytes, timeout: float) -> int:
    if os.write(fd, payload) != len(payload):
        raise RuntimeError("short RPMsg TTY write")
    deadline = time.monotonic() + timeout
    received = bytearray()
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], min(0.2, deadline - time.monotonic()))
        if not ready:
            continue
        try:
            received.extend(os.read(fd, 4096))
        except BlockingIOError:
            continue
        if payload in received:
            return len(received)
    raise RuntimeError(
        f"RPMsg echo timeout, payload={payload[:32]!r}, rx={bytes(received[:160])!r}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=int, default=72 * 60 * 60)
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--payload-size", type=int, default=451)
    parser.add_argument("--status", default=DEFAULT_STATUS)
    args = parser.parse_args()
    if args.duration_seconds <= 0 or args.interval < 0:
        parser.error("duration must be positive and interval non-negative")
    if not 16 <= args.payload_size <= 451:
        parser.error("payload size must be 16..451")

    wait_running()
    started_wall = datetime.datetime.now(datetime.timezone.utc)
    expected_end = started_wall + datetime.timedelta(seconds=args.duration_seconds)
    state = {
        "state": "RUNNING",
        "started_at": started_wall.isoformat(),
        "expected_end_at": expected_end.isoformat(),
        "duration_seconds": args.duration_seconds,
        "interval_seconds": args.interval,
        "payload_size": args.payload_size,
        "exchanges": 0,
        "rx_bytes": 0,
        "firmware_sha256": sha256("/lib/firmware/rk3572-uniproton.elf"),
        "micad_sha256": sha256("/usr/bin/micad"),
        "module_sha256": sha256("/lib/modules/mcs_km.ko"),
    }
    write_status(args.status, state)

    started = time.monotonic()
    next_report = started + 60.0
    fd = os.open(TTY_PATH, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    tty.setraw(fd)
    termios.tcflush(fd, termios.TCIOFLUSH)
    try:
        while time.monotonic() - started < args.duration_seconds:
            iteration_started = time.monotonic()
            sequence = state["exchanges"] + 1
            payload = make_payload(sequence, args.payload_size)
            state["rx_bytes"] += exchange(fd, payload, timeout=3.0)
            state["exchanges"] = sequence
            now = time.monotonic()
            if now >= next_report:
                state["elapsed_seconds"] = round(now - started, 3)
                write_status(args.status, state)
                print(
                    f"soak RUNNING: elapsed={state['elapsed_seconds']}s, "
                    f"exchanges={sequence}",
                    flush=True,
                )
                next_report = now + 60.0
            delay = args.interval - (time.monotonic() - iteration_started)
            if delay > 0:
                time.sleep(delay)
        state["state"] = "PASS"
        state["elapsed_seconds"] = round(time.monotonic() - started, 3)
        state["completed_at"] = utc_now()
        write_status(args.status, state)
        print(
            f"soak PASS: elapsed={state['elapsed_seconds']}s, "
            f"exchanges={state['exchanges']}, rx_bytes={state['rx_bytes']}",
            flush=True,
        )
    except BaseException as error:
        state["state"] = "FAIL"
        state["elapsed_seconds"] = round(time.monotonic() - started, 3)
        state["failed_at"] = utc_now()
        state["error"] = f"{type(error).__name__}: {error}"
        write_status(args.status, state)
        raise
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
