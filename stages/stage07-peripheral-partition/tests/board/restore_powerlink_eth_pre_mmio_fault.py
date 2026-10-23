"""One exact recovery: P3d CASAL undefined instruction BEFORE hardware acquire.
Requires physical CPU4/5 OFF, exact fault/image/lease; never stops a live CPU.
Not a generic override for unsafe DMA or unknown UP state.
"""
import hashlib
import json
from pathlib import Path
import struct
import time
import run_can_direct_pair as common
import eth3_l2_smoke as ethernet
from integrated_mmu_resources import read_reserved_dram
from verify_integrated_elf import symbols_and_data

ROOT = Path('/root/m7-powerlink-eth-p3d-20261023')
CLIENT = 'up-b-m7-plk-eth'
BOOT = '6974ac40-f3a2-4433-a5b8-11ec4318248f'
IMAGE = '73689e61b9edbd6f337b6affb47faf057db96ec03d7ba195efad8e3832d6f348'

if __name__ == '__main__':
    image = ROOT / 'tl3572-m7-powerlink-p3d-up-b.elf'
    if hashlib.sha256(image.read_bytes()).hexdigest() != IMAGE: raise RuntimeError('not exact failed candidate')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != BOOT: raise RuntimeError('boot changed')
    daemon = common.micad_state()
    if daemon != {'MainPID': '328', 'NRestarts': '0', 'ActiveState': 'active'}: raise RuntimeError('daemon changed')
    symbols = symbols_and_data(image)
    addr, size, _ = symbols['g_excInfoInternal']
    if size != 520: raise RuntimeError('exception layout mismatch')
    raw = read_reserved_dram(addr, size)
    elr, esr = struct.unpack_from('<Q', raw, 232)[0], struct.unpack_from('<Q', raw, 256)[0]
    start, size, code = symbols['TakeLease']
    if elr != 0x7c20fe68 or esr != 0x02000000 or not start <= elr < start + size or struct.unpack_from('<I', code, elr - start)[0] != 0x88e0fc64:
        raise RuntimeError('not exact pre-MMIO CASAL exception')
    addr, size, _ = symbols['g_ethLease']
    if size != 4 or struct.unpack('<I', read_reserved_dram(addr, size))[0]: raise RuntimeError('ETH lease not zero')
    common.confirm_up_cpus_off()  # Mandatory physical proof BEFORE any writes.
    print('EXACT PRE-MMIO FAULT + ZERO LEASE + CPU4/5 ALREADY OFF: reconcile client only; no forced CPU_OFF/reboot', flush=True)
    common.control('stop', CLIENT); common.control('rm', CLIENT)
    common.confirm_up_cpus_off()
    device = Path('/sys/bus/platform/devices/2a040000.ethernet')
    if (device / 'driver').exists(): raise RuntimeError('unexpected existing owner')
    Path('/sys/bus/platform/drivers/rk_gmac-dwmac/bind').write_text(device.name)
    common.command('ip', 'link', 'set', 'eth1', 'up')
    end = time.monotonic() + 20
    while time.monotonic() < end:
        try: ethernet.preflight(); break
        except (RuntimeError, OSError): time.sleep(.2)
    else: raise RuntimeError('Linux100full not restored; retain shared hold')
    common.command('rmmod', 'm7_eth2_power_hold')
    if Path('/sys/module/m7_eth2_power_hold').exists(): raise RuntimeError('residual hold')
    if common.micad_state() != daemon or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != BOOT:
        raise RuntimeError('daemon/boot drift')
    if list(Path('/dev').glob('ttyRPMSG*')): raise RuntimeError('RPMsg still present')
    print(common.command('mcsctl', 'status'), flush=True)
    print(common.command('ip', '-brief', 'address'), flush=True)
    print(common.command('ethtool', 'eth1'), common.command('ethtool', 'eth2'), flush=True)
    print('RECOVERY PASS: Linux100full restored, hold removed, original clients Offline, CPU4/5 OFF; no board reboot', flush=True)
