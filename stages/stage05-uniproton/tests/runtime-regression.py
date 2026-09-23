#!/usr/bin/env python3
"""TL3572 M5.3 RPMsg TTY and lifecycle regression test.

Run on the target as root while micad.service is active.
"""

import argparse
import os
import select
import subprocess
import termios
import time
import tty


TTY_PATH = "/dev/ttyRPMSG0"


def command(*args: str) -> str:
    result = subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}"
        )
    return result.stdout


def wait_running(timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        last = command("mcsctl", "status")
        if "up0" in last and "Running" in last and os.path.exists(TTY_PATH):
            return
        time.sleep(0.1)
    raise RuntimeError(f"up0 did not become ready:\n{last}")


def open_tty() -> int:
    fd = os.open(TTY_PATH, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    tty.setraw(fd)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def make_payload(index: int, size: int) -> bytes:
    prefix = f"M5-{index:06d}-".encode("ascii")
    if size < len(prefix):
        raise ValueError(f"payload size must be at least {len(prefix)}")
    return prefix + bytes([65 + index % 26]) * (size - len(prefix))


def echo_once(fd: int, payload: bytes, timeout: float = 3.0) -> int:
    written = os.write(fd, payload)
    if written != len(payload):
        raise RuntimeError(f"short write: {written}/{len(payload)}")

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
        f"echo timeout: payload={payload[:32]!r}, received={bytes(received[:160])!r}"
    )


def run_echo(count: int, payload_size: int) -> None:
    wait_running()
    fd = open_tty()
    total_rx = 0
    started = time.monotonic()
    try:
        for index in range(1, count + 1):
            total_rx += echo_once(fd, make_payload(index, payload_size))
            if index % 1000 == 0:
                print(f"echo progress: {index}/{count}", flush=True)
    finally:
        os.close(fd)
    elapsed = time.monotonic() - started
    print(
        f"echo PASS: count={count}, payload={payload_size}, "
        f"rx_bytes={total_rx}, elapsed={elapsed:.3f}s"
    )


def run_lifecycle(count: int, payload_size: int) -> None:
    wait_running()
    started = time.monotonic()
    for index in range(1, count + 1):
        command("mcsctl", "stop", "up0")
        command("mcsctl", "start", "up0")
        wait_running()
        fd = open_tty()
        try:
            echo_once(fd, make_payload(index, payload_size))
        finally:
            os.close(fd)
        if index % 10 == 0 or index == count:
            print(f"lifecycle progress: {index}/{count}", flush=True)
    elapsed = time.monotonic() - started
    print(
        f"lifecycle PASS: count={count}, payload={payload_size}, elapsed={elapsed:.3f}s"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--echo-count", type=int, default=0)
    parser.add_argument("--lifecycle-count", type=int, default=0)
    parser.add_argument("--payload-size", type=int, default=64)
    args = parser.parse_args()
    if args.payload_size > 451:
        parser.error("payload must be <=451 so the echoed frame fits the 496-byte RPMsg MTU")
    if args.echo_count < 0 or args.lifecycle_count < 0:
        parser.error("counts must be non-negative")
    if args.echo_count == 0 and args.lifecycle_count == 0:
        parser.error("request at least one test")

    if args.echo_count:
        run_echo(args.echo_count, args.payload_size)
    if args.lifecycle_count:
        run_lifecycle(args.lifecycle_count, args.payload_size)


if __name__ == "__main__":
    main()
