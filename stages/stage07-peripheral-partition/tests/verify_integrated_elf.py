"""Static check of the two integrated ELF64 images; Python stdlib only, no board access."""
import struct
import argparse
from pathlib import Path


def symbols_and_data(path):
    data = path.read_bytes()
    assert data[:6] == b'\x7fELF\x02\x01', 'Expected little-endian ELF64'
    assert struct.unpack_from('<H', data, 18)[0] == 183, 'Expected AArch64'
    offset = struct.unpack_from('<Q', data, 40)[0]
    stride, count = struct.unpack_from('<HH', data, 58)
    assert stride == 64 and count, 'Expected ordinary section table'
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * stride) for i in range(count)]
    result = {}
    for section in sections:
        if section[1] != 2:  # SHT_SYMTAB
            continue
        strings = sections[section[6]]
        names = data[strings[4]:strings[4] + strings[5]]
        assert section[9] == 24
        for address in range(section[4], section[4] + section[5], 24):
            name, info, other, index, value, size = struct.unpack_from('<IBBHQQ', data, address)
            name = names[name:names.find(b'\0', name)].decode('ascii')
            if name and 0 < index < count:
                target = sections[index]
                start = target[4] + value - target[3]
                content = b'' if target[1] == 8 else data[start:start + size]
                result[name] = (value, size, content)
    return result


def verify(path, cpu):
    symbols = symbols_and_data(path)
    for name in ('Rk3572IntegratedInit', 'Rk3572IntegratedInput', 'Rk3572CanClassicTest',
                 'Rk3572CanFdTest', 'Rk3572Rs232Test', 'Rk3572Rs485Test', 'UpLogBoot'):
        assert name in symbols and symbols[name][1], f'Missing function: {name}'
    assert 'Rk3572CanDirectTest' not in symbols, 'Legacy boot-test export unexpectedly linked'
    from audit_integrated_mmu import audit
    assert audit(path)['fits'], 'Insufficient real page-table budget'
    assert symbols['g_mmu_page_end'][0] - symbols['g_mmu_page_begin'][0] == 0x10000
    assert symbols['g_mmu_boot_info'][1] == 48 and symbols['g_mmu_boot_info'][2][:4] == b'7UMM'
    assert symbols['MmuBootReport'][1] and 'MmuBootFatal' in symbols
    start, size, instructions = symbols['Start']
    assert size == 20, 'Unexpected Start boot guard layout'
    branch = struct.unpack_from('<I', instructions, 12)[0]
    assert branch & 0xff00001f == 0x35000000, 'Start must CBNZ w0 after mmu_init'
    immediate = (branch >> 5) & 0x7ffff
    if immediate & 0x40000:
        immediate -= 0x80000
    assert start + 12 + immediate * 4 == symbols['MmuBootFatal'][0], 'MMU failure must branch to fatal path'
    ethernet = 'Rk3572EthTest' in symbols
    assert symbols['g_stacks'][1] == (4 if ethernet else 3) * 0x4000 and symbols['g_stacks'][0] % 16 == 0
    regions = list(struct.iter_unpack('<5Q', symbols['g_mem_map_info'][2]))
    assert len(regions) == (14 if ethernet and cpu == 5 else 11)
    image = 0x7B200000 if cpu == 4 else 0x7C200000
    shared = 0x7A080000 if cpu == 4 else 0x7A0A0000
    log = 0x7B000000 if cpu == 4 else 0x7C000000
    pages = ({0x2AB10000, 0x2C160000, 0x26500000, 0x26090000, 0x260B0000, 0x26074000, 0x26086000}
             if cpu == 4 else
             {0x2AB30000, 0x2C1A0000, 0x2C140000, 0x26090000, 0x26084000, 0x26074000, 0x26082000})
    assert {(r[0], r[2]) for r in regions if r[0] in pages} == {(p, 0x1000) for p in pages}
    extra = {0x2A040000, 0x2602A000, 0x7CA10000} if ethernet and cpu == 5 else set()
    assert {r[0] for r in regions} == pages | {image, shared, log, 0x2A600000} | extra
    for virtual, physical, size, level, attrs in regions:
        assert virtual == physical
        if virtual in pages:
            assert level == 3 and attrs == 0x60000000000400, 'Peripheral page must be device RW/XN'
        if virtual == 0x2A600000:
            assert size == 0x4000 and level == 3, 'GIC mapping is not the verified 16 KiB window'
        if virtual == image:
            assert size == 0x800000
        if virtual == 0x2A040000:
            assert size == 0x2000 and level == 3 and attrs == 0x60000000000400
        if virtual == 0x2602A000:
            assert size == 0x1000 and level == 3 and attrs == 0x60000000000400
        if virtual == 0x7CA10000:
            assert size == 0x10000 and level == 3 and attrs == 0x6000000000070c
            assert virtual >= symbols['g_mmu_page_end'][0] and virtual + size <= 0x7D000000
    print(f'ELF STATIC PASS UP{cpu - 3}: cumulative drivers + control/log; Ethernet={ethernet}; exact owned mappings')
    print('MMIO pages:', ' '.join(f'0x{p:08x}' for p in sorted(pages)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'firmware')
    firmware = parser.parse_args().firmware_dir
    verify(firmware / 'tl3572-m7-integrated-up-a.elf', 4)
    verify(firmware / 'tl3572-m7-integrated-up-b.elf', 5)
    print('No deployment or hardware result implied by this static verification.')
