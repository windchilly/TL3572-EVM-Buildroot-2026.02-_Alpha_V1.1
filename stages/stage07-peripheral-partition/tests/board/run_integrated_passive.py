#!/usr/bin/env python3
"""Board-only integrated passive boot/diagnostic regression. Never run peripheral tests."""
import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import select
import time

import can_resource_preflight as can
import rs232_resources as rs232
import rs485_resources as rs485
import run_can_direct_pair as common

ROOT = Path('/root/m7-integrated-20261009')
CLIENTS = ('up-a-m7-integrated', 'up-b-m7-integrated')
HASHES = ('d22bdf200c326e2727d4c9ff9f19e4aa46c38727b3b7b7dedc7f33503fbf1581',
          '1a4ece0cff536cfe5f796b1aecc843fc04b7ffb3ad5243ca094dba99b84fa622')
SAFE_COMMANDS = ('M7 status', 'M7 unsupported')


def passive_command(fd, text):
    if text not in SAFE_COMMANDS:
        raise ValueError('passive runner forbids all run/config/peripheral commands')
    payload = (text + '\n').encode('ascii')
    if os.write(fd, payload) != len(payload):
        raise RuntimeError('short RPMsg diagnostic write')
    received = bytearray()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if ready:
            try:
                received.extend(os.read(fd, 4096))
            except BlockingIOError:
                continue
            if b'\n' in received:
                return received.decode('ascii').strip()
    raise RuntimeError(f'diagnostic timeout: {bytes(received)!r}')


def validate_status(reply, up):
    expected = f'M7 UP{up} ready=1 pending=0x0 running=0x0 rc=0/0/0 done=0/0/0'
    if reply != expected:
        raise RuntimeError(f'not idle/ready or peripheral work executed: {reply!r}')


def validate_boot(text, up):
    for marker in (f'[boot] UP CPU{up + 3} entered', '[boot] interrupt routing ready',
                   '[boot] scheduler task entered', '[boot] RPMsg ready',
                   f'[integrated] UP{up} ready modules=can-classic,can-fd,rs232,rs485 mode=passive'):
        if marker not in text:
            raise RuntimeError(f'missing startup marker: {marker}')
    if re.search(r'\[(?:can|can-irq|can-fd|rs232|rs485)\]|\[integrated\].*\bbegin\b', text):
        raise RuntimeError('peripheral driver entered during passive test')


def snapshot():
    values = can.read_registers() | rs232.read_registers() | rs485.read_registers()
    profiles = [p['device'] for p in can.RESOURCES.values()]
    profiles += [p['device'] for p in rs232.RESOURCES.values()]
    profiles += [p['device'] for p in rs485.RESOURCES.values()]
    drivers = {}
    for device in profiles:
        path = Path('/sys/bus/platform/devices') / device / 'driver'
        if not path.exists():
            raise RuntimeError(f'Linux owner missing: {device}')
        drivers[device] = path.resolve().name
    return dict(registers={f'0x{a:08x}': v for a, v in sorted(values.items())}, drivers=drivers)


def compare_snapshot(before, after):
    if before != after:
        changes = {group: {key: [value, after[group].get(key)]
                          for key, value in entries.items() if after[group].get(key) != value}
                   for group, entries in before.items()}
        raise RuntimeError(f'passive peripheral resource drift: {changes}')


