"""Pinned P3g private DRAM only, read AFTER independent physical CPU4/5 OFF.
No controller MMIO. Not a substitute for the candidate's real stop readbacks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from powerlink_nmt_checks import SHA, SNAPSHOT_BYTES, validate_snapshot
IMAGE = Path('/root/m7-powerlink-nmt-p3g-20261023/tl3572-m7-powerlink-p3g-up-b.elf')

def read_stopped(image=IMAGE):
    import run_can_direct_pair as common
    from integrated_mmu_resources import read_reserved_dram
    from verify_integrated_elf import symbols_and_data
    common.confirm_up_cpus_off()
    if hashlib.sha256(image.read_bytes()).hexdigest() != SHA: raise RuntimeError('not pinned P3g candidate')
    symbols = symbols_and_data(image)
    def private(name, expected=None):
        address, size, _ = symbols[name]
        if (expected is not None and size != expected) or not 0 < size <= 2048 or not 0x7c200000 <= address <= 0x7ca00000 - size:
            raise RuntimeError('private symbol layout/range changed: ' + name)
        return read_reserved_dram(address, size)
    raw = private('snapshot', SNAPSHOT_BYTES)
    if raw != private('snapshot', SNAPSHOT_BYTES): raise RuntimeError('stopped snapshot is not stable')
    report = validate_snapshot(raw)
    report['ethLease'] = struct.unpack('<I', private('g_ethLease', 4))[0]
    exception = private('g_excInfoInternal', 520)
    report['exception'] = dict(cause=struct.unpack_from('<I', exception, 112)[0],
        elr=struct.unpack_from('<Q', exception, 232)[0], esr=struct.unpack_from('<Q', exception, 256)[0])
    if report['ethLease'] or any(report['exception'].values()): raise RuntimeError('lease/exception present after stop')
    pointer = struct.unpack('<Q', private('g_tskCbArray', 8))[0]
    maximum = struct.unpack('<I', private('g_tskMaxNum', 4))[0]
    if maximum >= 64 or not 0x7c200000 <= pointer <= 0x7ca00000 - (maximum + 1) * 800:
        raise RuntimeError('pinned M6 TCB bounds changed')
    report['threads'] = []
    for index in range(maximum + 1):
        control = read_reserved_dram(pointer + index * 800, 80)
        target = struct.unpack_from('<Q', control, 48)[0]
        for name in ('rpmsg_tty_task', 'rpmsg_listen_task'):
            if target == symbols[name][0]:
                report['threads'].append(dict(name=name, id=struct.unpack_from('<I', control, 20)[0],
                    allocated_stack=struct.unpack_from('<I', control, 16)[0]))
    if sorted((x['name'], x['allocated_stack']) for x in report['threads']) != [('rpmsg_listen_task', 4096), ('rpmsg_tty_task', 4096)]:
        raise RuntimeError('actual RPMsg thread stacks changed/missing')
    common.confirm_up_cpus_off()
    report.update(candidate_sha256=SHA, snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        limit='Stopped-core private cache, not live controller MMIO or an independent real-time/heap/IRQ proof.')
    return report

if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(read_stopped(), indent=2))
