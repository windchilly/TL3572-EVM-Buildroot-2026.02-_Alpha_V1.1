"""Explicitly approved recovery of ONE P3f pre-command fault, not an unsafe override.
Exact image/boot/exception/dormant cache/zero lease plus independent physical OFF.
Never force a running CPU off; no restart, MN command, PHY proxy or test frame.
"""
import hashlib
from pathlib import Path
import struct
import time
import run_can_direct_pair as common
import eth3_l2_smoke as ethernet
from integrated_mmu_resources import read_reserved_dram
from verify_integrated_elf import symbols_and_data

ROOT = Path('/root/m7-powerlink-mn-p3f-20261023')
CLIENT = 'up-b-m7-plk-mn-probe'
IMAGE = 'b00cdf67837d3359488385f4709fa1a162cd4ea6a791855c6f9708c1411992c1'
BOOT = '6974ac40-f3a2-4433-a5b8-11ec4318248f'
if __name__ == '__main__':
    image = ROOT / 'tl3572-m7-powerlink-p3f-up-b.elf'
    if hashlib.sha256(image.read_bytes()).hexdigest() != IMAGE: raise RuntimeError('not exact failed candidate')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != BOOT: raise RuntimeError('boot changed')
    daemon = common.micad_state()
    if daemon != dict(MainPID='328', NRestarts='0', ActiveState='active'): raise RuntimeError('daemon changed')
    symbols = symbols_and_data(image)
    def private(name, count=None):
        address, size, _ = symbols[name]
        if not 0x7c200000 <= address <= 0x7ca00000 - size: raise RuntimeError('not private image')
        return read_reserved_dram(address, size if count is None else count)
    exception = private('g_excInfoInternal')
    if len(exception) != 520 or struct.unpack_from('<I', exception, 120)[0] != 9 or \
        struct.unpack_from('<Q', exception, 232)[0] != 0x26262626 or \
        struct.unpack_from('<Q', exception, 256)[0] != 0x8a000000: raise RuntimeError('not exact pre-command exception')
    if struct.unpack('<I', private('g_ethLease'))[0]: raise RuntimeError('ETH lease not zero')
    cache = private('snapshot', 80)
    if struct.unpack_from('<9I', cache) != (1,0,0,0,0,0,0,0,6) or \
        any(struct.unpack_from('<5I', cache, 40)) or any(struct.unpack_from('<2Q', cache, 64)):
        raise RuntimeError('not untouched COLD/seq0/cmd0 MN cache')
    reader = common.load_log_reader()
    messages = common.new_log_messages(reader, 'up-b', 159)
    if not messages or any(boot != 4 for _, boot, _ in messages) or any(
            '[plk-mn-probe] BEGIN' in text for _, _, text in messages): raise RuntimeError('unexpected command/boot log')
    status = common.command('mcsctl', 'status')
    if CLIENT not in status or status.count('Offline') != 2: raise RuntimeError('unexpected clients')
    common.confirm_up_cpus_off()  # Mandatory independent proof before ANY state change.
    print('EXACT FAULT/DORMANT CACHE/ZERO LEASE/CPU4+5 ALREADY OFF PASS; reconcile only, no forced CPU_OFF/reboot', flush=True)
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
    else: raise RuntimeError('Linux100full restore failed; retain hold')
    common.command('rmmod', 'm7_eth2_power_hold')
    if Path('/sys/module/m7_eth2_power_hold').exists() or list(Path('/dev').glob('ttyRPMSG*')):
        raise RuntimeError('hold/endpoint remains')
    if common.micad_state() != daemon or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != BOOT:
        raise RuntimeError('daemon/boot drift')
    print(common.command('mcsctl', 'status'), flush=True)
    print(common.command('ip', '-brief', 'address'), flush=True)
    print('RECOVERY PASS: Linux ETH2/3 full restored, hold/endpoints/client removed, CPU4/5 OFF; no board reboot', flush=True)
