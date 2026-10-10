#!/usr/bin/env python3
"""Explicit ETH2/UP2 handoff and bounded L2 test against isolated onboard ETH3.
No CAN/UART tests, IP configuration, DT changes, flash or board reboot.
"""
import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import termios
import time
import tty

import eth3_l2_smoke as codec
import integrated_mmu_resources as mmu
import run_can_direct_pair as common
import run_integrated_passive as passive

ROOT = Path('/root/m7-eth-direct-20261010')
CLIENTS = ('up-a-m7-eth', 'up-b-m7-eth')
IMAGE_HASHES = ('e44c3a976f5da58a29fab4db6ce50cf4a028e1716d0511fa17117941ce1d15eb',
                'b05e3e63e3794ce61e660c27aa8a209dcc9ee7fd9cbb79c295ab9fde0c4d851d')
MODULE_HASH = '3b1e96999bfd6ad5a4d9ba5eab9e92d8051209567935158aafadc86bf84d0c1b'
DRIVER = Path('/sys/bus/platform/drivers/rk_gmac-dwmac')
DEVICE = '2a040000.ethernet'
UP_MAC = bytes.fromhex('025550320002')


def diagnostic(fd, text):
    if text not in ('M7 status', 'M7 run eth 0', 'M7 run eth 64', 'M7 run eth 1514'):
        raise ValueError('Ethernet runner forbids all other run commands')
    data = (text + '\n').encode()
    if os.write(fd, data) != len(data):
        raise RuntimeError('short RPMsg command')
    result = bytearray()
    end = time.monotonic() + 5
    while time.monotonic() < end:
        if select.select([fd], [], [], 0.1)[0]:
            try:
                result.extend(os.read(fd, 4096))
            except BlockingIOError:
                continue
            if b'\n' in result:
                return result.decode().strip()
    raise RuntimeError('RPMsg diagnostic timeout')


def logs(reader, seq):
    return ''.join(m for _, _, m in common.new_log_messages(reader, 'up-b', seq))


