#!/usr/bin/env python3
"""Approved temporary ETH2 handoff, PHY/MAC100-half, no DMA/test frames/MN.
Unknown startup/stop retains UP2+shared power hold. Never force recovery/reboot.
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
import eth3_l2_smoke as ethernet
import eth2_resources as fabric
import integrated_mmu_resources as mmu
import run_can_direct_pair as common
import run_integrated_passive as passive
from powerlink_eth_checks import fields, quiescent, validate_probe, link_mode

ROOT = Path('/root/m7-powerlink-eth-p3d-20261023')
CLIENT = 'up-b-m7-plk-eth'
DEVICE = Path('/sys/bus/platform/devices/2a040000.ethernet')
DRIVER = Path('/sys/bus/platform/drivers/rk_gmac-dwmac')
MODULE = Path('/root/m7-eth-direct-20261010/m7_eth2_power_hold.ko')
MODULE_HASH = 'b071d4346d0d3310e22ffd2d1ae9ce2dcc1f3a2784ae94efd05a0798a546fc8d'
ALLOWED = ('M7 status', 'PLK status', 'PLK eth-status', 'PLK eth-probe')


def diagnostic(fd, text):
    if text not in ALLOWED: raise ValueError('no-frame runner command denied')
    data = (text + '\n').encode('ascii')
    if os.write(fd, data) != len(data): raise RuntimeError('short diagnostic write')
    received = bytearray(); end = time.monotonic() + 5
    while time.monotonic() < end:
        if select.select([fd], [], [], .1)[0]:
            try: received.extend(os.read(fd, 4096))
            except BlockingIOError: continue
            if b'\n' in received: return received.decode('ascii').strip()
    raise RuntimeError(f'diagnostic timeout: {bytes(received)!r}')


def management():
    if Path('/sys/class/net/eth0/device').resolve().name != '29d20000.ethernet':
        raise RuntimeError('management port identity mismatch')
    address = common.command('ip', '-4', '-o', 'addr', 'show', 'dev', 'eth0')
    if '192.168.2.141/24' not in address: raise RuntimeError('management address mismatch')
    return dict(address=address, routes=common.command('ip', 'route'),
                cpus=Path('/sys/devices/system/cpu/online').read_text(),
                driver=str(Path('/sys/class/net/eth0/device/driver').resolve()))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-isolated-loop-handoff', action='store_true')
    p.add_argument('--sha256', required=True)
    p.add_argument('--cycles', type=int, choices=range(1, 4), default=3)
    a = p.parse_args()
    if not a.confirm_isolated_loop_handoff: raise RuntimeError('explicit no-frame handoff approval required')
    if os.geteuid() != 0: raise RuntimeError('requires board root')
    image = ROOT / 'tl3572-m7-powerlink-p3d-up-b.elf'
    config = ROOT / f'{CLIENT}.conf'
    if hashlib.sha256(image.read_bytes()).hexdigest() != a.sha256: raise RuntimeError('candidate SHA mismatch')
    if hashlib.sha256(MODULE.read_bytes()).hexdigest() != MODULE_HASH: raise RuntimeError('power hold SHA mismatch')
    if config.read_text().splitlines() != ['[Mica]', f'Name={CLIENT}', 'CPU=5', f'ClientPath={image}', 'AutoBoot=no']:
        raise RuntimeError('temporary config mismatch')
    status = common.command('mcsctl', 'status')
    if status.count('Offline') != 2 or any(name not in status for name in ('up-a', 'up-b')):
        raise RuntimeError('requires two original Offline clients')
    if list(Path('/dev').glob('ttyRPMSG*')) or Path('/sys/module/m7_eth2_power_hold').exists():
        raise RuntimeError('existing endpoint/power hold; refuse concurrent test')
    if int(Path('/proc/sys/kernel/tainted').read_text()) & 128: raise RuntimeError('kernel Oops taint')
    left, right = ethernet.preflight()
    if common.command('ip', '-4', '-o', 'addr', 'show', 'dev', left.name).strip() or common.command('ip', 'route', 'show', 'dev', left.name).strip():
        raise RuntimeError('ETH2 carries IP/routes: no handoff permitted')
    common.confirm_up_cpus_off()
    before, daemon = passive.snapshot(), common.micad_state()
    mgmt = management(); boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    if daemon.get('ActiveState') != 'active': raise RuntimeError('micad inactive')
    reader = common.load_log_reader(); baseline = common.log_header(reader, 'up-b')[1]
    held = detached = down = created = start_attempted = False
    safe, fd, error, results = True, None, None, []
    print('SCOPE: temporary UP2 ONLY; ETH2 PHY/MAC100-half; no DMA/test frames/MN/timer/CAN/UART/reboot/boot config', flush=True)
    print('BEFORE ' + json.dumps(dict(management=mgmt, micad=daemon, boot=boot.strip(), peripherals=before), sort_keys=True), flush=True)
    try:
        common.command('insmod', str(MODULE)); held = True
        power = Path('/sys/kernel/debug/pm_genpd/pm_genpd_summary').read_text()
        if 'm7-eth2-power-hold' not in power: raise RuntimeError('power hold absent from genpd')
        down = True; common.command('ip', 'link', 'set', left.name, 'down')
        detached = True; (DRIVER / 'unbind').write_text(DEVICE.name)
        if (DEVICE / 'driver').exists(): raise RuntimeError('Linux GMAC1 remains bound')
        power = Path('/sys/kernel/debug/pm_genpd/pm_genpd_summary').read_text()
        if not any(line.startswith('nvm0 ') and ' on ' in line for line in power.splitlines()):
            raise RuntimeError('NVM0 not held on; no UP2 MMIO permitted')
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
        required = dict(ready='1', pending='0', running='0', seq='0', done='0', state='0', nmt='0x0', processes='0', events='0')
        if not all(state.get(k) == v for k, v in required.items()): raise RuntimeError('not dormant COLD')
        expected = 'M7 UP2 ready=1 pending=0x0 running=0x0 rc=0/0/0 done=0/0/0 eth_rc=0 eth_done=0'
        if diagnostic(fd, 'M7 status') != expected: raise RuntimeError('peripheral startup not passive')
        safe = True
        for cycle in range(1, a.cycles + 1):
            safe = False
            reply = diagnostic(fd, 'PLK eth-probe'); print(reply, flush=True)
            if reply != f'PLK UP2 ACCEPTED seq={cycle}': raise RuntimeError('probe not accepted/unknown state')
            end = time.monotonic() + 25
            while time.monotonic() < end:
                state = fields(diagnostic(fd, 'PLK status'), 'PLK UP2')
                if state.get('done') == str(cycle) and state.get('running') == '0' and state.get('pending') == '0': break
                time.sleep(.1)
            else: raise RuntimeError('ETH owner timeout')
            reply = diagnostic(fd, 'PLK eth-status'); print(reply, flush=True)
            safe = quiescent(fields(reply, 'PLK UP2 ETH'))
            result = validate_probe(reply)
            if not all(state.get(k) == v for k, v in dict(ready='1', state='0', nmt='0x0', processes='0', events='0', cmd='4', rc='0x0', runtime='0x0').items()):
                safe = False
                raise RuntimeError('MN/runtime left dormant state')
            end = time.monotonic() + 8
            while time.monotonic() < end:
                peer_text = common.command('ethtool', right.name)
                peer = link_mode(peer_text)
                if peer['Speed'] == '100Mb/s' and peer['Duplex'] == 'Half' and peer['Link detected'] == 'yes': break
                time.sleep(.2)
            else: raise RuntimeError('ETH3 did not report matching100-half/link')
            print(f'ETH CYCLE {cycle} PASS\nPEER\n{peer_text}', flush=True)
            results.append(dict(cycle=cycle, up2=result, peer=peer))
            if management() != mgmt: raise RuntimeError('management/CPU drift')
            passive.compare_snapshot(before, passive.snapshot())
        if diagnostic(fd, 'M7 status') != expected:
            safe = False; raise RuntimeError('peripheral worker executed')
    except Exception as exc: error = exc
    finally:
        if fd is not None: os.close(fd)
        try:
            for seq, generation, message in common.new_log_messages(reader, 'up-b', baseline):
                print(f'[up-b boot={generation} seq={seq}] {message}', end='' if message.endswith('\n') else '\n', flush=True)
        except Exception as exc: print('LOG READ ERROR ' + str(exc), flush=True)
        if not safe:
            print('UNSAFE/UNKNOWN: retain temporary UP2 and shared power/root hold; NO CPU_OFF/Linux rebind/rmmod/reboot/retry', flush=True)
            raise RuntimeError(str(error))
        if start_attempted: common.control('stop', CLIENT)
        if created: common.control('rm', CLIENT)
        common.confirm_up_cpus_off()
        if detached and not (DEVICE / 'driver').exists(): (DRIVER / 'bind').write_text(DEVICE.name)
        if down: common.command('ip', 'link', 'set', left.name, 'up')
        if detached:
            end = time.monotonic() + 20
            while time.monotonic() < end:
                try: ethernet.preflight(); break
                except (RuntimeError, OSError): time.sleep(.2)
            else: raise RuntimeError('Linux100-full restore failed; keep shared hold')
        if held: common.command('rmmod', 'm7_eth2_power_hold')
        if Path('/sys/module/m7_eth2_power_hold').exists(): raise RuntimeError('residual power hold: no forced removal')
        passive.compare_snapshot(before, passive.snapshot())
        if management() != mgmt or common.micad_state() != daemon or Path('/proc/sys/kernel/random/boot_id').read_text() != boot:
            raise RuntimeError('final management/CPU/micad/boot drift')
        if list(Path('/dev').glob('ttyRPMSG*')) or common.command('mcsctl', 'status').count('Offline') != 2:
            raise RuntimeError('temporary client cleanup incomplete')
        print('CLEANUP PASS: CPU4/5 OFF, original clients Offline, Linux ETH2/3 full restored, hold removed, CAN/UART/ETH1/micad/boot unchanged', flush=True)
    report = dict(phase='P3d PHY/MAC100-half hardware only', passed=error is None, cycles=results,
        candidate_sha256=a.sha256, micad=daemon, boot_id=boot.strip(), cleanup=True, test_frames=0,
        error=None if error is None else str(error),
        limit='No DMA descriptors/start, EDRV physical TX/RX, FCS, MN/CN or realtime acceptance')
    (ROOT / 'board-result.json').write_text(json.dumps(report, indent=2) + '\n')
    if error: raise error
    print('OVERALL PASS P3d real PHY/MAC100-half + safe restoration; NO frame/MN acceptance', flush=True)


if __name__ == '__main__': main()
