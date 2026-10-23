"""READ ONLY completed failed P3g cache while owner may still be alive.
This is NOT stopped-resource proof or a recovery/CPU_OFF command. No controller MMIO.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from powerlink_nmt_checks import SHA, SNAPSHOT_BYTES, decode_snapshot
IMAGE = Path('/root/m7-powerlink-nmt-p3g-20261023/tl3572-m7-powerlink-p3g-up-b.elf')
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--read-completed-failed-cache', action='store_true'); a = p.parse_args()
    if not a.read_completed_failed_cache: raise RuntimeError('explicit failed-cache inspection required')
    from integrated_mmu_resources import read_reserved_dram
    from verify_integrated_elf import symbols_and_data
    if hashlib.sha256(IMAGE.read_bytes()).hexdigest() != SHA: raise RuntimeError('not pinned candidate')
    symbols = symbols_and_data(IMAGE)
    def private(name, expected):
        address, size, _ = symbols[name]
        if size != expected or not 0x7c200000 <= address <= 0x7ca00000 - size: raise RuntimeError('private bounds changed')
        return read_reserved_dram(address, size)
    raw = private('snapshot', SNAPSHOT_BYTES)
    if raw != private('snapshot', SNAPSHOT_BYTES): raise RuntimeError('cache changed, not a stable completed failure')
    report = decode_snapshot(raw); cache = report['cache']
    expected = dict(ready=0, pending=0, running=0, seq=1, done=1, cmd=7, rc=4, runtime=0xffffffff, owner=6)
    if any(cache[k] != v for k, v in expected.items()) or report['mn']['state'] != 3:
        raise RuntimeError('not this exact completed failed window')
    exception = private('g_excInfoInternal', 520)
    report.update(candidate_sha256=SHA, ethLease=struct.unpack('<I', private('g_ethLease', 4))[0],
        exception=dict(cause=struct.unpack_from('<I', exception, 112)[0], elr=struct.unpack_from('<Q', exception, 232)[0],
            esr=struct.unpack_from('<Q', exception, 256)[0]), snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        limit='Stable FAILED owner cache only; UP2/ETH/CNTP resources retained. No MMIO readback or safe-to-stop/rebind proof.')
    print(json.dumps(report, indent=2))