def wait_marker(reader, seq, marker, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        text = logs(reader, seq)
        if marker in text:
            return text
        if '[eth] FAIL' in text or '[eth] UNSAFE' in text or '[integrated] UP2 end module=3 rc=' in text:
            raise RuntimeError(f'Ethernet test failed before {marker}: {text}')
        time.sleep(0.05)
    raise RuntimeError(f'timeout waiting {marker}: {logs(reader, seq)}')


def ethernet_owner():
    left, right = codec.preflight()
    addresses = common.command('ip', '-4', '-o', 'addr', 'show', 'dev', left.name)
    if addresses.strip() or common.command('ip', 'route', 'show', 'dev', left.name).strip():
        raise RuntimeError('ETH2 has IPv4/routes: refuse management network handoff')
    if (Path('/sys/class/net/eth0/device').resolve().name != '29d20000.ethernet' or
            '192.168.2.141/24' not in common.command('ip', '-4', '-o', 'addr', 'show', 'dev', 'eth0')):
        raise RuntimeError('ETH1 management identity mismatch')
    return left, right


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-board-loop', action='store_true')
    parser.add_argument('--profile', choices=('probe', 'frames'), default='probe')
    parser.add_argument('--reverse-stop', action='store_true')
    args = parser.parse_args()
    left, right = ethernet_owner()
    if not args.confirm_board_loop:
        print('READ-ONLY ETH2/ETH3 preflight PASS; no handoff or transmit')
        return
    if os.geteuid() != 0 or common.command('mcsctl', 'status').count('Offline') != 2:
        raise RuntimeError('requires root and exactly two original offline clients')
    if list(Path('/dev').glob('ttyRPMSG*')) or Path('/sys/module/m7_eth2_power_hold').exists():
        raise RuntimeError('existing endpoint/power hold: refuse concurrent handoff')
    common.confirm_up_cpus_off()
    for index, digest in enumerate(IMAGE_HASHES):
        image = ROOT / f'tl3572-m7-integrated-up-{chr(97 + index)}.elf'
        if hashlib.sha256(image.read_bytes()).hexdigest() != digest:
            raise RuntimeError('firmware differs from static-audited Ethernet candidate')
    module = ROOT / 'm7_eth2_power_hold.ko'
    if hashlib.sha256(module.read_bytes()).hexdigest() != MODULE_HASH:
        raise RuntimeError('power hold module mismatch')
    before = passive.snapshot()
    daemon = common.micad_state()
    if daemon['ActiveState'] != 'active':
        raise RuntimeError('micad inactive')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    routes = common.command('ip', 'route')
    peer_mac = bytes.fromhex((right / 'address').read_text().strip().replace(':', ''))
    reader = common.load_log_reader()
    seqs = {name: common.log_header(reader, name)[1] for name in ('up-a', 'up-b')}
    created, fds, held, unbound, safe = [], {}, False, False, True
    error = None
    print(f'BASELINE boot={boot.strip()} micad={daemon} ETH1 management untouched', flush=True)
    try:
        common.command('insmod', str(module)); held = True
        power = Path('/sys/kernel/debug/pm_genpd/pm_genpd_summary').read_text()
        if 'm7-eth2-power-hold' not in power:
            raise RuntimeError('NVM0 power guard absent from genpd')
        print('POWER HOLD\n' + power, flush=True)
        common.command('ip', 'link', 'set', left.name, 'down')
        unbound = True
        (DRIVER / 'unbind').write_text(DEVICE)
        if (Path('/sys/bus/platform/devices') / DEVICE / 'driver').exists():
            raise RuntimeError('Linux GMAC1 still owns device')
        power = Path('/sys/kernel/debug/pm_genpd/pm_genpd_summary').read_text()
        if not any(line.startswith('nvm0 ') and ' on ' in line for line in power.splitlines()):
            raise RuntimeError('NVM0 is not held ON after detach; no UP2 MMIO permitted')
        print('GMAC1 UNBOUND; NVM0 ON; UP2 exclusively owns MAC/MDIO/PHY/DMA', flush=True)
        for index, client in enumerate(CLIENTS):
            config = ROOT / f'{client}.conf'
            expected = {'[Mica]', 'AutoBoot=no', f'Name={client}', f'CPU={index + 4}',
                        f'ClientPath={ROOT}/tl3572-m7-integrated-up-{chr(97 + index)}.elf'}
            if not expected.issubset(config.read_text().splitlines()):
                raise RuntimeError('temporary config mismatch')
            common.control('create', str(config)); created.append(client)
            known = set(Path('/dev').glob('ttyRPMSG*'))
            common.control('start', client)
            end = time.monotonic() + 15
            while time.monotonic() < end:
                added = set(Path('/dev').glob('ttyRPMSG*')) - known
                if len(added) == 1:
                    path = added.pop(); break
                time.sleep(0.1)
            else:
                raise RuntimeError('no unique RPMsg endpoint')
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_NOCTTY)
            tty.setraw(fd); termios.tcflush(fd, termios.TCIOFLUSH); fds[client] = fd
            print(f'{client} MMU {json.dumps(mmu.verify_running(ROOT / f"tl3572-m7-integrated-up-{chr(97 + index)}.elf"))}', flush=True)
            status = diagnostic(fd, 'M7 status')
            expected_status = f'M7 UP{index + 1} ready=1 pending=0x0 running=0x0 rc=0/0/0 done=0/0/0 eth_rc=0 eth_done=0'
            if status != expected_status:
                raise RuntimeError('nonpassive startup: ' + status)
        with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(codec.ETHERTYPE)) as peer:
            peer.bind((right.name, 0))
            profiles = (0,) if args.profile == 'probe' else (0, 64, 1514)
            for length in profiles:
                seq = common.log_header(reader, 'up-b')[1]
                safe = False
                reply = diagnostic(fds[CLIENTS[1]], f'M7 run eth {length}')
                if reply != 'M7 UP2 ACCEPTED mask=0x8':
                    safe = True; raise RuntimeError('ETH command not accepted: ' + reply)
                if length:
                    wait_marker(reader, seq, '[eth] READY', 20)
                    start = time.monotonic()
                    for number in range(1000):
                        request = codec.frame(UP_MAC, peer_mac, 1, number, length)
                        expected = codec.frame(peer_mac, UP_MAC, 2, number, length)
                        if peer.send(request) != length:
                            raise RuntimeError('short ETH3 send')
                        codec.receive(peer, expected)
                    print(f'PHYSICAL PEER PASS raw={length} tx=1000 rx=1000 bytes_each={length * 1000} elapsed={time.monotonic()-start:.3f}', flush=True)
                text = wait_marker(reader, seq, '[eth] QUIESCED reset=1', 20)
                safe = True
                wait_marker(reader, seq, '[integrated] UP2 end module=3 rc=0', 5)
                print(text, flush=True)
                status = diagnostic(fds[CLIENTS[1]], 'M7 status')
                if 'pending=0x0 running=0x0 rc=0/0/0 done=0/0/0 eth_rc=0' not in status:
                    raise RuntimeError('non-Ethernet worker executed or ETH failed: ' + status)
                print(status, flush=True)
    except Exception as exc:
        error = exc
    finally:
        if not safe:
            # Give the bounded firmware task time to finish/reset DMA before CPU_OFF.
            end = time.monotonic() + 40
            while time.monotonic() < end:
                if '[eth] QUIESCED reset=1' in logs(reader, seq):
                    safe = True; break
                if '[eth] UNSAFE' in logs(reader, seq):
                    break
                time.sleep(0.1)
        for fd in fds.values():
            os.close(fd)
        for name in seqs:
            print(f'FINAL LOG {name}\n' + ''.join(m for _, _, m in common.new_log_messages(reader, name, seqs[name])), flush=True)
        if not safe:
            print('UNSAFE: retain power hold and UP2 owner; NO CPU_OFF/Linux rebind', flush=True)
            raise RuntimeError(f'{error}; DMA quiescence not proven')
        common.CLIENTS = tuple(created)
        common.STOP_CLIENTS = tuple(reversed(created)) if args.reverse_stop else tuple(created)
        common.cleanup_clients()
        common.confirm_up_cpus_off()
        if unbound:
            (DRIVER / 'bind').write_text(DEVICE)
            common.command('ip', 'link', 'set', 'eth1', 'up')
            end = time.monotonic() + 15
            while time.monotonic() < end:
                try:
                    ethernet_owner(); break
                except (RuntimeError, OSError):
                    time.sleep(0.2)
            else:
                raise RuntimeError('Linux ETH2/ETH3 not restored; keep power hold')
        if held:
            common.command('rmmod', 'm7_eth2_power_hold')
        passive.compare_snapshot(before, passive.snapshot())
        if common.micad_state() != daemon or Path('/proc/sys/kernel/random/boot_id').read_text() != boot:
            raise RuntimeError('daemon changed/restarted or board rebooted')
        if common.command('ip', 'route') != routes:
            raise RuntimeError('management routes changed')
        if list(Path('/dev').glob('ttyRPMSG*')):
            raise RuntimeError('RPMsg cleanup failed')
        print('CLEANUP PASS CPUs OFF, original instances Offline, Linux ETH2/3 restored, power hold removed, CAN/UART snapshot unchanged, ETH1/micad/boot unchanged', flush=True)
    if error:
        raise error
    print(f'OVERALL PASS UP2 direct Ethernet profile={args.profile}; DMA polling, NOT IRQ/IP/throughput/coldboot acceptance', flush=True)


if __name__ == '__main__':
    main()
