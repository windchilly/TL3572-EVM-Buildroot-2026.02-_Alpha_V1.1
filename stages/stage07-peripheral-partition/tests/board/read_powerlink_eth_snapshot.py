"""Read only reserved private DRAM, never controller MMIO or task state writes.
Running-core values may be stale: not independent proof that CPU/DMA is stopped.
"""
import argparse
import json
from pathlib import Path
import struct
from integrated_mmu_resources import read_reserved_dram
from verify_integrated_elf import symbols_and_data

def decode(raw):
    if len(raw) != 400: raise ValueError('Not pinned P3d LP64 snapshot layout')
    result = dict(zip(('ready', 'pending', 'running', 'seq', 'done', 'cmd', 'rc', 'runtime', 'owner'), struct.unpack_from('<9I', raw)))
    result['mn'] = dict(zip(('state', 'owner', 'lastError', 'lastEvent', 'nmtState'), struct.unpack_from('<5I', raw, 40)))
    result['mn'].update(zip(('processes', 'events'), struct.unpack_from('<2Q', raw, 64)))
    names = ('phyHigh', 'phyLow', 'bmcr', 'bmsr', 'mac', 'tx', 'rx', 'dma', 'macIrq', 'dmaIrq')
    result['eth'] = {name: dict(zip(names, struct.unpack_from('<10I', raw, offset)))
                     for name, offset in (('configured', 304), ('stopped', 344))}
    result['eth'].update(zip(('result', 'clean', 'leaseBefore', 'leaseAfter'), struct.unpack_from('<4I', raw, 384)))
    return result


def decode_exception(raw):
    # Fixed M6 no-FPU ExcInfo: osVer[48], appVer[64], LP64 ExcRegInfo.
    if len(raw) != 520: raise ValueError('Not pinned no-FPU ExcInfo layout')
    esr = struct.unpack_from('<Q', raw, 256)[0]
    return dict(cause=struct.unpack_from('<I', raw, 112)[0], task=struct.unpack_from('<I', raw, 120)[0],
        elr=hex(struct.unpack_from('<Q', raw, 232)[0]), esr=hex(esr), ec=esr >> 26 & 63,
        far=hex(struct.unpack_from('<Q', raw, 248)[0]), sp=hex(struct.unpack_from('<Q', raw, 152)[0]),
        x3=hex(struct.unpack_from('<Q', raw, 488)[0]))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('image', type=Path); a = p.parse_args()
    symbols = symbols_and_data(a.image)
    report = {'limit': 'Reserved DRAM only, possibly stale on a running core; NO cleanup authorization', 'symbols': {}}
    for name in ('snapshot', 'g_ethLease', 'g_uniFlag', 'g_excInfoInternal'):
        address, size, _ = symbols[name]
        if not 0x7c200000 <= address <= 0x7ca00000 - size or size > 1024: raise ValueError('outside private image')
        raw = read_reserved_dram(address, size)
        report['symbols'][name] = {'address': hex(address), 'bytes': size, 'raw_hex': raw.hex()}
        if name == 'snapshot': report['snapshot'] = decode(raw)
        elif name == 'g_excInfoInternal': report['exception'] = decode_exception(raw)
        else: report[name] = struct.unpack('<I', raw)[0]
    print(json.dumps(report, indent=2))
