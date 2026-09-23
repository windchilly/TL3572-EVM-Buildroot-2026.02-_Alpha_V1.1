#!/usr/bin/env python3
"""Concurrent RPMsg and one-sided lifecycle regression for M6 dual UniProton."""

import argparse
import concurrent.futures
import os
import select
import subprocess
import termios
import time
import tty


def command(*args: str) -> str:
    result = subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=20,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}"
        )
    return result.stdout


def status_line(client: str) -> str:
    for line in command("mcsctl", "status").splitlines():
        if line.split(maxsplit=1)[0:1] == [client]:
            return line
    return ""


def wait_state(client: str, state: str, tty_path: str | None = None,
               timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        last = status_line(client)
        tty_ready = tty_path is None or os.path.exists(tty_path)
        if state in last and tty_ready:
            return
        time.sleep(0.1)
    raise RuntimeError(f"{client} did not reach {state}: {last}")


def open_tty(path: str) -> int:
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    tty.setraw(fd)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def make_payload(client: str, index: int, size: int) -> bytes:
    prefix = f"M6-{client}-{index:06d}-".encode("ascii")
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
        f"echo timeout: payload={payload[:40]!r}, received={bytes(received[:160])!r}"
    )


def echo_series(client: str, path: str, count: int, size: int) -> tuple[str, int, float]:
    wait_state(client, "Running", path)
    fd = open_tty(path)
    total_rx = 0
    started = time.monotonic()
    try:
        for index in range(1, count + 1):
            total_rx += echo_once(fd, make_payload(client, index, size))
            if index % 500 == 0:
                print(f"{client} echo progress: {index}/{count}", flush=True)
    finally:
        os.close(fd)
    return client, total_rx, time.monotonic() - started


def run_concurrent(pairs: list[tuple[str, str]], count: int, size: int) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(pairs)) as pool:
        futures = [pool.submit(echo_series, client, path, count, size)
                   for client, path in pairs]
        for future in concurrent.futures.as_completed(futures):
            client, total_rx, elapsed = future.result()
            print(
                f"{client} concurrent echo PASS: count={count}, payload={size}, "
                f"rx_bytes={total_rx}, elapsed={elapsed:.3f}s",
                flush=True,
            )


def run_isolation(pairs: list[tuple[str, str]], cycles: int, size: int) -> None:
    if len(pairs) != 2:
        raise ValueError("isolation test requires exactly two clients")
    started = time.monotonic()
    for cycle in range(1, cycles + 1):
        for victim_index in range(2):
            victim, victim_tty = pairs[victim_index]
            survivor, survivor_tty = pairs[1 - victim_index]
            command("mcsctl", "stop", victim)
            wait_state(victim, "Offline")
            wait_state(survivor, "Running", survivor_tty)

            survivor_fd = open_tty(survivor_tty)
            try:
                echo_once(survivor_fd, make_payload(survivor, cycle, size))
            finally:
                os.close(survivor_fd)

            command("mcsctl", "start", victim)
            wait_state(victim, "Running", victim_tty)
            wait_state(survivor, "Running", survivor_tty)

            victim_fd = open_tty(victim_tty)
            try:
                echo_once(victim_fd, make_payload(victim, cycle, size))
            finally:
                os.close(victim_fd)
        if cycle % 10 == 0 or cycle == cycles:
            print(f"isolation progress: {cycle}/{cycles}", flush=True)
    print(
        f"one-sided lifecycle PASS: clients={pairs[0][0]},{pairs[1][0]}, "
        f"cycles_each={cycles}, elapsed={time.monotonic() - started:.3f}s",
        flush=True,
    )


def parse_pair(value: str) -> tuple[str, str]:
    client, separator, path = value.partition(":")
    if not separator or not client or not path:
        raise argparse.ArgumentTypeError("pair must be CLIENT:/dev/ttyRPMSGx")
    return client, path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", action="append", type=parse_pair, required=True)
    parser.add_argument("--echo-count", type=int, default=0)
    parser.add_argument("--isolation-cycles", type=int, default=0)
    parser.add_argument("--payload-size", type=int, default=451)
    args = parser.parse_args()
    if not args.pair:
        parser.error("at least one --pair argument is required")
    if args.isolation_cycles > 0 and len(args.pair) != 2:
        parser.error("isolation testing requires exactly two --pair arguments")
    if args.payload_size > 451:
        parser.error("payload must be <=451 so the echoed frame fits the RPMsg MTU")
    if args.echo_count <= 0 and args.isolation_cycles <= 0:
        parser.error("request at least one test")

    if args.echo_count > 0:
        run_concurrent(args.pair, args.echo_count, args.payload_size)
    if args.isolation_cycles > 0:
        run_isolation(args.pair, args.isolation_cycles, args.payload_size)


if __name__ == "__main__":
    main()
