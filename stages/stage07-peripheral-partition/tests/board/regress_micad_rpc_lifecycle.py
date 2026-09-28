#!/usr/bin/env python3
"""Board-only RPC log lifetime regression; touches only the two named M7 clients."""

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import time


def load_echo_helper(path):
    spec = importlib.util.spec_from_file_location("m6_echo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def daemon_state():
    output = subprocess.check_output(
        ["systemctl", "show", "micad", "-p", "MainPID", "-p", "NRestarts",
         "-p", "ActiveState"], text=True, timeout=10,
    )
    values = dict(line.split("=", 1) for line in output.splitlines())
    if values["ActiveState"] != "active" or int(values["MainPID"]) <= 0:
        raise RuntimeError(f"micad not active: {output}")
    return int(values["MainPID"]), int(values["NRestarts"])


def file_handles(pid):
    handles = []
    for path in Path(f"/proc/{pid}/fd").iterdir():
        try:
            handles.append(os.readlink(path))
        except FileNotFoundError:
            continue
    return handles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-a", default="up-a-m7")
    parser.add_argument("--client-b", default="up-b-m7")
    parser.add_argument("--cycles-per-order", type=int, default=20)
    parser.add_argument("--echo-count", type=int, default=1000)
    parser.add_argument("--isolation-cycles", type=int, default=10)
    parser.add_argument("--echo-helper", type=Path,
                        default=Path(__file__).with_name("dual-runtime-regression.py"))
    args = parser.parse_args()
    if args.cycles_per_order < 1 or args.echo_count < 1 or args.isolation_cycles < 0:
        parser.error("request positive cycles/echo count and nonnegative isolation cycles")
    if args.client_a == args.client_b:
        parser.error("clients must differ")

    echo = load_echo_helper(args.echo_helper)
    clients = (args.client_a, args.client_b)
    cpus = {args.client_a: 4, args.client_b: 5}
    baseline = daemon_state()

    def check_daemon():
        current = daemon_state()
        if current != baseline:
            raise RuntimeError(f"micad changed: baseline={baseline}, now={current}")

    def cpu_off(cpu):
        subprocess.run(
            ["python3", str(Path(__file__).with_name("query_cpu_off.py")), str(cpu)],
            check=True, timeout=10,
        )

    def log_fds(running):
        check_daemon()
        handles = file_handles(baseline[0])
        expected = 1 if running else 0
        for name in ("/tmp/rpc_accesslog", "/tmp/rpc_log.txt"):
            if handles.count(name) != expected:
                raise RuntimeError(f"{name}: expected {expected}, handles={handles}")
        return len(handles)

    def control(action, client):
        output = echo.command("mcsctl", action, client)
        if "success" not in output.lower():
            raise RuntimeError(f"{action} {client}: no success response: {output}")
        check_daemon()

    def start_order(order):
        pairs = []
        for client in order:
            before = set(Path("/dev").glob("ttyRPMSG*"))
            control("start", client)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                added = set(Path("/dev").glob("ttyRPMSG*")) - before
                if len(added) == 1:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError(f"{client}: missing unique new RPMsg tty")
            path = str(added.pop())
            echo.wait_state(client, "Running", path)
            echo.echo_series(client, path, 1, 451)
            pairs.append((client, path))
            log_fds(True)
        return pairs

    def stop_order(order):
        for index, client in enumerate(order):
            control("stop", client)
            echo.wait_state(client, "Offline")
            cpu_off(cpus[client])
            time.sleep(0.05)
            log_fds(index == 0)
        if list(Path("/dev").glob("ttyRPMSG*")):
            raise RuntimeError("RPMsg tty remains after both clients stopped")
        current_fds = log_fds(False)
        if current_fds != baseline_fds:
            raise RuntimeError(f"offline fd leak: baseline={baseline_fds}, now={current_fds}")

    for client in clients:
        line = echo.status_line(client)
        if "Offline" not in line or str(cpus[client]) not in line.split():
            raise RuntimeError(f"wrong initial client state/CPU: {line}")
        cpu_off(cpus[client])
    if list(Path("/dev").glob("ttyRPMSG*")):
        raise RuntimeError("unexpected active RPMsg tty before regression")
    baseline_fds = log_fds(False)
    print(f"BASELINE pid={baseline[0]} restarts={baseline[1]} fds={baseline_fds}", flush=True)
    started = time.monotonic()

    for stop_sequence in (clients, clients[::-1]):
        for cycle in range(1, args.cycles_per_order + 1):
            start_sequence = clients if cycle % 2 else clients[::-1]
            pairs = start_order(start_sequence)
            if cycle == 1:
                echo.run_concurrent(pairs, args.echo_count, 451)
                if args.isolation_cycles:
                    echo.run_isolation(pairs, args.isolation_cycles, 451)
                log_fds(True)
            else:
                echo.run_concurrent(pairs, 5, 451)
            stop_order(stop_sequence)
            print(
                f"PAIR PASS stop={','.join(stop_sequence)} "
                f"start={','.join(start_sequence)} cycle={cycle}/{args.cycles_per_order} "
                f"pid={baseline[0]} fds={baseline_fds}", flush=True,
            )
    print(
        f"OVERALL PASS pairs={2 * args.cycles_per_order} "
        f"pid={baseline[0]} restarts={baseline[1]} fds={baseline_fds} "
        f"elapsed={time.monotonic() - started:.3f}s", flush=True,
    )


if __name__ == "__main__":
    main()
