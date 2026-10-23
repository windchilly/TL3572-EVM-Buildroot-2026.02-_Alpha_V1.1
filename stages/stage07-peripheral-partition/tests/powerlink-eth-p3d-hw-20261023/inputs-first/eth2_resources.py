"""Read CRU only. Never probe GMAC/GRF when fabric roots may be gated."""
import mmap
import os
import struct

ROOT_GATE = 0x260908A8


def validate_fabric_gate(value):
    # Shared ACLK/PCLK NVM0 roots, not the UP-owned GMAC1 leaf gates.
    if value & 0x6:
        raise RuntimeError(f'NVM0 shared ACLK/PCLK root gated (CRU42={value:#x}); '
                           'refuse GRF/GMAC access or UP start; fabric clock hold is required')


def require_fabric_clocks():
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, 4096, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ,
                       offset=ROOT_GATE & ~4095) as memory:
            value = struct.unpack_from('<I', memory, ROOT_GATE & 4095)[0]
    finally:
        os.close(fd)
    validate_fabric_gate(value)
    return value
