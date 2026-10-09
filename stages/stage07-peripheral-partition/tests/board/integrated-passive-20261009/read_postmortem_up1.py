import json
import mmap
import os
import struct
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
try:
    with mmap.mmap(fd, 0x2000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x7b259000) as memory:
        # Full aligned pages avoid Python's unaligned tail memcpy on ARM device memory.
        pages = bytes(memory[:0x1000]) + bytes(memory[0x1000:0x2000])
        values = {}
        for name, addr, size in [('exc', 0x7b259df0, 520), ('metal', 0x7b25aa08, 64), ('tskcb', 0x7b25a078, 8)]:
            data = pages[addr - 0x7b259000:addr - 0x7b259000 + size]
            values[name] = [hex(v) for v in struct.unpack('<' + 'Q' * (size // 8), data)]
    with mmap.mmap(fd, 0x1000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x7b2e7000) as memory:
        page = bytes(memory[:0x1000])
        fields = struct.unpack('<3Q3I4x', page[0xb90:0xb90 + 40])
        values['mmu_ctrl'] = dict(zip(('tlb_addr', 'tlb_size', 'tlb_fillptr', 'granule', 'start_level', 'va_bits'), (hex(value) for value in fields)))
        values['mmu_ctrl_note'] = 'BSS is cleared after mmu_init; these zero fields are NOT the original allocation counters.'
    values['exception'] = {
        'sctlr': values['exc'][25],
        'mmu_enabled': bool(int(values['exc'][25], 16) & 1),
        'elr': values['exc'][29],
        'far': values['exc'][31],
        'esr': values['exc'][32],
    }
    with mmap.mmap(fd, 0x8000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x7ba00000) as memory:
        raw_tables = b''.join(bytes(memory[offset:offset + 0x1000]) for offset in range(0, 0x8000, 0x1000))
    tables = {0x7ba00000 + offset: struct.unpack('<512Q', raw_tables[offset:offset + 0x1000])
              for offset in range(0, 0x8000, 0x1000)}
    def walk(va):
        table = 0x7ba00000
        path = []
        for level in (1, 2, 3):
            index = (va >> (12 + 9 * (3 - level))) & 511
            descriptor = tables[table][index]
            path.append(dict(level=level, table=hex(table), index=index, pte=hex(descriptor)))
            if (descriptor & 3) == 0:
                return dict(mapped=False, path=path)
            if level == 3 or (descriptor & 3) == 1:
                return dict(mapped=True, path=path)
            table = descriptor & 0x0000fffffffff000
            if table not in tables:
                return dict(mapped=False, error='outside reviewed table budget', path=path)
    values['page_tables'] = {
        'nonzero_entries': {hex(address): sum(value != 0 for value in table) for address, table in tables.items()},
        'mapping_walks': {hex(address): walk(address) for address in
                          (0x7a080000, 0x7b200000, 0x2a600000, 0x2ab10000, 0x2c160000,
                           0x26500000, 0x26090000, 0x260b0000, 0x26074000, 0x26086000, 0x7b000000)},
    }
    print(json.dumps(values, indent=2))
finally:
    os.close(fd)
