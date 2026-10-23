"""Pinned P3h private DRAM only. COLD heap is a live preflight, NOT stop proof.
Cleanup proof requires independent physical CPU4/5 OFF before and after reads.
No controller MMIO, heap walk, CPU_OFF, stop/rebind or recovery commands.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from powerlink_nmt_p3h_checks import SHA, PRIVATE_SIZES, validate_snapshot, decode_snapshot, validate_heap
IMAGE = Path('/root/m7-powerlink-nmt-p3h-20261023/tl3572-m7-powerlink-p3h-up-b.elf')

def image_symbols(image):
    from verify_integrated_elf import symbols_and_data
    if hashlib.sha256(image.read_bytes()).hexdigest() != SHA: raise RuntimeError('not pinned P3h candidate')
    symbols = symbols_and_data(image)
    for name, size in PRIVATE_SIZES.items():
        address, actual, _ = symbols[name]
        if actual != size or not 0x7c200000 <= address <= 0x7ca00000-size:
            raise RuntimeError('P3h private symbol layout/range changed: ' + name)
    if 'm7_nmt_probe' not in symbols or not 0x7c200000 < symbols['__os_section_end'][0] <= 0x7ca00000:
        raise RuntimeError('not reviewed P3h image boundary/NMT entry')
    return symbols

def private_reader(symbols):
    from integrated_mmu_resources import read_reserved_dram
    def private(name):
        address, size, _ = symbols[name]
        if not 0 < size <= 2048 or not 0x7c200000 <= address <= 0x7ca00000-size: raise RuntimeError('not small private metadata')
        return read_reserved_dram(address, size)
    return private

def heap(private, symbols, phase):
    names = ('g_memTotalSize', 'g_memUsage', 'g_memPeakUsage', 'g_memStartAddr')
    def values(): return {name:struct.unpack('<Q', private(name))[0] for name in names}
    first = values()
    if first != values(): raise RuntimeError('FSC metadata changed during bounded read')
    return validate_heap(first, symbols['g_memRegion00'][0], phase)

def exception_status(private):
    raw = private('g_excInfoInternal')
    result = dict(cause=struct.unpack_from('<I', raw, 112)[0], elr=struct.unpack_from('<Q', raw, 232)[0],
        esr=struct.unpack_from('<Q', raw, 256)[0])
    if any(result.values()): raise RuntimeError('UP2 exception cache is nonzero')
    return result

def read_cold_heap(image=IMAGE):
    symbols = image_symbols(image); private = private_reader(symbols)
    raw = private('snapshot'); report = decode_snapshot(raw)
    expected = dict(ready=1, pending=0, running=0, seq=0, done=0, cmd=0, rc=0, runtime=0)
    if (any(report['cache'][k] != v for k, v in expected.items()) or not 0 < report['cache']['owner'] < 64 or
            any(raw[40:]) or private('g_ethLease') != bytes(4)):
        raise RuntimeError('live heap preflight requires fresh dormant COLD owner/no ETH lease')
    result = heap(private, symbols, 'COLD')
    exception_status(private)
    if raw != private('snapshot'): raise RuntimeError('COLD owner changed while reading heap')
    return result

def read_stopped(image=IMAGE):
    symbols = image_symbols(image)
    import run_can_direct_pair as common
    from integrated_mmu_resources import read_reserved_dram
    common.confirm_up_cpus_off(); private = private_reader(symbols)
    raw = private('snapshot')
    if raw != private('snapshot'): raise RuntimeError('stopped snapshot is not stable')
    report = validate_snapshot(raw)
    report['ethLease'] = struct.unpack('<I', private('g_ethLease'))[0]
    report['exception'] = exception_status(private)
    if report['ethLease']: raise RuntimeError('ETH lease after stop')
    report['heap'] = heap(private, symbols, 'STOPPED')
    pointer = struct.unpack('<Q', private('g_tskCbArray'))[0]
    maximum = struct.unpack('<I', private('g_tskMaxNum'))[0]
    if maximum >= 64 or not 0x7c200000 <= pointer <= 0x7ca00000-(maximum+1)*800: raise RuntimeError('pinned M6 TCB bounds changed')
    report['threads'] = []
    for index in range(maximum + 1):
        control = read_reserved_dram(pointer + index*800, 80); target = struct.unpack_from('<Q', control, 48)[0]
        for name in ('rpmsg_tty_task', 'rpmsg_listen_task'):
            if target == symbols[name][0]:
                report['threads'].append(dict(name=name, id=struct.unpack_from('<I', control, 20)[0],
                    allocated_stack=struct.unpack_from('<I', control, 16)[0]))
    if sorted((x['name'], x['allocated_stack']) for x in report['threads']) != [('rpmsg_listen_task',4096), ('rpmsg_tty_task',4096)]:
        raise RuntimeError('actual RPMsg thread stacks changed/missing')
    common.confirm_up_cpus_off()
    report.update(candidate_sha256=SHA, snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        limit='Stopped-core cache/real FSC metadata, not controller MMIO, fragmentation or real-time proof. M6 TCB/exception offsets remain pinned.')
    return report

if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(read_stopped(), indent=2))
