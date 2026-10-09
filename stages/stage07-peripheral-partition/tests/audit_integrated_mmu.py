"""Offline page-table budget audit for the present 4 KiB / L1-start RK3572 maps."""
import json
import argparse
from pathlib import Path
import struct

from verify_integrated_elf import symbols_and_data


def table_budget(regions, available_bytes):
    # Matches bsp/mmu.c: max VA <= 2**32 selects 32 VA bits and start level 1.
    if not regions or max(r[0] + r[2] for r in regions) > 2**32:
        raise ValueError('audit only supports the current <=32-bit VA map')
    tables = {()}
    first_overflow = None
    for virtual, physical, size, level, attrs in regions:
        if level not in (2, 3) or size <= 0:
            raise ValueError('audit only supports nonempty L2/L3 mappings')
        stride = 1 << (12 + 9 * (3 - level))
        if virtual % stride or physical % stride or size % stride:
            raise ValueError('mapping is not aligned to its terminal level')
        for address in range(virtual, virtual + size, stride):
            tables.add((address >> 30,))
            if level == 3:
                tables.add((address >> 30, (address >> 21) & 511))
            if first_overflow is None and len(tables) * 4096 > available_bytes:
                first_overflow = hex(virtual)
    required_bytes = len(tables) * 4096
    return dict(table_pages=len(tables), required_bytes=required_bytes,
                available_bytes=available_bytes, fits=required_bytes <= available_bytes,
                first_overflow_region=first_overflow)


def audit(path):
    symbols = symbols_and_data(path)
    regions = list(struct.iter_unpack('<5Q', symbols['g_mem_map_info'][2]))
    budget = symbols['g_mmu_page_end'][0] - symbols['g_mmu_page_begin'][0]
    return dict(elf=path.name, **table_budget(regions, budget))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'firmware')
    firmware = parser.parse_args().firmware_dir
    results = [audit(firmware / f'tl3572-m7-integrated-up-{role}.elf') for role in ('a', 'b')]
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if all(result['fits'] for result in results) else 1)
