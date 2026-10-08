#!/usr/bin/env python3
"""Run and clean up the UP1/CAN1 <-> UP2/CAN3 direct-register test."""

import importlib.util
import fcntl
import mmap
import os
from pathlib import Path
import struct
import subprocess
import time


TEST_ROOT = Path("/root/m7-can-20260928")
LOG_READER = Path("/usr/libexec/m7/up_log_reader.py")
DRIVER = Path("/sys/bus/platform/drivers/rk3576_can")
DEVICES = ("2ab10000.can", "2ab30000.can")
CLIENTS = ("up-b-m7-can", "up-a-m7-can")
CONFIGS = {
    "up-a-m7-can": TEST_ROOT / "up-a-m7-can.conf",
    "up-b-m7-can": TEST_ROOT / "up-b-m7-can.conf",
}


def command(*args, check=True):
    result = subprocess.run(args, check=False, text=True, timeout=30,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}")
    return result.stdout


def control(action, client):
    output = command("mcsctl", action, client)
    if "success" not in output.lower():
        raise RuntimeError(f"mcsctl {action} {client}: {output.strip()}")
    return output


def load_log_reader():
    spec = importlib.util.spec_from_file_location("up_log_reader", LOG_READER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def log_header(reader, client):
    cpu, base = reader.CLIENTS[client]
    descriptor = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(descriptor, reader.REGION_SIZE, flags=mmap.MAP_SHARED,
                       prot=mmap.PROT_READ, offset=base) as region:
            header = reader.read_header(region, cpu)
            return (0, 0, 0) if header is None else header
    finally:
        os.close(descriptor)


def new_log_messages(reader, client, baseline_seq):
    cpu, base = reader.CLIENTS[client]
    descriptor = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(descriptor, reader.REGION_SIZE, flags=mmap.MAP_SHARED,
                       prot=mmap.PROT_READ, offset=base) as region:
            header = reader.read_header(region, cpu)
            if header is None:
                return []
            _, current_seq, _ = header
            return reader.read_new_records(region, baseline_seq, current_seq)[1]
    finally:
        os.close(descriptor)


def micad_state():
    fields = command("systemctl", "show", "micad", "-p", "ActiveState",
                     "-p", "MainPID", "-p", "NRestarts")
    return dict(line.split("=", 1) for line in fields.splitlines())


def prepare_linux_controllers():
    mappings = {
        "can1": "2ab10000.can",
        "can3": "2ab30000.can",
    }
    for interface, device in mappings.items():
        device_path = Path(f"/sys/class/net/{interface}/device").resolve().name
        if device_path != device:
            raise RuntimeError(f"{interface}: expected {device}, found {device_path}")
        command("ip", "link", "set", interface, "down")
        command("ip", "link", "set", interface, "type", "can",
                "bitrate", "1000000", "restart-ms", "100")
        command("ip", "link", "set", interface, "up")
        command("ip", "link", "set", interface, "down")


def unbind_controllers():
    for device in DEVICES:
        (DRIVER / "unbind").write_text(device)
        if (Path("/sys/bus/platform/devices") / device / "driver").exists():
            raise RuntimeError(f"Linux driver remains bound to {device}")
        print(f"UNBOUND {device}", flush=True)


def restore_controllers():
    errors = []
    for device in DEVICES:
        device_path = Path("/sys/bus/platform/devices") / device
        if not (device_path / "driver").exists():
            try:
                (DRIVER / "bind").write_text(device)
            except Exception as error:  # Continue restoring the other controller.
                errors.append(f"{device}: {error}")
    time.sleep(0.5)
    for device in DEVICES:
        net_dir = Path("/sys/bus/platform/devices") / device / "net"
        if not (Path("/sys/bus/platform/devices") / device / "driver").exists():
            errors.append(f"{device}: driver not rebound")
            continue
        if net_dir.exists():
            for interface in net_dir.iterdir():
                command("ip", "link", "set", interface.name, "down", check=False)
        print(f"REBOUND {device}", flush=True)
    if errors:
        raise RuntimeError("; ".join(errors))


def cleanup_clients():
    status = command("mcsctl", "status", check=False)
    for client in CLIENTS:
        if client in status:
            command("mcsctl", "stop", client, check=False)
    time.sleep(0.2)
    status = command("mcsctl", "status", check=False)
    for client in CLIENTS:
        if client in status:
            command("mcsctl", "rm", client, check=False)

    status = command("mcsctl", "status")
    remaining = [client for client in CLIENTS if client in status]
    if remaining:
        raise RuntimeError(f"temporary clients remain: {remaining}")


def confirm_up_cpus_off():
    descriptor = os.open("/dev/mcs", os.O_RDONLY)
    try:
        for cpu in (4, 5):
            # MCS cpu_info and _IOW('A', 2, int), as in query_cpu_off.py.
            fcntl.ioctl(descriptor, 0x40044102, struct.pack("<I4xQ", cpu, 0))
            print(f"CPU{cpu} PSCI OFF confirmed", flush=True)
    finally:
        os.close(descriptor)


def main():
    if os.geteuid() != 0:
        raise SystemExit("run as root")
    reader = load_log_reader()
    baseline_daemon = micad_state()
    if baseline_daemon.get("ActiveState") != "active":
        raise RuntimeError(f"micad is not active: {baseline_daemon}")
    status = command("mcsctl", "status")
    if "up-a" not in status or "up-b" not in status or status.count("Offline") != 2:
        raise RuntimeError(f"unexpected baseline clients:\n{status}")
    for path in (*CONFIGS.values(),
                 TEST_ROOT / "tl3572-m7-can-up-a.elf",
                 TEST_ROOT / "tl3572-m7-can-up-b.elf"):
        if not path.is_file():
            raise RuntimeError(f"missing test input: {path}")

    baseline_seq = {
        "up-a": log_header(reader, "up-a")[1],
        "up-b": log_header(reader, "up-b")[1],
    }
    print(f"BASELINE micad={baseline_daemon} seq={baseline_seq}", flush=True)
    prepare_linux_controllers()
    controllers_unbound = False
    primary_error = None
    try:
        controllers_unbound = True
        unbind_controllers()
        for client in CLIENTS:
            output = command("mcsctl", "create", str(CONFIGS[client]))
            if "success" not in output.lower():
                raise RuntimeError(f"create {client}: {output.strip()}")
        control("start", "up-b-m7-can")
        time.sleep(1.0)
        control("start", "up-a-m7-can")

        deadline = time.monotonic() + 35.0
        final_messages = {}
        while time.monotonic() < deadline:
            final_messages = {
                "up-a": new_log_messages(reader, "up-a", baseline_seq["up-a"]),
                "up-b": new_log_messages(reader, "up-b", baseline_seq["up-b"]),
            }
            text_a = "".join(message for _, _, message in final_messages["up-a"])
            text_b = "".join(message for _, _, message in final_messages["up-b"])
            if "[can] UP1 direct FAIL" in text_a or "[can] UP2 direct FAIL" in text_b:
                raise RuntimeError(f"direct CAN test failed\nUP1:\n{text_a}\nUP2:\n{text_b}")
            if ("[can] UP1 direct PASS tx=1000 rx=1000" in text_a and
                    "[can] UP2 direct PASS tx=1000 rx=1000" in text_b):
                for client in ("up-a", "up-b"):
                    for seq, boot, message in final_messages[client]:
                        print(f"[{client} boot={boot} seq={seq}] {message}",
                              end="" if message.endswith("\n") else "\n")
                print("OVERALL PASS direct CAN requests=1000 responses=1000", flush=True)
                break
            time.sleep(0.2)
        else:
            raise RuntimeError(f"timeout waiting for direct CAN PASS: {final_messages}")
    except Exception as error:
        primary_error = error
    finally:
        cleanup_errors = []
        try:
            cleanup_clients()
        except Exception as error:
            cleanup_errors.append(f"client cleanup: {error}")
        cpus_off = False
        try:
            confirm_up_cpus_off()
            cpus_off = True
        except Exception as error:
            cleanup_errors.append(f"CPU OFF not confirmed: {error}")
        if controllers_unbound and cpus_off:
            try:
                restore_controllers()
            except Exception as error:
                cleanup_errors.append(f"controller restore: {error}")
        current_daemon = micad_state()
        if current_daemon != baseline_daemon:
            cleanup_errors.append(f"micad changed: {baseline_daemon} -> {current_daemon}")
        if cleanup_errors:
            detail = "; ".join(cleanup_errors)
            primary_error = RuntimeError(f"{primary_error or 'test passed'}; cleanup: {detail}")

    if primary_error is not None:
        raise primary_error
    print("CLEANUP PASS temporary clients removed; Linux CAN rebound; micad unchanged", flush=True)


if __name__ == "__main__":
    main()
