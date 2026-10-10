#!/usr/bin/env python3
"""Explicit temporary CPU5 timer-only test. No peripheral handoff or frames.
Unsafe/unknown timer cleanup retains the client, never forces CPU_OFF/reboot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import termios
import time
import tty
import run_can_direct_pair as common
import integrated_mmu_resources as mmu

ROOT = Path('/root/m7-powerlink-timer-p3c-20261010')
CLIENT = 'up-b-m7-plk-timer'
ALLOWED = ('M7 status', 'PLK status', 'PLK timer-status', 'PLK timer-probe')


def diagnostic(fd, text):
    if text not in ALLOWED: raise ValueError('timer runner command denied')
    data = (text + '\n').encode('ascii')
    if os.write(fd, data) != len(data): raise RuntimeError('short diagnostic write')
    received = bytearray()
    end = time.monotonic() + 5
    while time.monotonic() < end:
        if select.select([fd], [], [], .1)[0]:
            try: received.extend(os.read(fd, 4096))
            except BlockingIOError: continue
            if b'\n' in received: return received.decode('ascii').strip()
    raise RuntimeError(f'diagnostic timeout: {bytes(received)!r}')


def fields(reply):
    return dict(re.findall(r'(\w+)=([^ ]+)', reply))


def resources():
    drivers = {}
    for path in Path('/sys/bus/platform/devices').iterdir():
        if path.name.endswith(('.can', '.serial', '.uart', '.ethernet')):
            drivers[path.name] = (path / 'driver').resolve().name if (path / 'driver').exists() else None
    return dict(drivers=drivers, routes=common.command('ip', 'route'),
                addresses=common.command('ip', '-brief', 'address'),
                linux_cpus=Path('/sys/devices/system/cpu/online').read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-timer-only', action='store_true')
    p.add_argument('--sha256', required=True)
    p.add_argument('--cycles', type=int, choices=range(1, 11), default=3)
    a = p.parse_args()
    if not a.confirm_timer_only: raise RuntimeError('explicit timer-only approval required')
    if os.geteuid() != 0: raise RuntimeError('requires board root')
    image = ROOT / 'tl3572-m7-powerlink-p3c-up-b.elf'
    config = ROOT / f'{CLIENT}.conf'
    if hashlib.sha256(image.read_bytes()).hexdigest() != a.sha256: raise RuntimeError('candidate hash mismatch')
    expected = ['[Mica]', f'Name={CLIENT}', 'CPU=5', f'ClientPath={image}', 'AutoBoot=no']
    if config.read_text().splitlines() != expected: raise RuntimeError('temporary config mismatch')
    status = common.command('mcsctl', 'status')
    if status.count('Offline') != 2 or 'up-a' not in status or 'up-b' not in status:
        raise RuntimeError('requires exactly two original Offline instances')
    if list(Path('/dev').glob('ttyRPMSG*')): raise RuntimeError('existing RPMsg endpoint')
    if int(Path('/proc/sys/kernel/tainted').read_text()) & 128: raise RuntimeError('kernel Oops taint present')
    common.confirm_up_cpus_off()
    before, daemon = resources(), common.micad_state()
    if daemon.get('ActiveState') != 'active': raise RuntimeError('micad inactive')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    reader = common.load_log_reader()
    baseline_seq = common.log_header(reader, 'up-b')[1]
    created, started, safe, fd, error = False, False, True, None, None
    results = []
    print('SCOPE: temporary UP2 ONLY; UP1 offline; no PHY/ETH/CAN/UART frames, unbind, DT, boot config or reboot', flush=True)
    print('BEFORE ' + json.dumps(dict(resources=before, micad=daemon, boot=boot.strip()), sort_keys=True), flush=True)
    try:
        common.control('create', str(config)); created = True
        common.control('start', CLIENT); started = True
        end = time.monotonic() + 15
        while time.monotonic() < end:
            endpoints = list(Path('/dev').glob('ttyRPMSG*'))
            if len(endpoints) == 1: break
            time.sleep(.1)
        else: raise RuntimeError('no unique RPMsg endpoint')
        fd = os.open(endpoints[0], os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY)
        tty.setraw(fd); termios.tcflush(fd, termios.TCIOFLUSH)
        print('REAL MMU ' + json.dumps(mmu.verify_running(image), sort_keys=True), flush=True)
        initial = diagnostic(fd, 'PLK status'); print(initial, flush=True)
        state = fields(initial)
        if not all(state.get(k) == v for k, v in dict(ready='1', pending='0', running='0', seq='0', done='0', state='0').items()):
            raise RuntimeError('not dormant COLD')
        for cycle in range(1, a.cycles + 1):
            safe = False
            accepted = diagnostic(fd, 'PLK timer-probe'); print(accepted, flush=True)
            if accepted != f'PLK UP2 ACCEPTED seq={cycle}': raise RuntimeError('probe not accepted')
            end = time.monotonic() + 5
            while time.monotonic() < end:
                status = diagnostic(fd, 'PLK status')
                state = fields(status)
                if state.get('done') == str(cycle) and state.get('running') == '0': break
                time.sleep(.05)
            else: raise RuntimeError('timer owner timeout')
            reply = diagnostic(fd, 'PLK timer-status'); print(reply, flush=True)
            result = fields(reply); safe = result.get('clean') == '1'
            results.append(result)
            if not safe: raise RuntimeError('timer cleanup unproved, retain owner')
            if not all(result.get(k) == v for k, v in dict(rc='0', samples='24', irqs='24', callbacks='24', el='4', ppi30='0x0/0x0/0x0').items()) or int(result['affinity'], 16) & 0xffffff != 0x101:
                raise RuntimeError('timer hardware diagnostic failed')
            if int(result['ticks']) <= 0 or int(result['hz']) <= 0: raise RuntimeError('system tick/frequency invalid')
            if state.get('state') != '0' or state.get('ready') != '1': raise RuntimeError('MN left COLD/not-ready')
            if resources() != before: raise RuntimeError('Linux resource drift')
            print(f'TIMER CYCLE {cycle} PASS', flush=True)
        passive = diagnostic(fd, 'M7 status'); print(passive, flush=True)
        if 'done=0/0/0 eth_rc=0 eth_done=0' not in passive: raise RuntimeError('peripheral worker executed')
    except Exception as exc: error = exc
    finally:
        if fd is not None: os.close(fd)
        for seq, generation, message in common.new_log_messages(reader, 'up-b', baseline_seq):
            print(f'[up-b boot={generation} seq={seq}] {message}', end='' if message.endswith('\n') else '\n', flush=True)
        if not safe:
            print('UNSAFE/UNKNOWN: retained temporary UP2; no stop/rm/reboot or automatic retry', flush=True)
            raise RuntimeError(str(error))
        if started: common.control('stop', CLIENT)
        if created: common.control('rm', CLIENT)
        common.confirm_up_cpus_off()
        if resources() != before or common.micad_state() != daemon or Path('/proc/sys/kernel/random/boot_id').read_text() != boot:
            raise RuntimeError('final Linux/daemon/boot drift')
        if list(Path('/dev').glob('ttyRPMSG*')): raise RuntimeError('endpoint cleanup failed')
        if common.command('mcsctl', 'status').count('Offline') != 2: raise RuntimeError('original client states changed')
        print('CLEANUP PASS: temporary client removed, original 2 Offline, CPU4/5 OFF, Linux bindings/routes/micad/boot unchanged', flush=True)
    if error: raise error
    report = dict(phase='P3c TIMER hardware only', passed=True, cycles=results, candidate_sha256=a.sha256,
                  micad=daemon, boot_id=boot.strip(), cleanup=True, powerlink_frames=0,
                  limit='Idle-board sample maximum only; NOT worst-case realtime acceptance/POWERLINK MN/CN test')
    (ROOT / 'board-result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('OVERALL PASS P3c real CNTP/PPI30 access+IRQ+task callbacks; no MN/ETH acceptance', flush=True)


if __name__ == '__main__': main()
