"""Read retired P3c task cache from reserved DRAM only; no controller access."""
import argparse
import json
from pathlib import Path
import struct
from integrated_mmu_resources import read_reserved_dram
from verify_integrated_elf import symbols_and_data

def decode(raw):
    # Pinned AArch64 LP64 layout. Fail closed if the declared ELF size changes.
    if len(raw) != 304: raise ValueError('Not the pinned final P3c snapshot layout')
    result = dict(zip(('ready', 'pending', 'running', 'seq', 'done', 'cmd', 'rc', 'runtime', 'owner'), struct.unpack_from('<9I', raw)))
    names = ('counter', 'ticks', 'affinity', 'interrupts', 'maxIrqLate', 'level', 'frequency', 'cntp', 'cntv', 'enabled', 'pending', 'active', 'group', 'config', 'priority30', 'priority27', 'typer', 'cpuControl')
    for name, offset in (('before', 80), ('after', 176)):
        result[name] = dict(zip(names, struct.unpack_from('<5Q13I', raw, offset)))
    result['timer'] = dict(zip(('callbacks', 'maxTaskLate', 'result', 'clean', 'samples'), struct.unpack_from('<2Q3I', raw, 272)))
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('image', type=Path); a = p.parse_args()
    address, size, _ = symbols_and_data(a.image)['snapshot']
    if size != 304 or not 0x7c200000 <= address <= 0x7ca00000 - size:
        raise ValueError('Unexpected private P3c cache')
    print(json.dumps(decode(read_reserved_dram(address, size)), indent=2))
