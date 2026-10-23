"""READ ONLY fixed failed P3g scalar allocator/platform/PDO metadata.
No heap walk, controller MMIO, CPU_OFF, lease release or recovery. UP2 may run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from powerlink_nmt_checks import SHA, decode_snapshot
IMAGE = Path('/root/m7-powerlink-nmt-p3g-20261023/tl3572-m7-powerlink-p3g-up-b.elf')
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--read-completed-failed-cache', action='store_true'); a = p.parse_args()
    if not a.read_completed_failed_cache: raise RuntimeError('explicit readonly failed-cache inspection required')
    from integrated_mmu_resources import read_reserved_dram
    from verify_integrated_elf import symbols_and_data
    if hashlib.sha256(IMAGE.read_bytes()).hexdigest() != SHA: raise RuntimeError('not pinned candidate')
    symbols = symbols_and_data(IMAGE)
    def private(name, expected):
        address, size, _ = symbols[name]
        if size != expected or not 0x7c200000 <= address <= 0x7ca00000-size: raise RuntimeError('symbol bounds changed: ' + name)
        return read_reserved_dram(address, size)
    raw = private('snapshot', 1504)
    cache = decode_snapshot(raw)
    if (raw != private('snapshot', 1504) or cache['cache']['done'] != 1 or cache['cache']['rc'] != 4 or
            cache['cache']['running'] or cache['cache']['ready'] or cache['mn']['state'] != 3): raise RuntimeError('not stable failed owner')
    sizes = {'g_memTotalSize':8, 'g_memUsage':8, 'g_memPeakUsage':8, 'g_memStartAddr':8, 'g_uniFlag':4,
        'g_uniTaskLock':2, 'irqDepth':4, 'faulted':4, 'pdokcalmem_pPdo_g':8, 'g_fscMemBitMap':4}
    values = {name:int.from_bytes(private(name, size), 'little') for name, size in sizes.items()}
    mutexes = private('mutexes', 128)
    report = dict(candidate_sha256=SHA, scalars=values,
        mutexes=[dict(token=struct.unpack_from('<Q',mutexes,i*16)[0], sem=struct.unpack_from('<H',mutexes,i*16+8)[0],
            locked=struct.unpack_from('<I',mutexes,i*16+12)[0]) for i in range(8)],
        pdou_tail_qwords=[hex(x) for x in struct.unpack_from('<8Q',private('pdouInstance_g',576),512)],
        limit='Point-in-time private metadata only, not an atomic heap snapshot, first-error record, stop proof or cleanup authorization.')
    print(json.dumps(report, indent=2))
