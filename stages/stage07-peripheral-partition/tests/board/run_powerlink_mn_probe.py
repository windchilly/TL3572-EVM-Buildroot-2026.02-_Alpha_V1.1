#!/usr/bin/env python3
"""Separate approval required: one full-stack GsOff lifecycle, no reset/start/TX.
Prepare DOES acquire ETH2 MAC/DMA/PHY and CNTP/PPI30. Unknown retains hold+UP2.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import termios
import time
import tty
import run_powerlink_eth_probe as base
from powerlink_eth_checks import fields
from powerlink_mn_checks import validate_lifecycle, passive_owner
common, passive, mmu, fabric, ethernet = base.common, base.passive, base.mmu, base.fabric, base.ethernet
ROOT = Path('/root/m7-powerlink-mn-p3f-20261023')
CLIENT = 'up-b-m7-plk-mn-probe'
ALLOWED = ('M7 status', 'PLK status', 'PLK mn-probe', 'PLK mn-status')

def diagnostic(fd, text):
    if text not in ALLOWED: raise ValueError('GsOff runner command denied')
    data = (text + '\n').encode('ascii')
    if os.write(fd, data) != len(data): raise RuntimeError('short RPMsg write')
    received = bytearray(); end = time.monotonic() + 5
    while time.monotonic() < end:
        if select.select([fd], [], [], .1)[0]:
            try: received.extend(os.read(fd, 4096))
            except BlockingIOError: continue
            if b'\n' in received: return received.decode('ascii').strip()
    raise RuntimeError('RPMsg diagnostic timeout')

def finished(fd):
    end = time.monotonic() + 20
    while time.monotonic() < end:
        try:
            state = fields(diagnostic(fd, 'PLK status'), 'PLK UP2')
            if state.get('done') == '1' and state.get('pending') == '0' and state.get('running') == '0':
                reply = diagnostic(fd, 'PLK mn-status'); print(reply, flush=True)
                return state, validate_lifecycle(reply)
        except (OSError, RuntimeError, ValueError) as exc: print('OBSERVE ' + str(exc), flush=True)
        time.sleep(.1)
    raise RuntimeError('lifecycle/cleanup unproved; retain owner+hold')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-isolated-gsoff-lifecycle', action='store_true'); p.add_argument('--sha256', required=True)
    a = p.parse_args()
    if not a.confirm_isolated_gsoff_lifecycle or os.geteuid() != 0: raise RuntimeError('separate explicit approval and root required')
    image = ROOT / 'tl3572-m7-powerlink-p3f-up-b.elf'; config = ROOT / (CLIENT + '.conf')
    if hashlib.sha256(image.read_bytes()).hexdigest() != a.sha256: raise RuntimeError('candidate SHA mismatch')
    if hashlib.sha256(base.MODULE.read_bytes()).hexdigest() != base.MODULE_HASH: raise RuntimeError('hold SHA mismatch')
    if config.read_text().splitlines() != ['[Mica]', f'Name={CLIENT}', 'CPU=5', f'ClientPath={image}', 'AutoBoot=no']:
        raise RuntimeError('temporary config mismatch')
    status = common.command('mcsctl', 'status')
    if status.count('Offline') != 2 or any(name not in status for name in ('up-a', 'up-b')): raise RuntimeError('original clients not Offline')
    if list(Path('/dev').glob('ttyRPMSG*')) or Path('/sys/module/m7_eth2_power_hold').exists(): raise RuntimeError('concurrent owner/hold')
    if int(Path('/proc/sys/kernel/tainted').read_text()) & 128: raise RuntimeError('kernel Oops taint')
    left, right = ethernet.preflight()
    if common.command('ip', '-4', '-o', 'addr', 'show', 'dev', left.name).strip() or common.command('ip', 'route', 'show', 'dev', left.name).strip():
        raise RuntimeError('ETH2 carries IP/routes')
    common.confirm_up_cpus_off()
    before, daemon, mgmt = passive.snapshot(), common.micad_state(), base.management()
    if daemon.get('ActiveState') != 'active': raise RuntimeError('micad inactive')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    reader = common.load_log_reader(); baseline = common.log_header(reader, 'up-b')[1]
    held = detached = down = created = start_attempted = submitted = False
    safe, fd, error, result = True, None, None, None
    idle = 'M7 UP2 ready=1 pending=0x0 running=0x0 rc=0/0/0 done=0/0/0 eth_rc=0 eth_done=0'
    print('SCOPE: one 128-process full-stack GsOff lifecycle; no reset/start/frame/CAN/UART/boot change/reboot', flush=True)
    print('BEFORE ' + json.dumps(dict(micad=daemon, management=mgmt, boot=boot.strip(), peripherals=before), sort_keys=True), flush=True)
    try:
        common.command('insmod', str(base.MODULE)); held = True
        down = True; common.command('ip', 'link', 'set', left.name, 'down')
        detached = True; (base.DRIVER / 'unbind').write_text(base.DEVICE.name)
        power = Path('/sys/kernel/debug/pm_genpd/pm_genpd_summary').read_text()
        if (base.DEVICE / 'driver').exists() or 'm7-eth2-power-hold' not in power or not any(
                line.startswith('nvm0 ') and ' on ' in line for line in power.splitlines()): raise RuntimeError('powered handoff failed')
        print('POWER/ROOT HOLD PASS CRU42=' + hex(fabric.require_fabric_clocks()), flush=True)
        common.control('create', str(config)); created = True
        safe = False; start_attempted = True; common.control('start', CLIENT)
        end = time.monotonic() + 15
        while time.monotonic() < end:
            endpoints = list(Path('/dev').glob('ttyRPMSG*'))
            if len(endpoints) == 1: break
            time.sleep(.1)
        else: raise RuntimeError('no unique RPMsg endpoint')
        fd = os.open(endpoints[0], os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY)
        tty.setraw(fd); termios.tcflush(fd, termios.TCIOFLUSH)
        print('REAL MMU ' + json.dumps(mmu.verify_running(image), sort_keys=True), flush=True)
        state = fields(diagnostic(fd, 'PLK status'), 'PLK UP2')
        if not all(state.get(k) == v for k, v in dict(ready='1', pending='0', running='0', seq='0', done='0', state='0', processes='0', events='0').items()):
            raise RuntimeError('not dormant COLD')
        if diagnostic(fd, 'M7 status') != idle: raise RuntimeError('industrial worker active')
        safe = True
        safe = False; submitted = True
        reply = diagnostic(fd, 'PLK mn-probe'); print(reply, flush=True)
        if reply != 'PLK UP2 ACCEPTED seq=1': raise RuntimeError('lifecycle acceptance unproved')
        state, result = finished(fd); safe = True
        if not passive_owner(state):
            safe = False; raise RuntimeError('MN owner/cache drift')
        if diagnostic(fd, 'M7 status') != idle: safe = False; raise RuntimeError('industrial worker ran')
    except Exception as exc: error = exc
    finally:
        if submitted and not safe and fd is not None:
            # Observe ONLY; never resubmit, reset, switch off, or retry cleanup.
            try:
                state, result = finished(fd)
                safe = passive_owner(state) and diagnostic(fd, 'M7 status') == idle
            except Exception as exc: print('CLEANUP OBSERVATION FAILED ' + str(exc), flush=True)
        if fd is not None: os.close(fd)
        for seq, generation, message in common.new_log_messages(reader, 'up-b', baseline):
            print(f'[up-b boot={generation} seq={seq}] {message}', end='' if message.endswith('\n') else '\n', flush=True)
        if not safe:
            print('UNSAFE/UNKNOWN: retain UP2+hold; NO CPU_OFF/rebind/rmmod/reboot/retry', flush=True)
            raise RuntimeError(str(error))
        if start_attempted: common.control('stop', CLIENT)
        if created: common.control('rm', CLIENT)
        common.confirm_up_cpus_off()
        if detached and not (base.DEVICE / 'driver').exists(): (base.DRIVER / 'bind').write_text(base.DEVICE.name)
        if down: common.command('ip', 'link', 'set', left.name, 'up')
        if detached:
            end = time.monotonic() + 20
            while time.monotonic() < end:
                try: ethernet.preflight(); break
                except (RuntimeError, OSError): time.sleep(.2)
            else: raise RuntimeError('Linux100-full restore failed; retain hold')
        if held: common.command('rmmod', 'm7_eth2_power_hold')
        passive.compare_snapshot(before, passive.snapshot())
        if Path('/sys/module/m7_eth2_power_hold').exists() or base.management() != mgmt or common.micad_state() != daemon or Path('/proc/sys/kernel/random/boot_id').read_text() != boot:
            raise RuntimeError('hold/management/micad/boot drift')
        if list(Path('/dev').glob('ttyRPMSG*')) or common.command('mcsctl', 'status').count('Offline') != 2: raise RuntimeError('client cleanup incomplete')
        print('CLEANUP PASS: CPU4/5 OFF, Linux full restored, peripherals/management/micad/boot unchanged', flush=True)
    (ROOT / 'board-result.json').write_text(json.dumps(dict(phase='P3f GsOff lifecycle', passed=error is None,
        candidate_sha256=a.sha256, result=result, cleanup=True, boot_id=boot.strip(), micad=daemon,
        error=None if error is None else str(error)), indent=2) + '\n')
    if error: raise error
    print('OVERALL PASS full-stack GsOff lifecycle; NOT NMT reset/start/CN acceptance', flush=True)
if __name__ == '__main__': main()
