"""Read only the instance's reserved DRAM; never access peripheral controllers."""
import mmap
import os
import struct

from audit_integrated_mmu import table_budget
from verify_integrated_elf import symbols_and_data


def verify_tables(regions, root, raw):
    visited = set()
    mapped = 0
    for virtual, physical, size, terminal, attrs in regions:
        stride = 1 << (12 + 9 * (3 - terminal))
        for offset in range(0, size, stride):
            address = root
            for level in (1, 2, 3):
                if address % 4096 or not root <= address < root + len(raw):
                    raise RuntimeError('page table pointer outside reviewed budget')
                visited.add(address)
                index = ((virtual + offset) >> (12 + 9 * (3 - level))) & 511
                pte = struct.unpack_from('<Q', raw, address - root + index * 8)[0]
                if level == terminal:
                    expected = (physical + offset) | attrs | (3 if level == 3 else 1)
                    if pte != expected:
                        raise RuntimeError(f'incomplete/wrong PTE at {virtual + offset:#x}: {pte:#x} != {expected:#x}')
                    mapped += 1
                    break
                if pte & 3 != 3:
                    raise RuntimeError(f'missing table at {virtual + offset:#x}, level={level}')
                address = pte & 0x0000fffffffff000
    expected_pages = table_budget(regions, len(raw))['table_pages']
    if len(visited) != expected_pages:
        raise RuntimeError('unexpected real page-table count')
    return dict(table_pages=len(visited), mapped_units=mapped)


def read_reserved_dram(address, size):
    page = address & ~4095
    offset = address - page
    length = (offset + size + 4095) & ~4095
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, length, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=page) as memory:
            # Full aligned reads avoid an unaligned device-memory memcpy tail on ARM.
            data = b''.join(bytes(memory[start:start + 4096]) for start in range(0, length, 4096))
        return data[offset:offset + size]
    finally:
        os.close(fd)


def verify_running(image):
    symbols = symbols_and_data(image)
    regions = list(struct.iter_unpack('<5Q', symbols['g_mem_map_info'][2]))
    root = symbols['g_mmu_page_begin'][0]
    budget = symbols['g_mmu_page_end'][0] - root
    if root not in (0x7ba00000, 0x7ca00000) or budget != 0x10000:
        raise RuntimeError('not the reviewed integrated MMU layout')
    info_addr, info_size, _ = symbols['g_mmu_boot_info']
    image_base = root - 0x800000
    if not image_base <= info_addr < image_base + 0x800000 - 48 or info_size != 48:
        raise RuntimeError('unexpected early boot record location/layout')
    magic, units, rc, reserved, base, used, available, tcr = struct.unpack('<IIiI4Q', read_reserved_dram(info_addr, 48))
    result = verify_tables(regions, root, read_reserved_dram(root, budget))
    if (magic != 0x4d4d5537 or rc != 0 or reserved != 0 or units != result['mapped_units'] or
            base != root or used != result['table_pages'] * 4096 or available != budget):
        raise RuntimeError('early MMU boot record disagrees with actual tables')
    return dict(**result, root=hex(root), used_bytes=used, budget_bytes=available, rc=rc, tcr=hex(tcr))
