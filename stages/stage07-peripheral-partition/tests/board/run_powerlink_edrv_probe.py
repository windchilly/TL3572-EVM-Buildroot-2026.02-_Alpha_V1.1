#!/usr/bin/env python3
"""Explicit P3e approval: ETH2<->ETH3 32x64B + 32x1514B request/reply ONLY.
Real EDRV, no MN/CAN/UART/boot change/reboot. Unknown stop retains UP2+hold.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import socket
import termios
import time
import tty
import run_powerlink_eth_probe as base
from powerlink_eth_checks import fields, quiescent, link_mode
from powerlink_edrv_checks import frame, accept_response, validate_result, OWN_MAC, TOTAL
common, passive, mmu, fabric, ethernet = base.common, base.passive, base.mmu, base.fabric, base.ethernet
ROOT = Path('/root/m7-powerlink-edrv-p3e-20261023')
CLIENT = 'up-b-m7-plk-edrv'
ALLOWED = ('M7 status', 'PLK status', 'PLK edrv-probe', 'PLK edrv-status')

def diagnostic(fd, text):
    if text not in ALLOWED: raise ValueError('bounded EDRV runner command denied')
    data = (text + '\n').encode('ascii')
    if os.write(fd, data) != len(data): raise RuntimeError('short RPMsg diagnostic write')
    received = bytearray(); end = time.monotonic() + 5
    while time.monotonic() < end:
        if select.select([fd], [], [], .1)[0]:
            try: received.extend(os.read(fd, 4096))
            except BlockingIOError: continue
            if b'\n' in received: return received.decode('ascii').strip()
    raise RuntimeError('RPMsg diagnostic timeout')

def ready_nonce(reader, baseline):
    end = time.monotonic() + 18
    while time.monotonic() < end:
        text = ''.join(msg for _, _, msg in common.new_log_messages(reader, 'up-b', baseline))
        match = re.search(r'\[plk-edrv-probe\] READY nonce=0x([0-9a-f]+) each=32 profiles=64/1514;', text)
        if match: return int(match[1], 16)
        if '[plk-edrv-probe] END' in text: raise RuntimeError('EDRV init failed before READY')
        time.sleep(.05)
    raise RuntimeError('EDRV READY timeout')

def wait_finished(fd):
    end = time.monotonic() + 26
    while time.monotonic() < end:
        try:
            state = fields(diagnostic(fd, 'PLK status'), 'PLK UP2')
            if state.get('done') == '1' and state.get('pending') == '0' and state.get('running') == '0':
                reply = diagnostic(fd, 'PLK edrv-status'); print(reply, flush=True)
                return state, fields(reply, 'PLK UP2 EDRV'), reply
        except (OSError, RuntimeError, ValueError) as exc:
            print('WAIT OWNER: ' + str(exc), flush=True)
        time.sleep(.1)
    raise RuntimeError('EDRV cleanup unproved; retain owner+hold')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-isolated-loop-frames', action='store_true'); p.add_argument('--sha256', required=True)
    a = p.parse_args()
    if not a.confirm_isolated_loop_frames or os.geteuid() != 0: raise RuntimeError('explicit frame approval and root required')
    image = ROOT / 'tl3572-m7-powerlink-p3e-up-b.elf'; config = ROOT / (CLIENT + '.conf')
    if hashlib.sha256(image.read_bytes()).hexdigest() != a.sha256: raise RuntimeError('candidate SHA mismatch')
    if hashlib.sha256(base.MODULE.read_bytes()).hexdigest() != base.MODULE_HASH: raise RuntimeError('shared hold SHA mismatch')
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
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    if daemon.get('ActiveState') != 'active': raise RuntimeError('micad inactive')
    reader = common.load_log_reader(); baseline = common.log_header(reader, 'up-b')[1]
    held = detached = down = created = start_attempted = submitted = False
    safe, fd, error, sent, received, result = True, None, None, 0, 0, None
    peer_mac = bytes.fromhex((right / 'address').read_text().strip().replace(':', ''))
    print('SCOPE: EDRV experimental frames only; 64 each direction, no MN/timer/CAN/UART/boot change/reboot', flush=True)
    print('BEFORE ' + json.dumps(dict(micad=daemon, management=mgmt, boot=boot.strip(), peripherals=before), sort_keys=True), flush=True)
    try:
        common.command('insmod', str(base.MODULE)); held = True
        down = True; common.command('ip', 'link', 'set', left.name, 'down')
        detached = True; (base.DRIVER / 'unbind').write_text(base.DEVICE.name)
        power = Path('/sys/kernel/debug/pm_genpd/pm_genpd_summary').read_text()
        if (base.DEVICE / 'driver').exists() or 'm7-eth2-power-hold' not in power or not any(
                line.startswith('nvm0 ') and ' on ' in line for line in power.splitlines()): raise RuntimeError('exclusive powered handoff failed')
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
        expected = 'M7 UP2 ready=1 pending=0x0 running=0x0 rc=0/0/0 done=0/0/0 eth_rc=0 eth_done=0'
        if diagnostic(fd, 'M7 status') != expected: raise RuntimeError('peripheral worker executed at startup')
        safe = True
        with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x88b5)) as peer:
            peer.bind((right.name, 0))
            safe = False; submitted = True
            reply = diagnostic(fd, 'PLK edrv-probe'); print(reply, flush=True)
            if reply != 'PLK UP2 ACCEPTED seq=1': raise RuntimeError('probe not accepted/unknown state')
            nonce = ready_nonce(reader, baseline); print(f'EDRV READY nonce=0x{nonce:x}', flush=True)
            peer_text = common.command('ethtool', right.name); print(peer_text, flush=True)
            mode = link_mode(peer_text)
            if mode['Speed'] != '100Mb/s' or mode['Duplex'] != 'Half' or mode['Link detected'] != 'yes':
                raise RuntimeError('peer100-half not confirmed: no test frame sent')
            for sequence in range(TOTAL):
                request = frame(OWN_MAC, peer_mac, nonce, sequence, 1)
                expected_frame = frame(peer_mac, OWN_MAC, nonce, sequence, 2)
                if peer.send(request) != len(request): raise RuntimeError('short ETH3 send')
                sent += 1; end = time.monotonic() + 2
                while time.monotonic() < end:
                    peer.settimeout(max(.01, end - time.monotonic()))
                    packet, address = peer.recvfrom(2048)
                    if accept_response(packet, address, expected_frame, nonce): break
                else: raise RuntimeError('physical response timeout')
                received += 1
                if sequence in (31, 63): print(f'PHYSICAL PROFILE PASS raw={len(request)} each=32 peer_tx={sent} peer_rx={received}', flush=True)
        state, result, reply = wait_finished(fd); safe = quiescent(result)
        validate_result(reply)
        if not all(state.get(k) == v for k, v in dict(ready='1', state='0', nmt='0x0', processes='0', events='0', cmd='5', rc='0x0', runtime='0x0').items()):
            safe = False; raise RuntimeError('MN/runtime changed')
        if diagnostic(fd, 'M7 status') != expected: safe = False; raise RuntimeError('industrial peripheral worker executed')
    except Exception as exc: error = exc
    finally:
        if submitted and not safe and fd is not None:
            # Observe the already-running bounded probe's cleanup, NEVER resubmit frames/commands.
            try:
                state, result, reply = wait_finished(fd); safe = quiescent(result)
                if state.get('state') != '0' or state.get('processes') != '0' or state.get('events') != '0': safe = False
            except Exception as exc: print('CLEANUP OBSERVATION FAILED ' + str(exc), flush=True)
        if fd is not None: os.close(fd)
        for seq, generation, message in common.new_log_messages(reader, 'up-b', baseline):
            print(f'[up-b boot={generation} seq={seq}] {message}', end='' if message.endswith('\n') else '\n', flush=True)
        if not safe:
            print('UNSAFE/UNKNOWN: retain UP2 and shared hold; NO CPU_OFF/rebind/rmmod/reboot/retry', flush=True)
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
            raise RuntimeError('final hold/management/micad/boot drift')
        if list(Path('/dev').glob('ttyRPMSG*')) or common.command('mcsctl', 'status').count('Offline') != 2: raise RuntimeError('client cleanup incomplete')
        print('CLEANUP PASS: CPU4/5 OFF, Linux full restored, hold/client/endpoints removed, CAN/UART/management/micad/boot unchanged', flush=True)
    report = dict(phase='P3e real EDRV bounded physical baseline', passed=error is None,
        candidate_sha256=a.sha256, peer_tx=sent, peer_rx=received, up2=result, cleanup=True,
        micad=daemon, boot_id=boot.strip(), error=None if error is None else str(error),
        limit='UP2 RX FCS bytes checked; no bad-FCS wire injection/TX-FCS capture, MN/CN, IRQ/throughput/realtime certification')
    (ROOT / 'board-result.json').write_text(json.dumps(report, indent=2) + '\n')
    if error: raise error
    print('OVERALL PASS P3e EDRV physical RX/TX, RX FCS, TX callbacks and safe restoration; NO MN', flush=True)

if __name__ == '__main__': main()
