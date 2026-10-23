#!/usr/bin/env python3
"""Separately authorized ONE bounded NMT reset/NotActive/SwitchOff on UP2.
Not continuous MN, test Ethernet frames, CAN/UART, boot change or reboot.
Unknown state retains client+ETH handoff+hold. Never reuse P3f permission.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import time
from powerlink_eth_checks import fields, link_mode
from powerlink_nmt_checks import SHA, SNAPSHOT_BYTES, original_clients, validate_reply, validate_owner, match_replies
from read_powerlink_nmt_snapshot import read_stopped
ROOT = Path('/root/m7-powerlink-nmt-p3g-20261023')
CLIENT = 'up-b-m7-plk-nmt-probe'
ALLOWED = ('M7 status', 'PLK status', 'PLK nmt-probe', 'PLK nmt-status')
IDLE = 'M7 UP2 ready=1 pending=0x0 running=0x0 rc=0/0/0 done=0/0/0 eth_rc=0 eth_done=0'

def linux_full(base):
    ports = base.ethernet.preflight()
    expected = {'Speed': '100Mb/s', 'Duplex': 'Full', 'Auto-negotiation': 'on', 'Link detected': 'yes'}
    for port in ports:
        if link_mode(base.common.command('ethtool', port.name)) != expected:
            raise RuntimeError('Linux link/full/AN-on not restored: ' + port.name)
    return ports

def diagnostic(fd, text):
    if text not in ALLOWED: raise ValueError('bounded NMT runner command denied')
    data = (text + '\n').encode('ascii')
    if os.write(fd, data) != len(data): raise RuntimeError('short RPMsg write')
    received = bytearray(); end = time.monotonic() + 5
    while time.monotonic() < end:
        if select.select([fd], [], [], .1)[0]:
            try: received.extend(os.read(fd, 4096))
            except BlockingIOError: continue
            if len(received) > 4096: raise RuntimeError('oversized RPMsg diagnostic')
            if b'\n' in received:
                if received.count(b'\n') != 1 or not received.endswith(b'\n'): raise RuntimeError('ambiguous RPMsg lines')
                return received.decode('ascii').strip()
    raise RuntimeError('RPMsg diagnostic timeout')

def finished(fd):
    end = time.monotonic() + 20
    while time.monotonic() < end:
        try:
            state = fields(diagnostic(fd, 'PLK status'), 'PLK UP2')
            if state.get('done') == '1' and state.get('pending') == '0' and state.get('running') == '0':
                reply = diagnostic(fd, 'PLK nmt-status'); print(reply, flush=True)
                result = validate_reply(reply); validate_owner(state, result)
                if diagnostic(fd, 'M7 status') != IDLE: raise ValueError('industrial worker ran')
                return dict(owner=state, result=result)
        except (OSError, RuntimeError, ValueError) as exc: print('OBSERVE ' + str(exc), flush=True)
        time.sleep(.1)
    raise RuntimeError('NMT completion/cleanup unproved; retain UP2+hold')

def stop_completed(common, image, evidence):
    # A bad/absent completion proof must not issue even the first CPU_OFF.
    if not evidence: raise RuntimeError('no successful completion proof; NO CPU_OFF')
    result = evidence['result']; validate_reply('PLK UP2 NMT ' + ' '.join(k + '=' + v for k, v in result.items()))
    validate_owner(evidence['owner'], result)
    common.control('stop', CLIENT)  # Once only, never retried on any later failure.
    common.confirm_up_cpus_off()
    report = read_stopped(image)
    match_replies(report, evidence['owner'], result)
    return report  # Caller may rm/rebind ONLY after this private proof succeeds.

def claim_attempt(root, boot):
    # Exclusive persistent marker: a second invocation cannot re-run this window.
    with (root / 'ATTEMPTED').open('x', encoding='ascii') as marker:
        marker.write('candidate=' + SHA + '\nboot=' + boot.strip() + '\n')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-isolated-bounded-nmt-reset', action='store_true'); p.add_argument('--sha256', required=True)
    a = p.parse_args()
    if not a.confirm_isolated_bounded_nmt_reset or getattr(os, 'geteuid', lambda: -1)() != 0:
        raise RuntimeError('NEW explicit isolated NMT reset/ETH2/CNTP approval and board root required')
    if a.sha256 != SHA: raise RuntimeError('only the pinned P3g candidate may run')
    import termios
    import tty
    import run_powerlink_eth_probe as base
    from verify_integrated_elf import symbols_and_data
    common, passive, mmu, fabric = base.common, base.passive, base.mmu, base.fabric
    image = ROOT / 'tl3572-m7-powerlink-p3g-up-b.elf'; config = ROOT / (CLIENT + '.conf')
    if (ROOT / 'ATTEMPTED').exists() or (ROOT / 'board-result.json').exists(): raise RuntimeError('one-shot window already attempted')
    if hashlib.sha256(image.read_bytes()).hexdigest() != SHA: raise RuntimeError('candidate SHA mismatch')
    symbols = symbols_and_data(image)
    if symbols['snapshot'][1] != SNAPSHOT_BYTES or 'm7_nmt_probe' not in symbols: raise RuntimeError('candidate NMT ABI mismatch')
    if hashlib.sha256(base.MODULE.read_bytes()).hexdigest() != base.MODULE_HASH: raise RuntimeError('hold SHA mismatch')
    if config.read_text().splitlines() != ['[Mica]', f'Name={CLIENT}', 'CPU=5', f'ClientPath={image}', 'AutoBoot=no']:
        raise RuntimeError('temporary config mismatch')
    if common.command('uname', '-r').strip() != '6.12.69-gf1b67c293213': raise RuntimeError('not pinned M6 kernel')
    original_clients(common.command('mcsctl', 'status'))
    if list(Path('/dev').glob('ttyRPMSG*')) or Path('/sys/module/m7_eth2_power_hold').exists(): raise RuntimeError('concurrent endpoint/hold')
    if int(Path('/proc/sys/kernel/tainted').read_text()) & 128: raise RuntimeError('kernel Oops taint')
    left, _ = linux_full(base)
    if common.command('ip', '-4', '-o', 'addr', 'show', 'dev', left.name).strip() or common.command('ip', 'route', 'show', 'dev', left.name).strip():
        raise RuntimeError('ETH2 carries IP/routes')
    common.confirm_up_cpus_off()
    before, daemon, mgmt = passive.snapshot(), common.micad_state(), base.management()
    if daemon.get('ActiveState') != 'active': raise RuntimeError('micad inactive')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    reader = common.load_log_reader(); baseline = common.log_header(reader, 'up-b')[1]
    claim_attempt(ROOT, boot)
    held = detached = down = created = start_attempted = submitted = False
    safe, fd, error, evidence, stopped, cleanup = True, None, None, None, None, False
    print('SCOPE: ONE reset -> NotActive -> SwitchOff; no continuous MN/CN/test frames/CAN/UART/boot change/reboot', flush=True)
    print('BEFORE ' + json.dumps(dict(micad=daemon, management=mgmt, boot=boot.strip(), peripherals=before), sort_keys=True), flush=True)
    try:
        safe = False; common.command('insmod', str(base.MODULE)); held = True; safe = True
        down = True; common.command('ip', 'link', 'set', left.name, 'down')
        detached = True; (base.DRIVER / 'unbind').write_text(base.DEVICE.name)
        power = Path('/sys/kernel/debug/pm_genpd/pm_genpd_summary').read_text()
        if (base.DEVICE / 'driver').exists() or 'm7-eth2-power-hold' not in power or not any(
                line.startswith('nvm0 ') and ' on ' in line for line in power.splitlines()): raise RuntimeError('powered handoff failed')
        print('POWER/ROOT HOLD PASS CRU42=' + hex(fabric.require_fabric_clocks()), flush=True)
        created = True; common.control('create', str(config))
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
        expected = dict(ready='1', pending='0', running='0', seq='0', done='0', cmd='0', rc='0x0', runtime='0x0',
            state='0', nmt='0x0', processes='0', events='0', mode='bounded-NMT-diagnostic')
        if any(state.get(k) != v for k, v in expected.items()) or diagnostic(fd, 'M7 status') != IDLE:
            raise RuntimeError('not dormant COLD/industrial idle')
        submitted = True  # Set BEFORE the only mutating RPMsg write, including short-write/timeout ambiguity.
        reply = diagnostic(fd, 'PLK nmt-probe'); print(reply, flush=True)
        if reply != 'PLK UP2 ACCEPTED seq=1': raise RuntimeError('NMT acceptance unproved')
        evidence = finished(fd); safe = True
    except BaseException as exc: error = type(exc).__name__ + ': ' + str(exc)
    finally:
        if submitted and not safe and fd is not None:
            # Observe ONLY. Never resubmit/reset/switch-off or retry stop/exit.
            try: evidence = finished(fd); safe = True
            except Exception as exc: print('COMPLETION OBSERVATION FAILED ' + str(exc), flush=True)
        if fd is not None:
            try: os.close(fd)
            except OSError as exc: error = (error + '; ' if error else '') + 'RPMsg close: ' + str(exc)
        try:
            for seq, generation, message in common.new_log_messages(reader, 'up-b', baseline):
                print(f'[up-b boot={generation} seq={seq}] {message}', end='' if message.endswith('\n') else '\n', flush=True)
        except Exception as exc: print('LOG READ ERROR ' + str(exc), flush=True)
        try:
            if not safe: raise RuntimeError('UNSAFE/UNKNOWN: retain UP2/client/ETH handoff/hold; NO CPU_OFF/rebind/rmmod/reboot/retry')
            if start_attempted:
                stopped = stop_completed(common, image, evidence)
                print('PRIVATE STOPPED PROOF ' + json.dumps(stopped, sort_keys=True), flush=True)
            else: common.confirm_up_cpus_off()
            if created: common.control('rm', CLIENT)
            if detached and not (base.DEVICE / 'driver').exists(): (base.DRIVER / 'bind').write_text(base.DEVICE.name)
            if down: common.command('ip', 'link', 'set', left.name, 'up')
            end = time.monotonic() + 20
            while time.monotonic() < end:
                try: linux_full(base); break
                except (RuntimeError, OSError): time.sleep(.2)
            else: raise RuntimeError('Linux100-full restore failed; retain hold')
            passive.compare_snapshot(before, passive.snapshot())
            if base.management() != mgmt or common.micad_state() != daemon or Path('/proc/sys/kernel/random/boot_id').read_text() != boot:
                raise RuntimeError('management/micad/boot drift; retain hold')
            original_clients(common.command('mcsctl', 'status'))
            if list(Path('/dev').glob('ttyRPMSG*')): raise RuntimeError('residual endpoint; retain hold')
            if held and Path('/sys/module/m7_eth2_power_hold').exists(): common.command('rmmod', 'm7_eth2_power_hold')
            if Path('/sys/module/m7_eth2_power_hold').exists(): raise RuntimeError('residual hold')
            common.confirm_up_cpus_off()
            passive.compare_snapshot(before, passive.snapshot())
            if (base.management() != mgmt or common.micad_state() != daemon or
                    Path('/proc/sys/kernel/random/boot_id').read_text() != boot or
                    int(Path('/proc/sys/kernel/tainted').read_text()) & 128): raise RuntimeError('post-release system drift/Oops')
            original_clients(common.command('mcsctl', 'status'))
            cleanup = True
            print('CLEANUP PASS CPU4/5 OFF, Linux full, original clients Offline, peripherals/management/micad/boot unchanged', flush=True)
        except Exception as exc:
            error = (error + '; ' if error else '') + str(exc)
            print('CLEANUP STOPPED: NO automatic second stop/rebind/rmmod/reboot/retry: ' + str(exc), flush=True)
        report = dict(phase='P3g bounded NMT hardware window', passed=error is None and cleanup, candidate_sha256=SHA,
            submitted=submitted, completion=evidence, private_stopped=stopped, cleanup=cleanup,
            boot_id=boot.strip(), micad=daemon, error=error)
        with (ROOT / 'board-result.json').open('x', encoding='utf-8') as out: json.dump(report, out, indent=2)
    if error or not cleanup: raise RuntimeError(error or 'cleanup incomplete')
    print('OVERALL PASS bounded reset/NotActive/SwitchOff; NOT continuous MN/CN/realtime acceptance', flush=True)

if __name__ == '__main__': main()
