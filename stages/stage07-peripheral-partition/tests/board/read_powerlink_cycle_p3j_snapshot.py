"""Pinned P3j private DRAM only. COLD heap is a live preflight, NOT stop proof.
Cleanup proof requires independent physical CPU4/5 OFF before and after reads.
No controller MMIO, heap walk, CPU_OFF, stop/rebind or recovery commands.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from powerlink_cycle_p3j_checks import SHA, PRIVATE_SIZES, validate_snapshot, validate_heap
IMAGE = Path('/root/m7-powerlink-cycle-p3j-20261104/tl3572-m7-powerlink-p3j-up-b.elf')

def image_symbols(image):
    from verify_integrated_elf import symbols_and_data
    if hashlib.sha256(image.read_bytes()).hexdigest() != SHA: raise RuntimeError('not pinned P3j candidate')
    symbols = symbols_and_data(image)
    for name, size in PRIVATE_SIZES.items():
        address, actual, _ = symbols[name]
        if actual != size or not 0x7c200000 <= address <= 0x7ca00000-size:
            raise RuntimeError('P3j private symbol layout/range changed: ' + name)
    if 'm7_cycle_probe' not in symbols or not 0x7c200000 < symbols['__os_section_end'][0] <= 0x7ca00000:
        raise RuntimeError('not reviewed P3j image boundary/NMT entry')
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
    raw = private('snapshot')
    cache = dict(zip(('ready','pending','running','seq','done','cmd','rc','runtime','owner'), struct.unpack_from('<9I',raw)))
    expected = dict(ready=1, pending=0, running=0, seq=0, done=0, cmd=0, rc=0, runtime=0)
    if (any(cache[k] != v for k, v in expected.items()) or not 0 < cache['owner'] < 64 or
            any(raw[40:]) or private('g_ethLease') != bytes(4) or
            private('cycleReady') != bytes(4) or private('cycleAttempted') != bytes(4) or any(private('cycleResult'))):
        raise RuntimeError('live heap preflight requires fresh dormant COLD owner/no ETH lease')
    result = heap(private, symbols, 'COLD')
    exception_status(private)
    if (raw != private('snapshot') or private('cycleReady') != bytes(4) or
            private('cycleAttempted') != bytes(4) or any(private('cycleResult')) or private('g_ethLease') != bytes(4)):
        raise RuntimeError('COLD owner changed while reading heap')
    return result

def completed(private):
    names = ('snapshot','cycleResult','cycleReady','cycleAttempted')
    data = {name:private(name) for name in names}
    if data != {name:private(name) for name in names}: raise RuntimeError('P3j result/cache unstable')
    raw = data['snapshot']; cycle_raw = data['cycleResult']
    report = validate_snapshot(raw, cycle_raw, struct.unpack('<I',data['cycleReady'])[0], struct.unpack('<I',data['cycleAttempted'])[0])
    report['ethLease'] = struct.unpack('<I', private('g_ethLease'))[0]
    report['exception'] = exception_status(private)
    if report['ethLease']: raise RuntimeError('ETH lease after stop')
    if struct.unpack('<I',private('ownerTask'))[0] != report['cycle']['owner']:
        raise RuntimeError('ownerTask/private result mismatch')
    report.update(candidate_sha256=SHA, snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        cycle_sha256=hashlib.sha256(cycle_raw).hexdigest(), snapshot_hex=raw.hex(),cycle_hex=cycle_raw.hex())
    return report

def read_completed(image=IMAGE):
    # Stable completed owner publication BEFORE CPU_OFF; not a physical stop proof.
    return completed(private_reader(image_symbols(image)))

def read_stopped(image=IMAGE):
    symbols = image_symbols(image)
    import run_can_direct_pair as common
    from integrated_mmu_resources import read_reserved_dram
    common.confirm_up_cpus_off(); private = private_reader(symbols)
    report = completed(private)
    report['heap'] = heap(private, symbols, 'STOPPED')
    pointer = struct.unpack('<Q', private('g_tskCbArray'))[0]
    maximum = struct.unpack('<I', private('g_tskMaxNum'))[0]
    if maximum >= 64 or not 0x7c200000 <= pointer <= 0x7ca00000-(maximum+1)*800: raise RuntimeError('pinned M6 TCB bounds changed')
    report['threads'] = []
    for index in range(maximum + 1):
        control = read_reserved_dram(pointer + index*800, 80); target = struct.unpack_from('<Q', control, 48)[0]
        for name in ('rpmsg_tty_task', 'rpmsg_listen_task', 'Worker'):
            if target == symbols[name][0]:
                report['threads'].append(dict(name=name, id=struct.unpack_from('<I', control, 20)[0],
                    allocated_stack=struct.unpack_from('<I', control, 16)[0]))
    if sorted((x['name'], x['allocated_stack']) for x in report['threads']) != [('Worker',32768), ('rpmsg_listen_task',4096), ('rpmsg_tty_task',4096)]:
        raise RuntimeError('actual RPMsg/PLKowner stacks changed/missing')
    if next(x['id'] for x in report['threads'] if x['name']=='Worker') != report['cycle']['owner']:
        raise RuntimeError('actual PLKowner task id mismatch')
    common.confirm_up_cpus_off()
    report['limit']='Stopped-core cache/real FSC metadata, not controller MMIO, fragmentation or real-time proof. M6 TCB/exception offsets and Worker identity remain pinned to this ELF.'
    return report

if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(read_stopped(), indent=2))