def handles(pid):
    result = []
    for path in Path(f'/proc/{pid}/fd').iterdir():
        try:
            result.append(os.readlink(path))
        except FileNotFoundError:
            continue
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycles-per-order', type=int, choices=range(1, 11), default=2)
    parser.add_argument('--echo-count', type=int, choices=range(1, 1001), default=100)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('requires board root')
    spec = importlib.util.spec_from_file_location('m6_echo', ROOT / 'dual-runtime-regression.py')
    echo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(echo)
    baseline = common.micad_state()
    if baseline.get('ActiveState') != 'active':
        raise RuntimeError(f'micad inactive: {baseline}')
    state = common.command('mcsctl', 'status')
    if state.count('Offline') != 2 or any(echo.status_line(c).split()[0:2] != [c, str(cpu)]
                                          for c, cpu in (('up-a', 4), ('up-b', 5))):
        raise RuntimeError(f'unexpected initial clients: {state}')
    if list(Path('/dev').glob('ttyRPMSG*')):
        raise RuntimeError('unexpected active RPMsg endpoint')
    common.confirm_up_cpus_off()
    for index, client in enumerate(CLIENTS):
        config = (ROOT / f'{client}.conf').read_text().splitlines()
        image = ROOT / f'tl3572-m7-integrated-up-{chr(97 + index)}.elf'
        required = {'[Mica]', 'AutoBoot=no', f'CPU={index + 4}', f'Name={client}', f'ClientPath={image}'}
        if not required.issubset(config) or hashlib.sha256(image.read_bytes()).hexdigest() != HASHES[index]:
            raise RuntimeError(f'config/firmware does not match reviewed passive image: {client}')
    for p in list(rs232.RESOURCES.values()) + list(rs485.RESOURCES.values()):
        result = common.command('fuser', '-v', f"/dev/{p['tty']}", check=False)
        if result.strip():
            raise RuntimeError(f"UART occupied: {p['tty']}: {result}")
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text()
    before = snapshot()
    reader = common.load_log_reader()
    initial_handles = handles(int(baseline['MainPID']))
    created = []
    log_seq = {c: common.log_header(reader, c)[1] for c in ('up-a', 'up-b')}
    primary = None
    print('NO industrial sends, controller unbind, FIFO access, CRU/IOC/GIC writes, DT change or reboot', flush=True)
    print(f'BASELINE micad={baseline} fds={len(initial_handles)} boot_id={boot_id.strip()}', flush=True)
    print('PERIPHERAL SNAPSHOT BEFORE ' + json.dumps(before, sort_keys=True), flush=True)
    try:
        for client in CLIENTS:
            common.control('create', str(ROOT / f'{client}.conf'))
            created.append(client)
        offline_handles = handles(int(baseline['MainPID']))
        for stop_order in (CLIENTS, CLIENTS[::-1]):
            for cycle in range(args.cycles_per_order):
                order = CLIENTS if cycle % 2 == 0 else CLIENTS[::-1]
                pairs = []
                for client in order:
                    known = set(Path('/dev').glob('ttyRPMSG*'))
                    common.control('start', client)
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        added = set(Path('/dev').glob('ttyRPMSG*')) - known
                        if len(added) == 1:
                            path = str(added.pop())
                            echo.wait_state(client, 'Running', path)
                            break
                        time.sleep(0.1)
                    else:
                        raise RuntimeError(f'no unique RPMsg TTY: {client}')
                    pairs.append((client, path))
                time.sleep(0.3)
                for client, path in pairs:
                    up = CLIENTS.index(client) + 1
                    entries = common.new_log_messages(reader, f'up-{chr(96 + up)}', log_seq[f'up-{chr(96 + up)}'])
                    validate_boot(''.join(message for _, _, message in entries), up)
                    fd = echo.open_tty(path)
                    try:
                        reply = passive_command(fd, 'M7 status')
                        validate_status(reply, up)
                        print(f'{client} STATUS PASS {reply}', flush=True)
                        invalid = passive_command(fd, 'M7 unsupported')
                        if invalid != f'M7 UP{up} ERROR invalid-command':
                            raise RuntimeError(f'wrong invalid-command response: {invalid}')
                        validate_status(passive_command(fd, 'M7 status'), up)
                    finally:
                        os.close(fd)
                echo.run_concurrent(pairs, args.echo_count, 451)
                compare_snapshot(before, snapshot())
                for index, client in enumerate(stop_order):
                    common.control('stop', client)
                    echo.wait_state(client, 'Offline')
                    if index == 0:
                        survivor = next(p for p in pairs if p[0] != client)
                        fd = echo.open_tty(survivor[1])
                        try:
                            validate_status(passive_command(fd, 'M7 status'), CLIENTS.index(survivor[0]) + 1)
                        finally:
                            os.close(fd)
                common.confirm_up_cpus_off()
                if handles(int(baseline['MainPID'])) != offline_handles:
                    # Compare counts and shared RPC logs, not /proc enumeration order.
                    if sorted(handles(int(baseline['MainPID']))) != sorted(offline_handles):
                        raise RuntimeError('per-cycle offline file-handle drift')
                if common.micad_state() != baseline:
                    raise RuntimeError('micad PID/restarts/state changed')
                if list(Path('/dev').glob('ttyRPMSG*')):
                    raise RuntimeError('RPMsg endpoints remain after both stopped')
                for name in log_seq:
                    entries = common.new_log_messages(reader, name, log_seq[name])
                    validate_boot(''.join(message for _, _, message in entries), 1 if name == 'up-a' else 2)
                    for serial, boot, message in entries:
                        print(f'[{name} boot={boot} seq={serial}] {message}', end='' if message.endswith('\n') else '\n', flush=True)
                    log_seq[name] = common.log_header(reader, name)[1]
                compare_snapshot(before, snapshot())
                print(f'PASSIVE PAIR PASS stop={stop_order} start={order} cycle={cycle + 1}', flush=True)
    except Exception as error:
        primary = error
    finally:
        errors = []
        common.CLIENTS = tuple(created)
        common.STOP_CLIENTS = tuple(created)
        try:
            common.cleanup_clients()
            common.confirm_up_cpus_off()
        except Exception as error:
            errors.append(f'lifecycle cleanup: {error}')
        try:
            after = snapshot()
            print('PERIPHERAL SNAPSHOT AFTER ' + json.dumps(after, sort_keys=True), flush=True)
            compare_snapshot(before, after)
            if common.micad_state() != baseline or Path('/proc/sys/kernel/random/boot_id').read_text() != boot_id:
                raise RuntimeError('daemon changed or board rebooted')
            if list(Path('/dev').glob('ttyRPMSG*')):
                raise RuntimeError('RPMsg endpoint cleanup failed')
            print(f'FINAL mcs={common.command("mcsctl", "status")}micad={common.micad_state()}', flush=True)
            print(f'FINAL fds={len(handles(int(baseline["MainPID"])))}; create/rm MCS fd leak is a known separate issue', flush=True)
        except Exception as error:
            errors.append(f'passive final state: {error}')
        if errors:
            primary = RuntimeError(f'{primary or "data checks passed"}; {errors}')
        if primary:
            for name in log_seq:
                for serial, boot, message in common.new_log_messages(reader, name, log_seq[name]):
                    print(f'[{name} boot={boot} seq={serial}] {message}', end='' if message.endswith('\n') else '\n', flush=True)
    if primary:
        raise primary
    print(f'OVERALL PASS integrated passive pairs={2 * args.cycles_per_order}; peripheral jobs=0', flush=True)
    print('CLEANUP PASS original clients Offline, CPUs OFF, Linux bindings/resources unchanged, micad unchanged', flush=True)


if __name__ == '__main__':
    main()
